"""Tagging an agent always gets an answer or a reason: your own agent from your own Hermes Multiplayer, a mark everyone can
see when an agent picks a mention up, answers that stay in the thread, plus the small onboarding helpers
(name from the Hermes Multiplayer page, one-line invite, who is online)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, tools = _pkg.load()


def peer_msg(content, mid, thread=None, gw="other-gw"):
    row = {"id": mid, "channel_id": "general", "author_type": "human", "author_name": "Brooklyn",
           "gateway_id": gw, "gateway_name": "Brooklyn", "content": content, "created_at": "2026-11-05T00:00:00Z"}
    if thread:
        row["thread_parent_id"] = thread
    return {"from": {"gateway_id": gw, "display_name": "Brooklyn"}, "channels": [], "messages": [row]}


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        store.AUTO_SYNC = False
        store.DB_PATH_OVERRIDE = Path(self.tmp.name) / "hermes-multiplayer.db"
        store.SETTINGS_OVERRIDE = {"display_name": "Tyler"}
        store._initialized.clear()
        store._wake_times.clear()
        store._wake_blocked.update(reason=None, at=None)
        self.woken = []
        store.WAKE_HANDLER = lambda key, text: self.woken.append((key, text)) or True
        store.set_mention_target("chat-1", "this chat")

    def tearDown(self):
        store.WAKE_HANDLER = None
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        store.AUTO_SYNC = True
        self.tmp.cleanup()


class OwnAgent(_Base):
    def test_tagging_your_own_agent_wakes_it(self):
        store.post_message("general", "@tyler-hermes summarize this channel")
        self.assertEqual(len(self.woken), 1)
        key, text = self.woken[0]
        self.assertEqual(key, "chat-1")
        self.assertIn("your own user (Tyler)", text)
        self.assertIn('multiplayer_post with channel="general"', text)
        self.assertNotIn("another person", text)

    def test_the_hermes_shortcut_wakes_your_own_agent(self):
        store.post_message("general", "hey @hermes what changed today?")
        self.assertEqual(len(self.woken), 1)

    def test_the_shortcut_from_a_teammate_wakes_nobody_here(self):
        store.ingest(peer_msg("@hermes do the thing", "m-short"))
        self.assertEqual(self.woken, [])

    def test_your_own_name_alone_is_not_a_request(self):
        store.post_message("general", "@tyler note to self")
        self.assertEqual(self.woken, [])

    def test_an_agent_post_never_wakes_the_agent(self):
        store.post_message("general", "@tyler-hermes loop?", author_type="agent")
        store.post_message("general", "@hermes loop?", author_type="agent")
        self.assertEqual(self.woken, [])

    def test_a_replayed_post_wakes_once(self):
        store.post_message("general", "@hermes once", message_id="same-id")
        store.post_message("general", "@hermes once", message_id="same-id")
        self.assertEqual(len(self.woken), 1)

    def test_no_chat_set_is_recorded_on_your_own_message(self):
        store.set_mention_target("")
        m = store.post_message("general", "@hermes anyone home?")
        self.assertEqual(self.woken, [])
        shown = store.list_messages("general")[-1]
        self.assertEqual(shown["id"], m["id"])
        self.assertEqual(shown["wake_skip"], "no_target")
        self.assertTrue(shown["wake_note"])

    def test_a_failing_wake_never_fails_the_post(self):
        def boom(key, text):
            raise RuntimeError("host down")
        store.WAKE_HANDLER = boom
        m = store.post_message("general", "@hermes still posts")
        self.assertEqual(store.get_message(m["id"])["content"], "@hermes still posts")

    def test_wake_off_applies_to_your_own_agent_too(self):
        store.SETTINGS_OVERRIDE = {"display_name": "Tyler", "mention_wake": False}
        store.post_message("general", "@hermes hello")
        self.assertEqual(self.woken, [])
        self.assertEqual(store.list_messages("general")[-1]["wake_skip"], "wake_off")


class PickupMark(_Base):
    def test_a_delivered_mention_gets_an_eyes_reaction_that_syncs(self):
        store.ingest(peer_msg("@tyler take a look", "m-ack"))
        self.assertEqual(len(self.woken), 1)
        shown = [m for m in store.list_messages("general") if m["id"] == "m-ack"][0]
        self.assertEqual(shown["reactions"], [{"emoji": "👀", "count": 1, "mine": True}])
        out = store.export_batch(0, viewer_gateway="other-gw")
        self.assertEqual([(r["message_id"], r["emoji"], r["active"]) for r in out["reactions"]],
                         [("m-ack", "👀", 1)])

    def test_the_old_eye_reaction_from_earlier_builds_still_shows(self):
        store.ingest(peer_msg("hello", "m-old"))
        batch = {"from": {"gateway_id": "other-gw", "display_name": "Brooklyn"}, "channels": [], "messages": [],
                 "reactions": [{"message_id": "m-old", "emoji": "👁️", "gateway_id": "other-gw", "active": 1,
                                "created_at": "2026-11-05T00:00:01Z"}]}
        store.ingest(batch)
        shown = [m for m in store.list_messages("general") if m["id"] == "m-old"][0]
        self.assertEqual([r["emoji"] for r in shown["reactions"]], ["👁️"])
        self.assertNotIn("👁️", store.REACTIONS)
        self.assertIn("👀", store.REACTIONS)

    def test_an_undelivered_mention_gets_no_mark(self):
        store.set_mention_target("")
        store.ingest(peer_msg("@tyler take a look", "m-skip"))
        shown = [m for m in store.list_messages("general") if m["id"] == "m-skip"][0]
        self.assertEqual(shown["reactions"], [])

    def test_your_own_tag_is_marked_too(self):
        m = store.post_message("general", "@hermes mark me")
        shown = [x for x in store.list_messages("general") if x["id"] == m["id"]][0]
        self.assertEqual([r["emoji"] for r in shown["reactions"]], ["👀"])


class ThreadAnswers(_Base):
    def test_a_mention_in_a_thread_is_answered_in_that_thread(self):
        store.ingest(peer_msg("kickoff", "root-1"))
        store.ingest(peer_msg("@tyler-hermes thoughts?", "reply-1", thread="root-1"))
        self.assertEqual(len(self.woken), 1)
        text = self.woken[0][1]
        self.assertIn('multiplayer_post with channel="general", reply_to="root-1"', text)
        self.assertIn('multiplayer_read_channel with thread="root-1"', text)

    def test_the_named_call_really_lands_in_the_thread(self):
        store.ingest(peer_msg("kickoff", "root-2"))
        import json
        out = json.loads(tools.multiplayer_post({"channel": "general", "reply_to": "root-2", "content": "on it"}))
        self.assertTrue(out["ok"])
        thread = store.list_thread("root-2")
        self.assertEqual([r["content"] for r in thread["replies"]], ["on it"])

    def test_a_thread_id_cannot_break_out_of_the_call(self):
        store.ingest(peer_msg("kickoff", 'r"x'))
        store.ingest(peer_msg("@tyler hi", "reply-q", thread='r"x'))
        text = self.woken[0][1]
        self.assertIn('reply_to="r\\"x"', text)

    def test_a_top_level_mention_still_reports_to_the_channel(self):
        store.ingest(peer_msg("@tyler hi", "top-1"))
        self.assertIn('multiplayer_post with channel="general" and your reply', self.woken[0][1])
        self.assertNotIn("reply_to", self.woken[0][1])

    def test_your_own_tag_in_a_thread_stays_in_the_thread(self):
        root = store.post_message("general", "plan for friday")
        store.post_message("general", "@hermes draft it", thread_parent_id=root["id"])
        self.assertIn(f'reply_to="{root["id"]}"', self.woken[0][1])


class Onboarding(_Base):
    def test_name_from_the_multiplayer_page_wins_and_clears(self):
        self.assertEqual(store.set_display_name("  Ty   A ")["display_name"], "Ty A")
        self.assertEqual(store.identity()["display_name"], "Ty A")
        self.assertEqual(store.post_message("general", "hi")["author_name"], "Ty A")
        self.assertEqual(store.set_display_name("")["display_name"], "Tyler")

    def test_a_name_is_one_plain_line(self):
        self.assertEqual(store.set_display_name("Ty\nler\x00")["display_name"], "Ty ler")

    def test_invite_is_one_pasted_line(self):
        self.assertEqual(store.parse_invite("https://b.ts.net:8642#ABCDE-FGHJK"),
                         ("https://b.ts.net:8642", "ABCDE-FGHJK"))
        self.assertEqual(store.parse_invite(" https://b.ts.net:8642/  ABCDE-FGHJK "),
                         ("https://b.ts.net:8642", "ABCDE-FGHJK"))
        self.assertEqual(store.parse_invite("https://b.ts.net:8642/", "abcde fghjk"),
                         ("https://b.ts.net:8642", "abcde fghjk"))
        self.assertEqual(store.parse_invite(store.make_invite("https://b.ts.net:8642/", "ABCDE-FGHJK")),
                         ("https://b.ts.net:8642", "ABCDE-FGHJK"))

    def test_a_pasted_invite_redeems(self):
        seen = {}

        def transport(url, body):
            seen["url"], seen["code"] = url, body["code"]
            raise store.urllib.error.URLError("stop here")
        store.PAIR_TRANSPORT = transport
        try:
            with self.assertRaises(store.MultiplayerError):
                store.redeem_pairing("https://b.ts.net:8642#abcde-fghjk", "")
        finally:
            store.PAIR_TRANSPORT = None
        self.assertEqual(seen, {"url": "https://b.ts.net:8642", "code": "ABCDEFGHJK"})

    def test_online_follows_the_last_exchange(self):
        store.ingest(peer_msg("hello", "m-on"))
        people = {p["display_name"]: p for p in store.list_participants()}
        self.assertTrue(people["Tyler"]["online"])
        self.assertTrue(people["Brooklyn"]["online"])
        with store.connect() as conn:
            conn.execute("UPDATE participants SET last_seen = '2026-01-01T00:00:00+00:00' WHERE is_self = 0")
        people = {p["display_name"]: p for p in store.list_participants()}
        self.assertFalse(people["Brooklyn"]["online"])


if __name__ == "__main__":
    unittest.main()
