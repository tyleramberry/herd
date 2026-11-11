"""Track 0: @mention wake is on by default, and a mention that does not reach the agent says why.

Covers the three silent blockers the night-build brief named: default-off setting, a missing target
(now a recorded skip, surfaced in the pane and multiplayer_read_channel), and the injection gate (now reported
as ``injection_not_allowed`` before any call is made).
"""
import json
import os
import sys
import tempfile
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


def peer_msg(content, mid, author_type="human", gw="other-gw", channel="general", thread=None):
    row = {"id": mid, "channel_id": channel, "author_type": author_type, "author_name": "Brooklyn",
           "gateway_id": gw, "gateway_name": "Brooklyn", "content": content, "created_at": "2026-11-05T00:00:00Z"}
    if thread:
        row["thread_parent_id"] = thread
    return {"from": {"gateway_id": gw, "display_name": "Brooklyn"}, "channels": [], "messages": [row]}


class _Base(unittest.TestCase):
    settings = {"display_name": "Tyler"}  # no mention_wake key: exercises the default

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        store.AUTO_SYNC = False
        store.DB_PATH_OVERRIDE = Path(self.tmp.name) / "w.db"
        store.SETTINGS_OVERRIDE = dict(self.settings)
        self.woken = []
        store.WAKE_HANDLER = lambda key, text: self.woken.append((key, text)) or True
        store._wake_times.clear()
        store._wake_blocked.update({"reason": None, "at": None})

    def tearDown(self):
        store.WAKE_HANDLER = None
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        store._wake_blocked.update({"reason": None, "at": None})
        self.tmp.cleanup()

    def skip_of(self, mid):
        return store.wake_skips_for([mid]).get(mid)


class DefaultOnTest(_Base):
    def test_wake_is_on_when_the_setting_is_absent(self):
        self.assertTrue(store.wake_enabled())

    def test_wake_is_on_for_blank_or_null_values(self):
        for value in (None, ""):
            store.SETTINGS_OVERRIDE = {"display_name": "Tyler", "mention_wake": value}
            self.assertTrue(store.wake_enabled(), value)

    def test_explicit_off_still_turns_it_off(self):
        for value in (False, "false", "off", "no", "0"):
            store.SETTINGS_OVERRIDE = {"display_name": "Tyler", "mention_wake": value}
            self.assertFalse(store.wake_enabled(), value)

    def test_default_on_wakes_the_agent_with_a_target(self):
        store.set_mention_target("ses_default", "this chat")
        store.ingest(peer_msg("@tyler hello", "d1"))
        self.assertEqual([k for k, _ in self.woken], ["ses_default"])
        self.assertIsNone(self.skip_of("d1"))

    def test_manifest_default_is_on(self):
        text = (_pkg.ROOT / "plugin.yaml").read_text(encoding="utf-8")
        start = text.index("  mention_wake:")
        self.assertIn("default: true", text[start:start + 120])


class SkipRecordingTest(_Base):
    def test_no_target_is_recorded_not_dropped(self):
        store.ingest(peer_msg("@tyler are you there", "n1"))
        self.assertEqual(self.woken, [])
        self.assertEqual(self.skip_of("n1"), "no_target")
        msg = next(m for m in store.list_messages("general") if m["id"] == "n1")
        self.assertIn("/multiplayer-listen", msg["wake_note"])

    def test_wake_off_is_recorded(self):
        store.SETTINGS_OVERRIDE = {"display_name": "Tyler", "mention_wake": False}
        store.set_mention_target("ses_x")
        store.ingest(peer_msg("@tyler hi", "o1"))
        self.assertEqual(self.skip_of("o1"), "wake_off")

    def test_injection_not_allowed_is_checked_before_calling_the_host(self):
        store.set_mention_target("ses_x")
        with mock.patch.object(store, "gateway_injection_allowed", return_value=False):
            store.ingest(peer_msg("@tyler hi", "i1"))
        self.assertEqual(self.woken, [])
        self.assertEqual(self.skip_of("i1"), "injection_not_allowed")

    def test_host_refusal_is_recorded_and_clears_on_the_next_success(self):
        store.set_mention_target("ses_x")
        store.WAKE_HANDLER = lambda k, t: False
        store.ingest(peer_msg("@tyler hi", "h1"))
        self.assertEqual(self.skip_of("h1"), "host_refused")
        self.assertEqual(store.wake_block()["blocked_reason"], "host_refused")
        store.WAKE_HANDLER = lambda k, t: self.woken.append((k, t)) or True
        store.ingest(peer_msg("@tyler again", "h2"))
        self.assertIsNone(self.skip_of("h2"))
        self.assertEqual(store.wake_block()["blocked_reason"], "")

    def test_handler_exception_is_recorded_as_wake_error(self):
        store.set_mention_target("ses_x")

        def boom(k, t):
            raise RuntimeError("x")
        store.WAKE_HANDLER = boom
        self.assertEqual(store.ingest(peer_msg("@tyler hi", "e1")), 1)
        self.assertEqual(self.skip_of("e1"), "wake_error")

    def test_rate_limited_mentions_are_recorded_not_lost(self):
        store.set_mention_target("ses_x")
        total = store.WAKE_MAX_PER_MINUTE + 3
        for i in range(total):
            store.ingest(peer_msg("@tyler go", f"r{i}"))
        self.assertEqual(len(self.woken), store.WAKE_MAX_PER_MINUTE)
        rate_limited = [i for i in range(total) if self.skip_of(f"r{i}") == "rate_limited"]
        self.assertEqual(len(rate_limited), 3)

    def test_a_retry_overwrites_the_reason_for_one_message(self):
        store._record_wake_skip("x1", "wake_off")
        store._record_wake_skip("x1", "no_target")
        self.assertEqual(store.wake_skips_for(["x1"]), {"x1": "no_target"})

    def test_wake_skips_for_empty_input_costs_no_query(self):
        self.assertEqual(store.wake_skips_for([]), {})


