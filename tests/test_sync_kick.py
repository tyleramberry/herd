"""The post kick waits for an in-flight sync pass instead of dropping to the next 3 s tick."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_store import Gateway  # noqa: E402

_, store, _tools = _pkg.load()


class SyncKickTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.A = Gateway(root, "tyler", peer="brooklyn")
        self.B = Gateway(root, "brooklyn")
        self._saved = (store.AUTO_SYNC, store.TRANSPORT)

        def transport(peer, body):
            with self.B:
                return json.loads(json.dumps(store.handle_peer_sync(json.loads(json.dumps(body)))))
        store.TRANSPORT = transport
        store.AUTO_SYNC = True

    def tearDown(self):
        store.AUTO_SYNC, store.TRANSPORT = self._saved
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        self.tmp.cleanup()

    def test_post_during_inflight_pass_reaches_peer_without_tick(self):
        # Overrides are process-global: keep A active for the whole test; the transport swaps to B itself.
        with self.A:
            store._sync_lock.acquire()
            try:
                store.post_message("#general", "kick me")
                time.sleep(0.3)  # the kick fires (50 ms) and finds the lock busy
                self.assertEqual(self._b_texts_unsafe(), [])
            finally:
                store._sync_lock.release()
            deadline = time.time() + 1.0
            while time.time() < deadline and "kick me" not in self._b_texts_unsafe():
                time.sleep(0.02)
            self.assertIn("kick me", self._b_texts_unsafe())

    def _b_texts_unsafe(self):
        # Read B's DB directly without flipping the global overrides under the kick thread.
        import sqlite3
        conn = sqlite3.connect(self.B.db)
        try:
            return [r[0] for r in conn.execute("SELECT content FROM messages")]
        except sqlite3.Error:
            return []
        finally:
            conn.close()

    def test_sync_all_default_returns_immediately_when_busy(self):
        with self.A:
            store._sync_lock.acquire()
            try:
                t0 = time.time()
                self.assertEqual(store.sync_all(), [])
                self.assertLess(time.time() - t0, 0.5)
            finally:
                store._sync_lock.release()

    def test_wait_gives_up_after_timeout(self):
        saved = store.SYNC_KICK_WAIT_S
        store.SYNC_KICK_WAIT_S = 0.2
        try:
            with self.A:
                store._sync_lock.acquire()
                try:
                    self.assertEqual(store.sync_all(wait=True), [])
                finally:
                    store._sync_lock.release()
        finally:
            store.SYNC_KICK_WAIT_S = saved


if __name__ == "__main__":
    unittest.main()
