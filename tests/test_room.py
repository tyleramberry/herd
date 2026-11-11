"""The team room, end to end: real Herd stores syncing over real HTTP with the real relay (relay/server.mjs).

Nobody here is linked to anybody else. Everyone joins one room from one invite link, and the room carries
messages, DMs, edits, deletes, reactions, presence and typing between them, and holds what was written while
someone was away."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_store import Gateway  # noqa: E402

_, store, _tools = _pkg.load()
ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


def _node_has_sqlite() -> bool:
    if not NODE:
        return False
    out = subprocess.run([NODE, "-e", "import('node:sqlite').then(()=>process.exit(0),()=>process.exit(1))"],
                         capture_output=True)
    return out.returncode == 0


@unittest.skipUnless(_node_has_sqlite(), "needs node 22.5+ to run the relay")
class RoomTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.Popen(
            [NODE, "--no-warnings", str(ROOT / "relay" / "server.mjs"), "--port", "0", "--hold-ms", "400"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        line = cls.proc.stdout.readline()
        cls.relay = re.search(r"http://\S+", line).group(0)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.proc.stdout.close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        store.AUTO_SYNC = False
        store.TRANSPORT = None
        store._initialized.clear()
        store._wake_times.clear()
        store._typing_peers.clear()
        store.clear_typing()
        self.A, self.B, self.C = (Gateway(root, n) for n in ("tyler", "riley", "sam"))
        with self.A:
            self.invite = store.create_room(self.relay)["invite"]
            self.a_id = store.identity()["gateway_id"]
        for gw in (self.B, self.C):
            with gw:
                store.join_room(self.invite)
        with self.B:
            self.b_id = store.identity()["gateway_id"]
        with self.C:
            self.c_id = store.identity()["gateway_id"]
        self.sync(self.A, self.B, self.C, self.A, self.B)  # everyone has met the room, and so each other

    def tearDown(self):
        store.WAKE_HANDLER = None
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        store.AUTO_SYNC = True
        self.tmp.cleanup()

    def sync(self, *gateways):
        for gw in gateways:
            with gw:
                store._room_kick.set()
                results = store.sync_all()
                self.assertEqual([r["name"] for r in results], [store.RELAY_PEER_NAME])
                self.assertTrue(results[0]["ok"], results)

    def texts(self, gw, channel="general"):
        with gw:
            return [m["content"] for m in store.list_messages(channel)]

    # -- joining ---------------------------------------------------------------------------------------------

    def test_one_link_puts_everyone_in_the_same_conversation(self):
        with self.A:
            store.post_message("general", "hello team")
        self.sync(self.A, self.B, self.C)
        self.assertEqual(self.texts(self.B), ["hello team"])
        self.assertEqual(self.texts(self.C), ["hello team"])
        with self.C:
            store.post_message("general", "hi from sam")
        self.sync(self.C, self.A, self.B)
        self.assertEqual(self.texts(self.A), ["hello team", "hi from sam"])
        self.assertEqual(self.texts(self.B), ["hello team", "hi from sam"])

    def test_people_lists_teammates_online_and_never_the_room_itself(self):
        with self.B:
            people = {p["display_name"]: p for p in store.list_participants()}
            self.assertEqual(set(people), {"riley", "tyler", "sam"})
            self.assertTrue(all(p["online"] for p in people.values()))
            st = store.status()
            self.assertEqual(st["room"]["joined"], True)
            self.assertTrue(st["room"]["connected"], st["room"])
            self.assertNotIn("#", json.dumps(st))  # the key is never in the status
            self.assertEqual(st["peers"], [])
            self.assertEqual(store.room_invite()["invite"], self.invite)

    def test_a_message_written_while_you_were_away_is_waiting_and_your_agent_answers_it(self):
        woken = []
        with self.A:
            store.post_message("general", "@riley can you look at this when you are back?")
        self.sync(self.A)  # riley's Herd is not running: nothing of theirs syncs
        store.WAKE_HANDLER = lambda key, text: woken.append(text) or True
        with self.B:
            store.set_mention_target("chat-1", "this chat")
        self.sync(self.B)
        self.assertEqual(self.texts(self.B), ["@riley can you look at this when you are back?"])
        self.assertEqual(len(woken), 1)
        self.sync(self.B, self.A)  # the pickup mark travels back through the room
        with self.A:
            self.assertEqual([r["emoji"] for r in store.list_messages("general")[0]["reactions"]], ["👀"])

    def test_what_a_new_member_brings_is_history_not_news(self):
        woken = []
        root = Path(self.tmp.name)
        d = Gateway(root, "dana")
        with d:
            store.post_message("general", "@tyler an old note from before I joined")
            store.join_room(self.invite)
        store.WAKE_HANDLER = lambda key, text: woken.append(text) or True
        with self.A:
            store.set_mention_target("chat-1", "this chat")
        self.sync(d, d, self.A)
        self.assertIn("@tyler an old note from before I joined", self.texts(self.A))
        self.assertEqual(woken, [])
        with d:
            store.post_message("general", "@tyler and this one is new")
        self.sync(d, self.A)
        self.assertEqual(len(woken), 1)

    # -- privacy ---------------------------------------------------------------------------------------------

    def test_a_dm_reaches_only_its_two_people(self):
        with self.A:
            dm = store.open_dm(self.b_id)
            store.post_message(dm["id"], "just between us")
        self.sync(self.A, self.B, self.C)
        self.assertEqual(self.texts(self.B, dm["id"]), ["just between us"])
        with self.C:
            self.assertIsNone(store.get_channel(dm["id"]))
            with store.connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)

    def _raw_sync(self, body, key=None):
        url, room_key = store.parse_room_link(self.invite)
        req = urllib.request.Request(url + store.PEER_SYNC_PATH, data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {key or room_key}",
                                              "Content-Type": "application/json"})
        with store._OPEN_PEER(req, timeout=5) as resp:
            return json.loads(resp.read())

    def test_a_member_cannot_ask_as_someone_else(self):
        with self.A:
            dm = store.open_dm(self.b_id)
            store.post_message(dm["id"], "just between us")
        self.sync(self.A)
        with self.C:
            token = store.relay_member_token()
        with self.assertRaises(urllib.error.HTTPError) as c:
            self._raw_sync({"from": {"gateway_id": self.b_id, "display_name": "riley", "token": token}})
        self.assertEqual(c.exception.code, 403)
        own = self._raw_sync({"from": {"gateway_id": self.c_id, "display_name": "sam", "token": token}})
        self.assertEqual([m for m in own["messages"] if m["channel_id"] == dm["id"]], [])
        self.assertNotIn(dm["id"], [c["id"] for c in own["channels"]])

    def test_the_wrong_key_is_refused_and_says_so(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            self._raw_sync({"from": {"gateway_id": "x1", "token": "t" * 32}}, key="k" * 40)
        self.assertEqual(c.exception.code, 401)
        url, _ = store.parse_room_link(self.invite)
        with self.C:
            store.join_room(f"{url}#{'z' * 43}")
            store._room_kick.set()
            [res] = store.sync_all()
            self.assertFalse(res["ok"])
            self.assertIn("refused this invite link", store.status()["room"]["last_error"])

    def test_a_private_channel_and_a_group_go_only_to_their_members(self):
        with self.A:
            store.create_channel("founders", members=[self.b_id])
            store.post_message("founders", "numbers are in")
            group = store.open_group([self.b_id, self.c_id])
            store.post_message(group["id"], "all three of us")
        self.sync(self.A, self.B, self.C)
        self.assertEqual(self.texts(self.B, "founders"), ["numbers are in"])
        with self.C:
            self.assertIsNone(store.get_channel("founders"))
            got = store.get_channel(group["id"])
            self.assertTrue(got["is_group"])
            self.assertEqual(store.open_group([self.a_id, self.b_id])["id"], group["id"])  # the same group
        self.assertEqual(self.texts(self.C, group["id"]), ["all three of us"])
        with self.B:
            self.assertTrue(store.get_channel("founders")["is_private"])

    # -- everything else rides along ---------------------------------------------------------------------------

    def test_edits_deletes_reactions_and_threads_cross_the_room(self):
        with self.A:
            first = store.post_message("general", "frist")["id"]
            second = store.post_message("general", "delete me")["id"]
        self.sync(self.A, self.B)
        with self.B:
            store.toggle_reaction("general", first, "🚀")
            store.post_message("general", "a reply", thread_parent_id=first)
        with self.A:
            store.edit_message(first, "first")
            store.delete_message(second)
        self.sync(self.A, self.B, self.A, self.C)
        for gw in (self.A, self.B, self.C):
            with gw:
                [m] = store.list_messages("general")
                self.assertEqual(m["content"], "first")
                self.assertTrue(m["edited_at"])
                self.assertEqual(m["reply_count"], 1)
                self.assertEqual([r["emoji"] for r in m["reactions"]], ["🚀"])

    def test_typing_reaches_teammates(self):
        with self.A:
            store.set_typing("general")
        self.sync(self.A)
        store.clear_typing()
        self.sync(self.B)
        self.assertIn({"gateway_id": self.a_id, "name": "tyler", "channel_id": "general"}, store.typing_list())

    def test_the_wait_line_answers_when_something_changes(self):
        self.sync(self.A, self.B)
        with self.B:
            peer = store.relay_peer()
            self.assertFalse(store._room_wait_once(peer)["changed"])  # held ~0.4 s, then: nothing new
        with self.A:
            store.post_message("general", "ping")
        self.sync(self.A)
        with self.B:
            self.assertTrue(store._room_wait_once(peer)["changed"])
        self.sync(self.B)
        self.assertEqual(self.texts(self.B), ["ping"])

    def test_leaving_keeps_your_messages_and_stops_syncing(self):
        with self.A:
            store.post_message("general", "before")
        self.sync(self.A, self.B)
        with self.B:
            store.leave_room()
            self.assertEqual(store.status()["room"], {"joined": False})
            self.assertEqual(store.sync_all(), [])
        self.assertEqual(self.texts(self.B), ["before"])


class RoomLinks(unittest.TestCase):
    def test_parsing(self):
        ok = "https://relay.example.workers.dev/r/abcdef0123456789#" + "k" * 43
        self.assertEqual(store.parse_room_link(ok), ("https://relay.example.workers.dev/r/abcdef0123456789", "k" * 43))
        self.assertEqual(store.parse_room_link(ok.split("#")[0]), ("https://relay.example.workers.dev/r/abcdef0123456789", ""))
        for bad in ("", "hello", "https://x.example/abc", "ftp://x.example/r/abcdef0123456789",
                    "https://user@x.example/r/abcdef0123456789", "https://x.example/r/short",
                    "https://x.example/r/abcdef0123456789#bad key", "http://[::1/r/abcdef0123456789"):
            self.assertEqual(store.parse_room_link(bad), ("", ""), bad)
        self.assertTrue(store.is_room_link(ok))
        self.assertFalse(store.is_room_link("https://riley.example:8642/#ABCDE-FGHJK"))


if __name__ == "__main__":
    unittest.main()
