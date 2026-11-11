"""Rule 11: the peer bearer key must never survive a redirect (pre-flight audit B1).

The old code fell back to plain ``urllib.request.urlopen`` when the core
credentialed-url helper could not be imported, and urllib copies the ``Authorization``
header onto whatever a 3xx points at. This is the audit's probe, encoded: origin A
redirects to origin B, so B must see no request at all (the 3xx surfaces as an
``HTTPError``) while a same-origin POST still returns 200.
"""
import json
import os
import sys
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, _tools = _pkg.load()

KEY = "peer-key-do-not-leak"


def _server(record, lock, status, location=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the test output clean
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            with lock:
                record.append({"path": self.path, "authorization": self.headers.get("Authorization")})
            payload = b"{}"
            self.send_response(status)
            if location:
                self.send_header("Location", location)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class PeerRedirectSecurity(unittest.TestCase):
    def setUp(self):
        self.lock = threading.Lock()
        self.target_hits = []   # requests the redirect TARGET saw
        self.origin_hits = []   # requests the origin saw
        store.AUTO_SYNC = False
        self.target, self.target_url = _server(self.target_hits, self.lock, 200)
        self.origin, self.origin_url = _server(self.origin_hits, self.lock, 302,
                                               self.target_url + store.PEER_SYNC_PATH)

    def tearDown(self):
        for server in (self.origin, self.target):
            server.shutdown()
            server.server_close()

    @staticmethod
    def peer(url):
        return {"name": "riley", "url": url, "key": KEY}

    def test_cross_origin_redirect_never_receives_the_key(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            store._http_sync(self.peer(self.origin_url), {"from": "tyler", "messages": []})
        self.assertEqual(caught.exception.code, 302)      # surfaced, not followed
        self.assertEqual(self.target_hits, [])            # the other origin saw nothing at all
        self.assertEqual(len(self.origin_hits), 1)        # ...and the peer itself did get the POST
        self.assertEqual(self.origin_hits[0]["authorization"], f"Bearer {KEY}")

    def test_same_origin_post_still_works(self):
        self.assertEqual(store._http_sync(self.peer(self.target_url), {"from": "tyler"}), {})
        self.assertEqual(self.target_hits[0]["authorization"], f"Bearer {KEY}")

    def test_no_plain_urlopen_fallback_remains(self):
        # The fallback existed only to survive a failed core import; no core import and no
        # unguarded opener should be left (this also clears the validator's rule-9 WARN).
        source = (Path(__file__).resolve().parent.parent / "dashboard" / "multiplayer_store.py").read_text()
        self.assertNotIn("urllib_security", source)
        self.assertNotIn("urllib.request.urlopen", source)
        self.assertIn("build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open", source)
        self.assertNotIn("build_opener(_NoRedirect()).open", source)  # the pre-fix form must be gone


if __name__ == "__main__":
    unittest.main()
