"""A database replaced under a live process must not error until restart (QA observation).

``herd_store`` caches schema init per DB path per process. When the file is replaced
(restore, copy, rm + recreate) the cache still says "initialized", so queries ran against a
schema-less database and the peer route answered 500 until the gateway was restarted. The
per-connect usability check makes that self-healing.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, _tools = _pkg.load()


class SchemaSelfHeal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "herd.db"
        self.saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC)
        store.DB_PATH_OVERRIDE = self.db
        store.SETTINGS_OVERRIDE = {"display_name": "tyler"}
        store.AUTO_SYNC = False
        store._initialized.clear()  # module-level cache: keep this test independent of run order

    def tearDown(self):
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC = self.saved
        store._initialized.clear()
        self.tmp.cleanup()

    def _replace_db_with_empty_file(self):
        """What a restore/copy/rm under a live process leaves behind: same path, no schema."""
        for suffix in ("", "-wal", "-shm"):
            path = Path(str(self.db) + suffix)
            if path.exists():
                path.unlink()
        sqlite3.connect(str(self.db)).close()

    def test_replaced_db_recovers_without_restart(self):
        store.post_message("general", "before")  # initializes the per-path cache
        self.assertIn(str(self.db), store._initialized)
        self._replace_db_with_empty_file()
        self.assertEqual(store.list_messages("general"), [])  # must not raise
        with store.connect() as conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"messages", "channels", "peer_state", "reactions"} <= tables)

    def test_peer_route_recovers_after_replacement(self):
        # The surface QA saw 500 on: the peer route, driven directly.
        store.post_message("general", "before")
        self._replace_db_with_empty_file()
        resp = store.handle_peer_sync(
            {"from": {"gateway_id": "peer-gw", "display_name": "riley"},
             "channels": [],
             "messages": [{"id": "m1", "channel_id": "general", "content": "hi", "author_type": "human",
                           "author_name": "riley", "created_at": "2026-11-07T12:00:00.000+00:00"}]})
        self.assertEqual(resp.get("accepted"), 1)
        self.assertEqual([m["content"] for m in store.list_messages("general")], ["hi"])

    def test_healthy_db_is_not_reinitialized(self):
        # Positive control: an intact DB must keep its rows and identity, so the new check
        # cannot pass by simply rebuilding the file every connect.
        store.post_message("general", "keep me")
        before = store.identity()["gateway_id"]
        self.assertEqual([m["content"] for m in store.list_messages("general")], ["keep me"])
        self.assertEqual(store.identity()["gateway_id"], before)

    def test_partial_schema_is_repaired(self):
        # A replaced DB that has *some* tables but not the ones we query is also healed.
        store.post_message("general", "before")
        for suffix in ("", "-wal", "-shm"):
            path = Path(str(self.db) + suffix)
            if path.exists():
                path.unlink()
        conn = sqlite3.connect(str(self.db))
        conn.execute("CREATE TABLE unrelated (x TEXT)")
        conn.commit()
        conn.close()
        self.assertEqual(store.list_messages("general"), [])
        with store.connect() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
        self.assertTrue({"id", "channel_id", "thread_parent_id", "task_id"} <= cols)


if __name__ == "__main__":
    unittest.main()