class WakeBlockTest(_Base):
    def test_banner_state_when_the_agent_answers(self):
        store.set_mention_target("ses_ok", "this chat")
        block = store.wake_block()
        self.assertEqual(block["blocked_reason"], "")
        self.assertTrue(block["enabled"] and block["target_set"])
        self.assertEqual(block["target_label"], "this chat")

    def test_banner_names_the_missing_target(self):
        block = store.wake_block()
        self.assertEqual(block["blocked_reason"], "no_target")
        self.assertEqual(block["target_label"], "")

    def test_injection_banner_carries_the_copyable_config_line(self):
        store.set_mention_target("ses_x")
        with mock.patch.object(store, "gateway_injection_allowed", return_value=False):
            block = store.wake_block()
        self.assertEqual(block["blocked_reason"], "injection_not_allowed")
        self.assertEqual(block["config_line"], "allow_gateway_injection: true")

    def test_status_carries_the_wake_block(self):
        store.set_mention_target("ses_x")
        status = store.status()
        self.assertEqual(status["wake"]["target_label"], "your active chat")
        self.assertIn("mention_wake", status)

    def test_label_is_cleared_with_the_target(self):
        store.set_mention_target("ses_x", "Ops room")
        self.assertEqual(store.mention_label(), "Ops room")
        store.set_mention_target("")
        self.assertEqual(store.mention_target(), "")
        self.assertEqual(store.mention_label(), "your active chat")

    def test_label_is_one_plain_line(self):
        store.set_mention_target("ses_x", "line\nbreak \"quoted\"")
        self.assertEqual(store.mention_label(), 'line break "quoted"')

    def test_wake_block_never_raises(self):
        with mock.patch.object(store, "wake_enabled", side_effect=RuntimeError("boom")):
            self.assertEqual(store.wake_block()["blocked_reason"], "wake_error")


class ReadChannelSurfacesTheReasonTest(_Base):
    def test_read_channel_carries_mention_not_delivered(self):
        store.ingest(peer_msg("@tyler help", "rc1"))
        read = json.loads(tools.multiplayer_read_channel({"channel": "general"}))
        msg = next(m for m in read["messages"] if m["id"] == "rc1")
        self.assertIn("/multiplayer-listen", msg["mention_not_delivered"])

    def test_a_delivered_mention_has_no_note(self):
        store.set_mention_target("ses_x")
        store.ingest(peer_msg("@tyler help", "rc2"))
        read = json.loads(tools.multiplayer_read_channel({"channel": "general"}))
        msg = next(m for m in read["messages"] if m["id"] == "rc2")
        self.assertNotIn("mention_not_delivered", msg)

    def test_thread_replies_carry_the_note_too(self):
        store.ingest(peer_msg("root", "t-root"))
        store.ingest(peer_msg("@tyler reply", "t-reply", thread="t-root"))
        thread = store.list_thread("t-root")
        self.assertEqual(thread["parent"]["wake_note"], "")
        self.assertEqual([r["id"] for r in thread["replies"]], ["t-reply"])
        self.assertIn("/multiplayer-listen", thread["replies"][0]["wake_note"])


@unittest.skipUnless(TestClient is not None, "fastapi/httpx not installed")
class WakeTargetRouteTest(_Base):
    def setUp(self):
        super().setUp()
        spec_path = _pkg.ROOT / "dashboard" / "plugin_api.py"
        import importlib.util

        spec = importlib.util.spec_from_file_location("multiplayer_api_under_test", spec_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = FastAPI()
        app.include_router(module.router, prefix="/api/plugins/hermes-multiplayer")
        self.client = TestClient(app)

    def test_pane_sets_the_target_from_its_session_key(self):
        res = self.client.post("/api/plugins/hermes-multiplayer/wake-target",
                               json={"session_key": "ses_pane", "label": "this chat"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(store.mention_target(), "ses_pane")
        self.assertEqual(res.json()["wake"]["target_label"], "this chat")

    def test_empty_key_clears_the_target_like_listen_off(self):
        store.set_mention_target("ses_pane")
        res = self.client.post("/api/plugins/hermes-multiplayer/wake-target", json={"session_key": ""})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(store.mention_target(), "")

    def test_a_control_character_in_the_key_is_refused(self):
        res = self.client.post("/api/plugins/hermes-multiplayer/wake-target", json={"session_key": "ses\nx"})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(store.mention_target(), "")


if __name__ == "__main__":
    unittest.main()
