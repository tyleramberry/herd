"""S-15 live supervision status: fixed vocabulary, local-only, in-memory, never guessed (D-5 / D-6)."""
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

try:  # the route test is the pane's real transport; skip cleanly where fastapi isn't installed
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # noqa: BLE001
    FastAPI = TestClient = None

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, tools = _pkg.load()
ROOT = _pkg.ROOT
SOURCE = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")

# S3 hardening (t_1f78eb04): shapes that must read as unset, never raise. Nothing writes these
# today (set_status always stores a float `at`); they stand in for a corrupted in-memory record.
# `at` is <1s old at the tests' `now=1000`, so TTL expiry is not what makes a record read as unset -
# only the defect below does.
FRESH_AT = 999.0
MALFORMED_STATUS_RECORDS = (
    {"phrase": "idle"},                        # missing at
    {"phrase": "idle", "at": "oops"},          # non-numeric at
    {"phrase": "idle", "at": None},
    {"phrase": "idle", "at": True},            # bool is an int subclass, still not a timestamp
    {"phrase": "idle", "at": float("nan")},
    {"phrase": "idle", "at": float("inf")},
    {"phrase": "idle", "at": 1e300},           # numeric, but no datetime can format it
    {"at": FRESH_AT},                          # missing phrase
    {"phrase": "almost done", "at": FRESH_AT},  # invented phrase
    {"phrase": 123, "at": FRESH_AT},           # non-string phrase
    {"phrase": ["idle"], "at": FRESH_AT},      # unhashable phrase
    {},
    None,
    "idle",                                    # not a dict at all
    ["idle"],
)


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "herd.db"
        self._saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.TRANSPORT, store.AUTO_SYNC)
        store.DB_PATH_OVERRIDE = self.db
        store.SETTINGS_OVERRIDE = {"display_name": "tyler", "__secrets__": {}}
        store.AUTO_SYNC = False
        store._status = None

    def tearDown(self):
        store._status = None
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.TRANSPORT, store.AUTO_SYNC = self._saved
        self.tmp.cleanup()

    # Written first: the main way this feature can fail is showing a phrase nobody set.
    def test_unset_shows_nothing(self):
        self.assertIsNone(store.agent_status())
        self.assertIn("agent_status", store.status())
        self.assertIsNone(store.status()["agent_status"])

    # S3 hardening (t_1f78eb04): a malformed in-memory record reads as unset - it never raises out
    # of agent_status()/status() and so can never turn GET /status into a 500.
    def test_malformed_status_record_fails_closed(self):
        store._status = {"phrase": "idle", "at": FRESH_AT}
        self.assertEqual(store.agent_status(now=1000)["phrase"], "idle")  # control: fresh + valid
        for record in MALFORMED_STATUS_RECORDS:
            with self.subTest(record=record):
                store._status = record
                self.assertIsNone(store.agent_status(now=1000))
                self.assertIsNone(store.status()["agent_status"])

    def test_malformed_record_does_not_poison_a_later_valid_set(self):
        store._status = {"phrase": "idle"}          # missing `at`
        self.assertIsNone(store.agent_status())
        store.set_status("reviewing")               # the setter still works, and replaces it
        self.assertEqual(store.agent_status()["phrase"], "reviewing")
        self.assertEqual(store.status()["agent_status"]["phrase"], "reviewing")

    def test_agent_status_never_raises_on_a_bad_now(self):
        store.set_status("idle")
        for bad_now in ("oops", [], {}, True, float("nan")):
            with self.subTest(now=bad_now):
                self.assertIsNone(store.agent_status(now=bad_now))
        self.assertEqual(store.agent_status()["phrase"], "idle")   # the clock path is untouched

    def test_vocabulary_accepted_exactly(self):
        self.assertEqual(store.STATUS_PHRASES,
                         ("reading the code", "writing the code", "reviewing", "done", "idle"))
        for phrase in store.STATUS_PHRASES:
            store.set_status(phrase)
            self.assertEqual(store.agent_status()["phrase"], phrase)
            self.assertEqual(store.status()["agent_status"]["phrase"], phrase)

    def test_normalization_returns_canonical_phrase(self):
        out = store.set_status("  Writing   THE code ")
        self.assertEqual(out["phrase"], "writing the code")
        self.assertEqual(store.agent_status()["phrase"], "writing the code")

    def test_invented_phrase_refused(self):
        for bad in ("thinking about it", "ran bash", "", "reading code", None):
            with self.assertRaises(store.HerdError) as cm:
                store.set_status(bad)
            self.assertEqual(cm.exception.status, 422)
            for phrase in store.STATUS_PHRASES:
                self.assertIn(phrase, cm.exception.message)
            self.assertIsNone(store.agent_status(), bad)

    def test_refusal_does_not_clear_or_replace_valid_status(self):
        store.set_status("reviewing")
        with self.assertRaises(store.HerdError):
            store.set_status("almost done")
        self.assertEqual(store.agent_status()["phrase"], "reviewing")

    def test_tool_contract(self):
        ok = json.loads(tools.herd_set_status({"status": "reviewing"}))
        self.assertIs(ok["ok"], True)
        self.assertEqual(ok["status"], "reviewing")
        for args in ({"status": "nope"}, {}, None):
            raw = tools.herd_set_status(args)
            self.assertIsInstance(raw, str)
            bad = json.loads(raw)
            self.assertIs(bad["ok"], False)
            self.assertTrue(bad["error"])
        self.assertEqual(store.agent_status()["phrase"], "reviewing")

    def test_ttl_bound_is_exact(self):
        store.set_status("writing the code")
        at = store._status["at"]
        self.assertEqual(store.STATUS_TTL_S, 300.0)
        self.assertEqual(store.agent_status(now=at + store.STATUS_TTL_S - 1)["phrase"], "writing the code")
        self.assertIsNone(store.agent_status(now=at + store.STATUS_TTL_S))
        self.assertIsNone(store.agent_status(now=at + store.STATUS_TTL_S + 3600))

    def test_agent_status_never_touches_db(self):
        store.set_status("idle")
        with mock.patch.object(store, "connect", side_effect=AssertionError("db touched")):
            self.assertEqual(store.agent_status()["phrase"], "idle")

    def test_no_persistence_across_restart(self):
        store.set_status("writing the code")
        spec = importlib.util.spec_from_file_location(
            "herd_status_fresh", ROOT / "dashboard" / "herd_store.py")
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
        fresh.DB_PATH_OVERRIDE = self.db
        fresh.SETTINGS_OVERRIDE = dict(store.SETTINGS_OVERRIDE)
        self.assertIsNone(fresh.agent_status())
        self.assertIsNone(fresh.status()["agent_status"])
        conn = sqlite3.connect(str(self.db))
        try:
            keys = [r[0] for r in conn.execute("SELECT key FROM meta").fetchall()]
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            dump = "\n".join(conn.iterdump())
        finally:
            conn.close()
        self.assertFalse([k for k in keys if "status" in k], keys)
        self.assertFalse([t for t in tables if "status" in t], tables)
        self.assertNotIn("writing the code", dump)

    def test_set_status_makes_no_network_call(self):
        calls = []

        def broken_transport(peer, body):
            raise AssertionError("network used")

        store.TRANSPORT = broken_transport
        with mock.patch.object(store, "request_sync", side_effect=lambda: calls.append(1)):
            out = store.set_status("done")
        self.assertEqual(out["phrase"], "done")
        self.assertEqual(calls, [])

    def test_notify_rides_existing_broadcast(self):
        events = []
        with mock.patch.object(store, "_notify", side_effect=lambda e, p: events.append((e, p))):
            store.set_status("idle")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "status.changed")
        self.assertEqual(events[0][1]["phrase"], "idle")

        sent = []
        stub = types.ModuleType("hermes_cli.plugin_events")
        stub.broadcast_plugin_event = lambda plugin_id, event, payload: sent.append((plugin_id, event, payload))
        pkg = sys.modules.get("hermes_cli") or types.ModuleType("hermes_cli")
        with mock.patch.dict(sys.modules, {"hermes_cli": pkg, "hermes_cli.plugin_events": stub}):
            store._notify("status.changed", {})
        self.assertEqual(sent, [("hermes-multiplayer", "status.changed", {})])

    def test_status_survives_event_path_down(self):
        with mock.patch.object(store, "_notify", lambda e, p: None):
            store.set_status("reviewing")
        self.assertEqual(store.status()["agent_status"]["phrase"], "reviewing")
        # The pane reads the phrase from the /status query, never from the event payload.
        handler = re.search(r"ctx\.onEvent\('plugin\.hermes-multiplayer\.status\.changed'.*?\}\)", SOURCE, re.S).group(0)
        self.assertIn("invalidateQueries({ queryKey: KEYS.status })", handler)
        self.assertNotIn("payload", handler)
        self.assertNotIn("phrase", handler)


