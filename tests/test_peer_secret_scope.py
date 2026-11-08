"""S-20: Herd's peer routes authenticate with Herd's OWN secret, never the gateway API_SERVER_KEY."""
import asyncio
import hmac
import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

herd, store, _tools = _pkg.load()

try:
    from aiohttp import web
    HAVE_AIOHTTP = True
except ImportError:  # pragma: no cover - depends on the venv
    web = None
    HAVE_AIOHTTP = False

API_KEY = "-".join(["gateway", "api", "server", "key"])   # B's API_SERVER_KEY (must be refused)
B_SECRET = "-".join(["b", "herd", "secret", "canary"])   # B's HERD_SECRET
A_SECRET = "-".join(["a", "herd", "secret", "canary"])   # A's own HERD_SECRET


class StubAdapter:
    """Would ACCEPT the gateway API key: a 401 for that key proves the plugin no longer asks it."""

    def __init__(self):
        self.calls = 0

    def _check_auth(self, request):
        self.calls += 1
        if (request.headers.get("Authorization") or "") == "Bearer " + API_KEY:
            return None
        return web.json_response({"error": "unauthorized"}, status=401)


class LiveServer:
    """The plugin's own ``_wire_api_server`` on 127.0.0.1:0, in a background thread + loop."""

    def __init__(self, adapter):
        self.adapter = adapter
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.url = ""

    def _run(self):
        asyncio.set_event_loop(self.loop)
        app = web.Application()
        herd._wire_api_server(app, self.adapter)
        app.on_startup.clear()  # no background sync loop in a unit test
        app.on_cleanup.clear()
        self.runner = web.AppRunner(app)
        self.loop.run_until_complete(self.runner.setup())
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        self.loop.run_until_complete(site.start())
        port = site._server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        self.ready.set()
        self.loop.run_forever()

    def start(self):
        self.thread.start()
        if not self.ready.wait(10):
            raise RuntimeError("test server did not start")
        return self

    def stop(self):
        fut = asyncio.run_coroutine_threadsafe(self.runner.cleanup(), self.loop)
        fut.result(10)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(10)
        self.loop.close()


def http(method, url, body=None, key=""):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"raw": raw.decode("utf-8", "replace")}


def load_second_store():
    """A second, independent in-process instance of herd_store.py (gateway A), like the harness."""
    spec = importlib.util.spec_from_file_location(
        "herd_store_gateway_a", Path(store.__file__).resolve())
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC, store.TRANSPORT)
        store.DB_PATH_OVERRIDE = Path(self.tmp.name) / "b.db"
        self.secrets = {"HERD_SECRET": B_SECRET}
        store.SETTINGS_OVERRIDE = {"display_name": "brooklyn", "__secrets__": self.secrets}
        store.AUTO_SYNC = False
        store.TRANSPORT = None

    def tearDown(self):
        (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC, store.TRANSPORT) = self._saved
        self.tmp.cleanup()

    def unset_secret(self):
        self.secrets.pop("HERD_SECRET", None)


class SecretHelpers(Base):
    def test_status_reports_herd_secret_set_as_bool(self):
        st = store.status()
        self.assertIs(st["herd_secret_set"], True)
        self.assertNotIn(B_SECRET, json.dumps(st))
        self.unset_secret()
        self.assertIs(store.status()["herd_secret_set"], False)

    def test_constant_time_compare_on_bytes(self):
        with mock.patch.object(store.hmac, "compare_digest", wraps=hmac.compare_digest) as cmp:
            self.assertTrue(store.inbound_authorized("Bearer " + B_SECRET))
        cmp.assert_called_once_with(B_SECRET.encode("utf-8"), B_SECRET.encode("utf-8"))

    def test_fails_closed_and_never_takes_the_api_key(self):
        self.assertFalse(store.inbound_authorized("Bearer " + API_KEY))
        self.assertFalse(store.inbound_authorized(None))
        self.assertFalse(store.inbound_authorized("Basic " + B_SECRET))
        self.assertFalse(store.inbound_authorized("Bearer " + B_SECRET + "é"))  # non-ASCII: no TypeError
        self.unset_secret()
        self.assertFalse(store.inbound_authorized("Bearer "))
        self.assertFalse(store.inbound_authorized("Bearer " + B_SECRET))


