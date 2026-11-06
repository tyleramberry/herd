"""S-13 / TC-10: promote a DM into a shared channel (two gateways simulated in-process)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_store import Gateway  # noqa: E402

_, store, tools = _pkg.load()


class ShareDmTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.A = Gateway(root, "tyler", peer="brooklyn")
        self.B = Gateway(root, "brooklyn")
        store.AUTO_SYNC = False

        def transport(peer, body):
            with self.B:
                return json.loads(json.dumps(store.handle_peer_sync(json.loads(json.dumps(body)))))

        store.TRANSPORT = transport
        self.woken = []
        store.WAKE_HANDLER = lambda target, text: self.woken.append((target, text)) or True

    def tearDown(self):
        store.TRANSPORT = None
        store.WAKE_HANDLER = None
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        self.tmp.cleanup()

    def sync(self):
        with self.A:
            store.sync_all()

    def seeded_dm(self):
        """Link, open the DM on A, and exchange messages including a thread and a reaction."""
        self.sync()
        with self.A:
            dm = store.open_dm(next(p["id"] for p in store.list_participants() if not p["is_self"]))
            first = store.post_message(dm["id"], "hi brooklyn")
        self.sync()
        with self.B:
            store.post_message(dm["id"], "hi tyler")
            store.post_message(dm["id"], "in a thread", thread_parent_id=first["id"])
        self.sync()
        with self.A:
            store.toggle_reaction(dm["id"], first["id"], "👍")
        self.sync()
        return dm, first

    def texts(self, gw, ch):
        with gw:
            return [m["content"] for m in store.list_messages(ch)]

    def test_share_copies_history_and_leaves_dm_alone(self):
        dm, first = self.seeded_dm()
        with self.A:
            before = [m["id"] for m in store.list_messages(dm["id"])]
            out = store.share_dm(dm["id"], "Launch Room")
            self.assertEqual(out["id"], "launch-room")
            self.assertEqual(out["message_count"], 3)
            msgs = store.list_messages("launch-room")
            self.assertEqual([m["content"] for m in msgs], ["hi brooklyn", "hi tyler"])      # 10.2/10.3
            self.assertEqual([m["author_name"] for m in msgs], ["tyler", "brooklyn"])
            self.assertTrue(all(m["promoted_from"] == dm["id"] for m in msgs))
            self.assertEqual(msgs[0]["reply_count"], 1)                                      # thread kept
            self.assertEqual(msgs[0]["reactions"], [])                                       # not copied
            self.assertEqual([m["id"] for m in store.list_messages(dm["id"])], before)       # DM untouched
            self.assertTrue(store.get_channel(dm["id"])["is_dm"])
            self.assertFalse(set(m["id"] for m in msgs) & set(before))                       # fresh ids

    def test_converges_to_peer(self):
        dm, _ = self.seeded_dm()
        with self.A:
            store.share_dm(dm["id"], "launch")
        self.sync()
        self.assertEqual(self.texts(self.B, "launch"), ["hi brooklyn", "hi tyler"])          # 10.4
        with self.B:
            self.assertFalse(store.get_channel("launch")["is_dm"])
            ids = [m["id"] for m in store.list_messages("launch")]
        self.sync()
        self.sync()
        with self.B:
            self.assertEqual([m["id"] for m in store.list_messages("launch")], ids)          # no dupes
        # Both sides can now post and read in the new channel.
        with self.B:
            store.post_message("launch", "from brooklyn")
        self.sync()
        self.assertEqual(self.texts(self.A, "launch")[-1], "from brooklyn")

    def test_rules(self):
        dm, _ = self.seeded_dm()
        with self.A:
            for bad, status in (("", 422), ("Bad/Name", 422), ("general", 409)):
                with self.assertRaises(store.HerdError) as cm:
                    store.share_dm(dm["id"], bad)
                self.assertEqual(cm.exception.status, status)
            with self.assertRaises(store.HerdError) as cm:
                store.share_dm("general", "x")                                              # not a DM
            self.assertEqual(cm.exception.status, 404)
            store.share_dm(dm["id"], "once")
            with self.assertRaises(store.HerdError) as cm:
                store.share_dm(dm["id"], "once")                                            # repeat
            self.assertEqual(cm.exception.status, 409)
            self.assertEqual(len(store.list_messages("once")), 2)                           # not doubled

    def test_empty_dm_refused(self):
        self.sync()
        with self.A:
            dm = store.open_dm(next(p["id"] for p in store.list_participants() if not p["is_self"]))
            with self.assertRaises(store.HerdError) as cm:
                store.share_dm(dm["id"], "empty")
            self.assertEqual(cm.exception.status, 422)
            self.assertIsNone(store.get_channel("empty"))

    def test_copies_do_not_wake_agent(self):
        dm, _ = self.seeded_dm()
        with self.A:
            store.post_message(dm["id"], "@brooklyn-hermes please look")
        self.sync()
        with self.B:
            store.SETTINGS_OVERRIDE["mention_wake"] = True
            store.set_mention_target("sess")
        with self.A:
            store.share_dm(dm["id"], "wakeless")
        self.woken.clear()
        self.sync()
        self.assertEqual(self.woken, [])
        self.assertIn("@brooklyn-hermes please look", self.texts(self.B, "wakeless"))

    def test_protocol_version_and_status(self):
        self.assertEqual(store.PROTOCOL_VERSION, 2)
        with self.A:
            self.assertEqual(store.status()["protocol"], 2)

    def test_old_peer_row_without_field_still_ingests(self):
        with self.B:
            n = store.ingest({"from": {"gateway_id": "g1", "display_name": "old"}, "channels": [],
                              "messages": [{"id": "m1", "channel_id": "general", "author_type": "human",
                                            "author_name": "old", "gateway_id": "g1", "content": "hi",
                                            "created_at": "2026-11-01T00:00:00Z"}]})
            self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