class DesktopSourceTest(unittest.TestCase):
    def test_only_agent_messages_carry_a_badge(self):
        # Spec §3: the human badge is gone; the agent badge is decided by author_type alone.
        self.assertIn("const agent = message.author_type === 'agent'", SOURCE)
        self.assertIn("agent ? jsx(Badge, { variant: 'muted', size: 'xs', children: 'agent' }) : null", SOURCE)
        self.assertNotIn("children: 'human'", SOURCE)
        self.assertNotIn("'human' ? 'default'", SOURCE)
        for line in SOURCE.splitlines():
            if "jsx(Badge" in line:
                self.assertNotIn("author_name", line)

    def test_work_line_renders_backend_phrase_only(self):
        self.assertIn("status.agent_status", SOURCE)
        self.assertIn("if (!lines.length) return null", SOURCE)  # nothing to show: no placeholder line
        self.assertIn("lines.push({ text: work.phrase", SOURCE)  # this gateway's own phrase, verbatim
        self.assertIn("jsx(WorkLine, { status })", SOURCE)

    def test_no_hardcoded_phrase_in_pane(self):
        # D-6: the pane cannot invent or hardcode a phrase. "done" also occurs inside unrelated
        # identifiers (onDone, `const done = id =>`), so for it we forbid it as a string literal in
        # any quote style; every other phrase must be absent from the source entirely.
        lowered = SOURCE.casefold()
        for phrase in store.STATUS_PHRASES:
            for q in ("'", '"', "`"):
                self.assertNotIn(q + phrase, lowered, phrase)
            if phrase != "done":
                self.assertNotIn(phrase, lowered, phrase)

    def test_one_new_event_and_no_new_timer(self):
        events = re.findall(r"ctx\.onEvent\('plugin\.hermes-multiplayer\.([a-z_.]+)'", SOURCE)
        # Four pre-existing handlers (message.created, reactions.changed, channels.changed,
        # settings.changed), status.changed (S-15) and incoming.messages (Track 2, notifications).
        # typing.changed and presence.changed (team room) only invalidate queries the pane already polls.
        self.assertEqual(sorted(events), sorted(["message.created", "reactions.changed", "channels.changed",
                                                 "settings.changed", "status.changed", "incoming.messages",
                                                 "typing.changed", "presence.changed"]))
        self.assertEqual(SOURCE.count("ctx.setInterval("), 2)