@unittest.skipUnless(HAVE_AIOHTTP, "aiohttp not installed")
class Routes(Base):
    def setUp(self):
        super().setUp()
        self.adapter = StubAdapter()
        self.server = LiveServer(self.adapter).start()
        self.sync_url = self.server.url + store.PEER_SYNC_PATH
        self.ping_url = self.server.url + "/herd/v1/ping"

    def tearDown(self):
        self.server.stop()
        super().tearDown()

    def assert_denied(self, status, body, message=None):
        self.assertEqual(status, 401, body)
        self.assertEqual(body["error"]["code"], "gateway_auth_failed")
        if message is not None:
            self.assertEqual(body["error"]["message"], message)

    def test_right_secret_reaches_sync(self):
        status, body = http("POST", self.sync_url, {}, key=B_SECRET)
        self.assertEqual(status, 200, body)
        self.assertIn("from", body)

    def test_gateway_api_key_is_rejected_on_both_routes(self):
        self.assert_denied(*http("POST", self.sync_url, {}, key=API_KEY))
        self.assert_denied(*http("GET", self.ping_url, key=API_KEY))
        self.assertEqual(self.adapter.calls, 0, "the plugin must not consult adapter._check_auth")

    def test_fail_closed_without_a_herd_secret(self):
        self.unset_secret()
        for key in (API_KEY, B_SECRET, ""):
            self.assert_denied(*http("POST", self.sync_url, {}, key=key), message=store.NO_LOCAL_SECRET)
            self.assert_denied(*http("GET", self.ping_url, key=key), message=store.NO_LOCAL_SECRET)

    def test_ping_obeys_the_same_rule(self):
        status, body = http("GET", self.ping_url, key=B_SECRET)
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"])
        self.assert_denied(*http("GET", self.ping_url, key="wrong-secret"))
        self.unset_secret()
        self.assert_denied(*http("GET", self.ping_url, key=B_SECRET))

    def test_route_goes_through_inbound_authorized(self):
        with mock.patch.object(store, "inbound_authorized", return_value=False) as check:
            self.assert_denied(*http("POST", self.sync_url, {}, key=B_SECRET))
            self.assert_denied(*http("GET", self.ping_url, key=B_SECRET))
        self.assertEqual(check.call_count, 2)
        check.assert_called_with("Bearer " + B_SECRET)

    def test_sync_peer_round_trip_over_real_http(self):
        a = load_second_store()
        a.DB_PATH_OVERRIDE = Path(self.tmp.name) / "a.db"
        a.AUTO_SYNC = False
        a.TRANSPORT = None  # the real _http_sync
        a.SETTINGS_OVERRIDE = {"display_name": "tyler", "peer_name": "brooklyn", "peer_url": self.server.url,
                               "__secrets__": {"HERD_PEER_KEY": B_SECRET, "HERD_SECRET": A_SECRET}}
        posted = a.post_message("general", "hello from A", author_type="human")
        [peer] = a.configured_peers()
        res = a.sync_peer(peer)
        self.assertIs(res["ok"], True, res)
        ids = [m["id"] for m in store.list_messages("general", limit=500)]
        self.assertIn(posted["id"], ids)

    def test_actionable_failure_text(self):
        a = load_second_store()
        a.DB_PATH_OVERRIDE = Path(self.tmp.name) / "a.db"
        a.AUTO_SYNC = False
        a.TRANSPORT = None
        a.SETTINGS_OVERRIDE = {"display_name": "tyler", "peer_name": "brooklyn", "peer_url": self.server.url,
                               "__secrets__": {"HERD_PEER_KEY": "not-" + B_SECRET, "HERD_SECRET": A_SECRET}}
        [peer] = a.configured_peers()
        res = a.sync_peer(peer)
        self.assertFalse(res["ok"])
        self.assertIn("rejected our Herd secret", res["error"])
        self.assertNotIn("API_SERVER_KEY", res["error"])
        st = a.status()
        self.assertEqual(st["peers"][0]["last_error"], res["error"])
        dumped = json.dumps(st)
        for value in (B_SECRET, A_SECRET):
            self.assertNotIn(value, dumped)
            self.assertNotIn(value, res["error"])

        self.unset_secret()  # now the peer itself has no Herd secret
        a.SETTINGS_OVERRIDE["__secrets__"]["HERD_PEER_KEY"] = B_SECRET
        res = a.sync_peer(peer)
        self.assertFalse(res["ok"])
        self.assertIn("peer has no Herd secret set", res["error"])
        dumped = json.dumps(a.status())
        for value in (B_SECRET, A_SECRET):
            self.assertNotIn(value, dumped)
            self.assertNotIn(value, res["error"])


if __name__ == "__main__":
    unittest.main()
