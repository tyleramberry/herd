"""S-19: the peer key never travels in cleartext off loopback unless the owner opts in."""
import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, _tools = _pkg.load()
ROOT = _pkg.ROOT

SECRET = "-".join(["canary", "peer", "value"])
CLEAR_URL = "http://brooklyn-mac.local:8642"
BAD_URL = "http://[::1:8642"  # an unmatched bracket: urlsplit raises ValueError


class CleartextPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = {"display_name": "tyler", "peer_name": "brooklyn", "peer_url": CLEAR_URL,
                         "__secrets__": {"HERD_PEER_KEY": SECRET}}
        self._saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC, store.TRANSPORT)
        store.DB_PATH_OVERRIDE = Path(self.tmp.name) / "a.db"
        store.SETTINGS_OVERRIDE = self.settings
        store.AUTO_SYNC = False
        store.TRANSPORT = None

    def tearDown(self):
        (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC, store.TRANSPORT) = self._saved
        self.tmp.cleanup()

    def urls(self):
        return [p["url"] for p in store.configured_peers()]

    def test_cleartext_off_loopback_is_refused_visibly(self):
        for cfg in ({}, {"allow_cleartext_peer": False}):
            self.settings.pop("allow_cleartext_peer", None)
            self.settings.update(cfg)
            self.assertEqual(store.configured_peers(), [])
            refused = store.refused_peers()
            self.assertEqual(len(refused), 1)
            self.assertEqual(refused[0]["reason"], store.CLEARTEXT_REFUSED)
            st = store.status()
            self.assertEqual(st["peers"], [])
            self.assertEqual(st["refused"][0]["reason"], store.CLEARTEXT_REFUSED)
            self.assertIsInstance(st["refused"][0]["has_key"], bool)
            self.assertTrue(st["refused"][0]["has_key"])
            self.assertNotIn(SECRET, json.dumps(st))

    def test_opt_in_allows_cleartext(self):
        for value in (True, "true"):
            self.settings["allow_cleartext_peer"] = value
            self.assertEqual(self.urls(), [CLEAR_URL])
            self.assertEqual(store.refused_peers(), [])

    def test_https_and_loopback_always_allowed(self):
        for url in ("https://brooklyn-mac.local:8642", "http://127.0.0.1:8642",
                    "http://localhost:8642", "http://[::1]:8642"):
            self.settings["peer_url"] = url
            self.assertEqual(self.urls(), [url], url)
            self.assertEqual(store.refused_peers(), [], url)

    def test_no_request_is_issued_for_a_refused_peer(self):
        calls = []

        def counting(peer, body):
            calls.append(peer["url"])
            return {}

        with mock.patch.object(store, "_http_sync", counting):
            self.assertEqual(store.sync_all(), [])
            self.assertEqual(len(calls), 0)
            self.settings["peer_url"] = "http://127.0.0.1:8642"  # positive control
            store.sync_all()
            self.assertEqual(len(calls), 1)

        def opener(*args, **kwargs):
            self.fail("the opener must never be reached for a refused peer")

        with mock.patch.object(store, "_OPEN_PEER", opener):
            with self.assertRaises(store.PeerRefusedError) as caught:
                store._http_sync({"name": "brooklyn", "url": CLEAR_URL, "key": "k"}, {})
        self.assertEqual(str(caught.exception), store.CLEARTEXT_REFUSED)

    def test_sync_peer_surfaces_the_refusal_message(self):
        result = store.sync_peer({"name": "brooklyn", "url": CLEAR_URL, "key": SECRET})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], store.CLEARTEXT_REFUSED)

    def test_redirect_still_refused(self):
        lock = threading.Lock()
        target_hits, origin_hits = [], []

        def server(record, status, location=None):
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *a):
                    pass

                def _handle(self):
                    length = int(self.headers.get("Content-Length") or 0)
                    self.rfile.read(length)
                    with lock:
                        record.append({"method": self.command, "auth": self.headers.get("Authorization")})
                    payload = b"{}"
                    self.send_response(status)
                    if location:
                        self.send_header("Location", location)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

                do_GET = do_POST = do_HEAD = do_PUT = _handle

            srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.addCleanup(srv.server_close)
            self.addCleanup(srv.shutdown)
            return f"http://127.0.0.1:{srv.server_address[1]}"

        target = server(target_hits, 200)
        origin = server(origin_hits, 302, target + store.PEER_SYNC_PATH)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            store._http_sync({"name": "r", "url": origin, "key": SECRET}, {"messages": []})
        self.assertEqual(caught.exception.code, 302)
        self.assertEqual(target_hits, [])
        self.assertEqual(len(origin_hits), 1)
        self.assertEqual(origin_hits[0]["method"], "POST")
        self.assertEqual(origin_hits[0]["auth"], f"Bearer {SECRET}")
        # positive control: same-origin POST still works
        self.assertEqual(store._http_sync({"name": "r", "url": target, "key": SECRET}, {}), {})

    def test_no_redirect_handler_preserved(self):
        source = (Path(__file__).resolve().parent.parent / "dashboard" / "herd_store.py").read_text()
        self.assertIn("build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open", source)
        self.assertNotIn("build_opener(_NoRedirect()).open", source)  # the pre-fix form must be gone
        self.assertGreaterEqual(source.count("_NoRedirect"), 2)

    def test_env_http_proxy_never_sees_the_peer_key(self):
        """An ambient http_proxy/HTTP_PROXY must not receive the peer key (local loopback probe)."""
        sink_hits, peer_hits = [], []
        lock = threading.Lock()

        def server(record):
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *a):
                    pass

                def do_POST(self):
                    self.rfile.read(int(self.headers.get("Content-Length") or 0))
                    with lock:
                        record.append({"method": self.command, "path": self.path,
                                       "auth": self.headers.get("Authorization")})
                    payload = b"{}"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

            srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.addCleanup(srv.server_close)
            self.addCleanup(srv.shutdown)
            return f"http://127.0.0.1:{srv.server_address[1]}"

        sink_url = server(sink_hits)
        peer_url = server(peer_hits)
        proxy_env = {"http_proxy": sink_url, "HTTP_PROXY": sink_url, "no_proxy": "", "NO_PROXY": ""}

        # _OPEN_PEER is built at import time and urllib's default ProxyHandler binds getproxies() at
        # construction, so load a fresh copy of the module while the proxy variables are set.
        spec = importlib.util.spec_from_file_location(
            "herd_store_proxyprobe", ROOT / "dashboard" / "herd_store.py")
        mod = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, proxy_env):
            spec.loader.exec_module(mod)
            mod.AUTO_SYNC = False

            # Positive control (local, over loopback; not an exploit): the pre-fix opener construction
            # with the proxy env set sends the request to the sink. This makes the 0-hit check below
            # meaningful rather than vacuous.
            legacy_open = urllib.request.build_opener(mod._NoRedirect()).open
            req = urllib.request.Request(
                peer_url + mod.PEER_SYNC_PATH, data=b"{}", method="POST",
                headers={"Authorization": "Bearer canary-legacy-control", "Content-Type": "application/json"})
            with legacy_open(req, timeout=5) as resp:
                resp.read()
        if not (len(sink_hits) == 1 and not peer_hits):
            self.fail("positive control did not fire: expected the legacy opener to deliver the request to "
                      f"the proxy sink on this platform (sink={sink_hits}, peer={peer_hits}); "
                      "getproxies() may ignore the environment here")
        self.assertEqual(sink_hits[0]["auth"], "Bearer canary-legacy-control")

        with lock:
            sink_hits.clear()
            peer_hits.clear()
        with mock.patch.dict(os.environ, proxy_env):
            result = mod._http_sync({"name": "b", "url": peer_url, "key": SECRET}, {"from": {}})
        self.assertEqual(result, {})
        self.assertEqual(sink_hits, [])
        self.assertEqual(len(peer_hits), 1)
        self.assertEqual(peer_hits[0]["auth"], f"Bearer {SECRET}")

    def test_malformed_peer_url_refusal_is_a_string_not_an_exception(self):
        self.assertEqual(store._peer_url_refusal(BAD_URL), store.PEER_URL_INVALID)

    def test_malformed_url_is_refused_visibly_and_status_survives(self):
        self.settings["peer_url"] = BAD_URL
        self.assertEqual(store.configured_peers(), [])
        refused = store.refused_peers()
        self.assertEqual(len(refused), 1)
        self.assertEqual(refused[0]["reason"], store.PEER_URL_INVALID)
        self.assertIsInstance(refused[0]["has_key"], bool)
        st = store.status()  # must return, not raise
        self.assertEqual(st["peers"], [])
        self.assertEqual(st["refused"][0]["reason"], store.PEER_URL_INVALID)
        self.assertNotIn(SECRET, json.dumps(store.status()))

    def test_nothing_is_sent_for_a_malformed_url(self):
        self.settings["peer_url"] = BAD_URL
        calls = []
        with mock.patch.object(store, "_http_sync", side_effect=lambda *a, **k: calls.append(a)):
            self.assertEqual(store.sync_all(), [])
        self.assertEqual(calls, [])

        def boom(*a, **k):
            raise AssertionError("opener reached for a malformed peer_url")

        with mock.patch.object(store, "_OPEN_PEER", boom):
            with self.assertRaises(store.PeerRefusedError) as caught:
                store._http_sync({"name": "b", "url": BAD_URL, "key": "k"}, {})
        self.assertEqual(str(caught.exception), store.PEER_URL_INVALID)


if __name__ == "__main__":
    unittest.main()
