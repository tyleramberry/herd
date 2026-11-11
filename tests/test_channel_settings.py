"""Track 3: channel topic (set, sync, last writer wins) and the honest rename/private answer.

The topic syncs to the mesh, so it is tested across two real gateways. Renaming is deliberately absent: a public
channel's name is its id, and peers key their rows on it, so a rename would orphan the channel's history.
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # noqa: BLE001
    FastAPI = TestClient = None

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_presence import TwoGateways  # noqa: E402

_, store, _tools = _pkg.load()


class TopicLocalTest(TwoGateways):
    prime = False

    def test_a_topic_is_set_and_shown(self):
        with self.A:
            store.set_topic("general", "Ship the demo on Friday")
            self.assertEqual(store.get_channel("general")["topic"], "Ship the demo on Friday")

    def test_a_topic_is_one_line_and_capped(self):
        with self.A:
            store.set_topic("general", "line one\n\tline   two " + "x" * 400)
            topic = store.get_channel("general")["topic"]
        self.assertNotIn("\n", topic)
        self.assertNotIn("\t", topic)
        self.assertLessEqual(len(topic), store.TOPIC_MAX_CHARS)
        self.assertTrue(topic.startswith("line one line two"))

    def test_an_empty_topic_clears_it(self):
        with self.A:
            store.set_topic("general", "something")
            store.set_topic("general", "   ")
            self.assertEqual(store.get_channel("general")["topic"], "")

    def test_a_direct_message_has_no_topic(self):
        with self.A:
            with store.connect() as conn:
                conn.execute("INSERT INTO channels(id, name, topic, is_dm, members, created_at) "
                             "VALUES ('dm:a+b', 'A & B', '', 1, '[]', '2026-11-01T00:00:00Z')")
            with self.assertRaises(store.HerdError) as ctx:
                store.set_topic("dm:a+b", "nope")
        self.assertEqual(ctx.exception.status, 422)

    def test_an_unknown_channel_is_a_404(self):
        with self.A:
            with self.assertRaises(store.HerdError) as ctx:
                store.set_topic("nowhere", "x")
        self.assertEqual(ctx.exception.status, 404)

    def test_create_channel_with_a_topic_keeps_it_one_line(self):
        with self.A:
            store.create_channel("ops", "first\nsecond")
            self.assertEqual(store.get_channel("ops")["topic"], "first second")


class TopicAcrossPeersTest(TwoGateways):
    prime = True

    def test_a_topic_reaches_the_teammate(self):
        with self.A:
            store.set_topic("general", "release on friday")
        self.sync()
        with self.B:
            self.assertEqual(store.get_channel("general")["topic"], "release on friday")

    def test_the_most_recent_topic_wins_in_either_direction(self):
        with self.A:
            store.set_topic("general", "from tyler")
        self.sync()
        time.sleep(0.01)
        with self.B:
            store.set_topic("general", "from riley, later")
        self.sync()
        with self.A:
            self.assertEqual(store.get_channel("general")["topic"], "from riley, later")
        with self.B:
            self.assertEqual(store.get_channel("general")["topic"], "from riley, later")

    def test_a_stale_topic_does_not_overwrite_a_newer_one(self):
        with self.A:
            store.set_topic("general", "current")
        self.sync()
        with self.A:
            store.ingest({"from": {"gateway_id": "riley-gw", "display_name": "riley"},
                          "channels": [{"id": "general", "name": "general", "topic": "old news", "is_dm": False,
                                        "members": [], "created_at": "2026-01-01T00:00:00Z",
                                        "topic_at": "2026-01-02T00:00:00Z"}],
                          "messages": []})
            self.assertEqual(store.get_channel("general")["topic"], "current")

    def test_a_replayed_topic_is_harmless(self):
        with self.A:
            store.set_topic("general", "stable")
        self.sync()
        with self.A:
            with store.connect() as conn:
                conn.execute("UPDATE peer_state SET pull_seq = 0, pull_rseq = 0")
        self.sync()
        with self.B:
            self.assertEqual(store.get_channel("general")["topic"], "stable")

    def test_a_malformed_topic_stamp_is_replaced_not_trusted(self):
        with self.A:
            store.ingest({"from": {"gateway_id": "riley-gw", "display_name": "riley"},
                          "channels": [{"id": "fresh-room", "name": "fresh-room", "topic": "hi", "is_dm": False,
                                        "members": [], "created_at": "2026-01-01T00:00:00Z",
                                        "topic_at": "not a time"}],
                          "messages": []})
            self.assertEqual(store.get_channel("fresh-room")["topic"], "hi")


@unittest.skipUnless(TestClient is not None, "fastapi/httpx not installed")
class TopicRouteTest(TwoGateways):
    prime = False

    def setUp(self):
        super().setUp()
        import importlib.util

        spec = importlib.util.spec_from_file_location("herd_api_topic_test", _pkg.ROOT / "dashboard" / "plugin_api.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = FastAPI()
        app.include_router(module.router, prefix="/api/plugins/hermes-multiplayer")
        self.client = TestClient(app)

    def test_post_topic_sets_it(self):
        with self.A:
            res = self.client.post("/api/plugins/hermes-multiplayer/channels/general/topic", json={"topic": "via the pane"})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(store.get_channel("general")["topic"], "via the pane")

    def test_post_topic_on_a_dm_is_refused(self):
        with self.A:
            with store.connect() as conn:
                conn.execute("INSERT INTO channels(id, name, topic, is_dm, members, created_at) "
                             "VALUES ('dm:x+y', 'X & Y', '', 1, '[]', '2026-11-01T00:00:00Z')")
            res = self.client.post("/api/plugins/hermes-multiplayer/channels/dm:x+y/topic", json={"topic": "no"})
            self.assertEqual(res.status_code, 422)

    def test_there_is_no_rename_route(self):
        with self.A:
            res = self.client.patch("/api/plugins/hermes-multiplayer/channels/general", json={"name": "lobby"})
            self.assertIn(res.status_code, (404, 405))
            self.assertEqual(store.get_channel("general")["name"], "general")


if __name__ == "__main__":
    unittest.main()
