"""QA round-1 regression tests: replay semantics and the after_seq cursor (Sentry Q-2, S-5).

Pins three contracts that the two-gateway SPINE depends on:
- same-channel replay of an existing message id converges silently (no re-broadcast)
- replaying a message id into a DIFFERENT channel is refused (409)
- list_messages after_seq filtering is immune to created_at spelling variants
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import _pkg  # noqa: E402

_, store, _tools = _pkg.load()


class ReplaySemanticsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "herd.db"
        self.settings = {"display_name": "tyler", "__secrets__": {}}
        store.DB_PATH_OVERRIDE = self.db
        store.SETTINGS_OVERRIDE = self.settings
        store.AUTO_SYNC = False
        self.notifications = []
        self._saved_notify = store._notify
        store._notify = lambda event, payload: self.notifications.append((event, payload))

    def tearDown(self):
        store._notify = self._saved_notify
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        store.AUTO_SYNC = True
        self.tmp.cleanup()

    def _message_created_count(self):
        return sum(1 for event, _ in self.notifications if event == "message.created")

    def test_same_channel_replay_converges_silently(self):
        first = store.post_message("general", "once", message_id="fixed-uuid")
        second = store.post_message("general", "replayed", message_id="fixed-uuid")
        # The original row is returned unchanged; no duplicate was inserted.
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["content"], "once")
        rows = store.list_messages("general")
        self.assertEqual([r["content"] for r in rows], ["once"])
        # Exactly one broadcast — the replay stays silent.
        self.assertEqual(self._message_created_count(), 1)

    def test_cross_channel_replay_is_refused(self):
        store.post_message("general", "in general", message_id="shared-id")
        store.create_channel("beta")
        with self.assertRaises(store.HerdError) as caught:
            store.post_message("beta", "in beta", message_id="shared-id")
        self.assertEqual(caught.exception.status, 409)
        # Neither channel gained a row from the refused replay.
        self.assertEqual(len(store.list_messages("general")), 1)
        self.assertEqual(store.list_messages("beta"), [])
        self.assertEqual(self._message_created_count(), 1)

    def test_after_seq_cursor_immune_to_timestamp_spelling(self):
        # Three DISTINCT, monotonic instants — each spelled differently (Z suffix,
        # +00:00 offset, fractional seconds). Chronological and lexicographic order
        # agree on this triple, so any reasonable ordering must match insertion order.
        spellings = [
            "2026-11-05T12:00:00Z",
            "2026-11-05T12:00:01+00:00",
            "2026-11-05T12:00:02.123456+00:00",
        ]
        batch = {
            "from": {"gateway_id": "peer-gw", "display_name": "peer"},
            "channels": [{"id": store.resolve_channel("general")["id"],
                          "name": "general", "topic": "", "is_dm": 0, "members": ""}],
            "messages": [
                {"id": f"m-{i}", "channel_id": store.resolve_channel("general")["id"],
                 "author_type": "human", "author_name": "peer", "gateway_id": "peer-gw",
                 "gateway_name": "peer", "content": f"msg-{i}", "created_at": ts}
                for i, ts in enumerate(spellings)
            ],
        }
        store.ingest(json.loads(json.dumps(batch)))
        rows = store.list_messages("general")
        self.assertEqual(len(rows), 3)
        # Cursor by seq: everything after the first row, regardless of spelling.
        tail = store.list_messages("general", after_seq=rows[0]["seq"])
        self.assertEqual([r["content"] for r in tail],
                         ["msg-1", "msg-2"])
        # And a cursor at the last row returns nothing further.
        self.assertEqual(store.list_messages("general", after_seq=rows[-1]["seq"]), [])

    def test_peer_ingest_replays_local_row_silently(self):
        # Belt-and-suspenders pin (probe authored by Sentry, round 3): a peer echoing
        # a locally-originated row back through handle_peer_sync must be a no-op —
        # no duplicate row, no extra broadcast, no crash.
        local = store.post_message("general", "local hello", message_id="local-uuid-1")
        self.assertEqual(self._message_created_count(), 1)
        chan = store.resolve_channel("general")
        batch = {
            "v": 1,
            "from": {"gateway_id": "peer-gw", "display_name": "peer"},
            "channels": [dict(chan, is_dm=0, members="")],
            "messages": [dict(local, seq=999)],
        }
        result = store.handle_peer_sync(json.loads(json.dumps(batch)))
        self.assertEqual(result["accepted"], 0)
        rows = store.list_messages("general")
        self.assertEqual([r["id"] for r in rows], ["local-uuid-1"])
        self.assertEqual(self._message_created_count(), 1)


if __name__ == "__main__":
    unittest.main()
