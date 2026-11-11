"""The real client path (urllib, Bearer key, JSON) against a stdlib HTTP stand-in for gateway B."""
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, _tools = _pkg.load()
KEY = "riley-api-server-key"


class TwoGatewaysOverHttp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.lock = threading.Lock()
        self.b_db, self.a_db = root / "b.db", root / "a.db"
        self.b_settings = {"display_name": "riley"}
        store.AUTO_SYNC = False
        store.TRANSPORT = None
        test = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                if self.path != store.PEER_SYNC_PATH:
                    return self._send(404, {"error": "not found"})
                if self.headers.get("Authorization") != f"Bearer {KEY}":
                    return self._send(401, {"error": "bad key"})
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE)
                store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = test.b_db, test.b_settings
                try:
                    out = store.handle_peer_sync(body)
                finally:
                    store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = saved
                self._send(200, out)

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        self.tmp.cleanup()

    def use_a(self, key=KEY, url=None):
        store.DB_PATH_OVERRIDE = self.a_db
        store.SETTINGS_OVERRIDE = {"display_name": "tyler", "peer_name": "riley", "peer_url": url or self.url,
                                   "__secrets__": {"HERMES_MULTIPLAYER_PEER_KEY": key}}

    def test_round_trip_over_http(self):
        self.use_a()
        store.post_message("general", "hello riley")
        [res] = store.sync_all()
        self.assertTrue(res["ok"], res)
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = self.b_db, self.b_settings
        self.assertEqual([m["content"] for m in store.list_messages("general")], ["hello riley"])
        store.post_message("general", "hi tyler")
        self.use_a()
        [res] = store.sync_all()
        self.assertTrue(res["ok"], res)
        self.assertEqual([m["content"] for m in store.list_messages("general")], ["hello riley", "hi tyler"])
        st = store.status()["peers"][0]
        self.assertTrue(st["connected"])
        self.assertEqual(st["remote_name"], "riley")

    def test_passive_side_reports_incoming_over_http(self):
        self.use_a()
        [res] = store.sync_all()
        self.assertTrue(res["ok"], res)
        a_id = store.identity()["gateway_id"]
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = self.b_db, self.b_settings
        st = store.status()
        self.assertEqual(st["peers"], [])
        [inc] = st["incoming"]
        self.assertEqual((inc["gateway_id"], inc["name"], inc["linked_back"]), (a_id, "tyler", False))

    def test_wrong_key_is_a_friendly_error(self):
        self.use_a(key="wrong")
        [res] = store.sync_all()
        self.assertFalse(res["ok"])
        self.assertIn("rejected our Hermes Multiplayer secret", res["error"])

    def test_multiplayer_not_enabled_on_peer(self):
        self.use_a(url=self.url + "/nothing-here")
        [res] = store.sync_all()
        self.assertFalse(res["ok"])
        self.assertIn("doesn't have Hermes Multiplayer", res["error"])

    def test_unreachable_peer(self):
        self.use_a(url="http://127.0.0.1:9")
        [res] = store.sync_all()
        self.assertFalse(res["ok"])
        self.assertIn("reach", res["error"])


if __name__ == "__main__":
    unittest.main()