class StatusRouteTest(unittest.TestCase):
    """The pane's real transport: GET /api/plugins/hermes-multiplayer/status, with the event path down (TC-11.7)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC, store._notify)
        store.DB_PATH_OVERRIDE = Path(self.tmp.name) / "herd.db"
        store.SETTINGS_OVERRIDE = {"display_name": "tyler", "__secrets__": {}}
        store.AUTO_SYNC = False
        store._status = None
        store._notify = lambda event, payload: None  # sockets no-op on OAuth remotes (TC-2.5)

    def tearDown(self):
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC, store._notify = self._saved
        store._status = None
        self.tmp.cleanup()

    @unittest.skipIf(TestClient is None, "fastapi/httpx not installed")
    def test_route_serves_the_phrase_and_nothing_when_unset(self):
        import herd.dashboard.plugin_api as api

        app = FastAPI()
        app.include_router(api.router, prefix="/api/plugins/hermes-multiplayer")
        client = TestClient(app)
        url = "/api/plugins/hermes-multiplayer/status"

        self.assertIsNone(client.get(url).json()["agent_status"])          # never set -> nothing
        self.assertEqual(json.loads(tools.herd_set_status({"status": "reviewing"}))["ok"], True)
        got = client.get(url).json()["agent_status"]                        # poll -> the phrase
        self.assertEqual(got["phrase"], "reviewing")
        self.assertEqual(got["agent"], "tyler")

        at = store._status["at"]
        store._status = {**store._status, "at": at - store.STATUS_TTL_S - 1}
        self.assertIsNone(client.get(url).json()["agent_status"])           # past the bound -> nothing

    # S3 hardening (t_1f78eb04): the card's regression - a malformed record must answer 200 with
    # agent_status: null, not bubble KeyError/ValueError out of the route as a 500.
    @unittest.skipIf(TestClient is None, "fastapi/httpx not installed")
    def test_route_fails_closed_on_malformed_record(self):
        import herd.dashboard.plugin_api as api

        app = FastAPI()
        app.include_router(api.router, prefix="/api/plugins/hermes-multiplayer")
        client = TestClient(app)
        url = "/api/plugins/hermes-multiplayer/status"

        for record in ({"phrase": "idle"}, {"phrase": "idle", "at": "oops"}):
            with self.subTest(record=record):
                store._status = record
                res = client.get(url)
                self.assertEqual(res.status_code, 200)
                self.assertIsNone(res.json()["agent_status"])


class PaneRenderTest(unittest.TestCase):
    """Runs the pane's real WorkLine()/MessageRow() in node (TC-11.1/11.2/11.6)."""

    @unittest.skipIf(shutil.which("node") is None, "node is not installed")
    def test_pane_render_probe(self):
        probe = ROOT / "tests" / "s15_pane_render_probe.mjs"
        done = subprocess.run(["node", str(probe), str(ROOT / "desktop" / "plugin.js")],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("PROBE OK", done.stdout)


if __name__ == "__main__":
    unittest.main()
