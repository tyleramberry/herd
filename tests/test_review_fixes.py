"""Regression tests for the adversarial review of the stack: pairing race, recorded wake reasons, error mapping,
one-line peer topics, and pruning of expired peer status."""
import http.client
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_pairing import PairingTest, RESPONDER_SECRET  # noqa: E402
from test_wake_default import _Base, peer_msg  # noqa: E402

_, store, _tools = _pkg.load()


class PairingRaceTest(PairingTest):
    def responder_redeem(self, code):
        with self.responder:
            return store.handle_pair_request({"code": code, "nonce": "f" * 32,
                                              "requester": {"gateway_id": "tyler-gw"}})

    def test_two_requests_that_both_read_the_code_unspent_get_one_secret(self):
        code = store._normalize_code(self.mint()["code"])
        real = store.hmac.compare_digest
        inner = {}

        def racing(a, b):
            # The first comparison lets a second request complete before this one spends the code.
            if not inner.get("started"):
                inner["started"] = True
                inner["out"] = self.responder_redeem(code)
            return real(a, b)

        with mock.patch.object(store.hmac, "compare_digest", racing):
            with self.assertRaises(store.HerdError) as ctx:
                self.responder_redeem(code)
        self.assertEqual(inner["out"]["herd_secret"], RESPONDER_SECRET)
        self.assertEqual(ctx.exception.status, 403)


class RecordedReasonsTest(_Base):
    def test_an_agent_mention_records_why_it_did_not_wake(self):
        store.set_mention_target("ses_x")
        store.ingest(peer_msg("@tyler from another agent", "ag1", author_type="agent"))
        self.assertEqual(self.woken, [])
        self.assertEqual(self.skip_of("ag1"), "agent_author")

    def test_a_history_mention_records_why_it_did_not_wake(self):
        store.set_mention_target("ses_x")
        store.ingest(peer_msg("@tyler old news", "hist1"), suppress_wakes=True)
        self.assertEqual(self.woken, [])
        self.assertEqual(self.skip_of("hist1"), "history")


class ErrorMappingTest(PairingTest):
    def test_a_protocol_level_failure_is_a_502_not_a_stack_trace(self):
        store.PAIR_TRANSPORT = lambda url, body: (_ for _ in ()).throw(http.client.BadStatusLine("junk"))
        with self.requester:
            with self.assertRaises(store.HerdError) as ctx:
                store.redeem_pairing("https://brooklyn-mac.tailnet.ts.net:8642", "ABCDE-FGHJK")
        self.assertEqual(ctx.exception.status, 502)


class PeerTopicTest(_Base):
    def test_a_peer_topic_is_stored_as_one_line(self):
        store.ingest({"from": {"gateway_id": "riley-gw", "display_name": "riley"}, "channels": [
            {"id": "lines-room", "name": "lines-room", "topic": "first\nsecond\tthird", "is_dm": False,
             "members": [], "created_at": "2026-01-01T00:00:00Z"}], "messages": []})
        self.assertEqual(store.get_channel("lines-room")["topic"], "first second third")


class PeerStatusPruneTest(unittest.TestCase):
    def test_expired_peer_entries_are_dropped_on_the_next_write(self):
        store._peer_status.clear()
        store._peer_status["gw-old"] = {"phrase": "idle", "agent": "", "name": "old",
                                        "at": time.time() - store.STATUS_TTL_S - 5}
        store._record_peer_status({"gateway_id": "gw-new", "display_name": "new"}, {"phrase": "done"})
        self.assertEqual(sorted(store._peer_status), ["gw-new"])
        store._peer_status.clear()


if __name__ == "__main__":
    unittest.main()
