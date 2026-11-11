"""Track 5: the one-time pairing code (mint, exchange, single use, expiry, lockout, binding, downgrade refusal).

The responder (a gateway holding a Hermes Multiplayer secret) and the requester (a teammate typing the code) are two real
gateways. The exchange goes through the JSON round trip, the way the wire does it.
"""
import io
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_store import Gateway  # noqa: E402

_, store, _tools = _pkg.load()

RESPONDER_SECRET = "-".join(["brooklyn", "herd", "key", "0123456789abcdef"])  # assembled: not a literal credential
URL = "https://brooklyn-mac.tailnet.ts.net:8642"


class PairingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.responder = Gateway(root, "brooklyn")
        self.responder.settings["__secrets__"]["HERD_SECRET"] = RESPONDER_SECRET
        self.requester = Gateway(root, "tyler")
        self.calls = []
        self._saved = (store.PAIR_TRANSPORT, store.AUTO_SYNC, store.TRANSPORT)
        store.AUTO_SYNC = False
        store.TRANSPORT = None

        def transport(url, body):
            # Behaves like the wire: a refusal arrives as an HTTP error with a JSON body, which the requester maps.
            self.calls.append((url, body))
            try:
                with self.responder:
                    return json.loads(json.dumps(store.handle_pair_request(json.loads(json.dumps(body)))))
            except store.HerdError as exc:
                raise urllib.error.HTTPError(url, exc.status, exc.message, {},
                                             io.BytesIO(json.dumps({"error": exc.message}).encode("utf-8")))
        store.PAIR_TRANSPORT = transport

    def tearDown(self):
        store.PAIR_TRANSPORT, store.AUTO_SYNC, store.TRANSPORT = self._saved
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        self.tmp.cleanup()

    def mint(self):
        with self.responder:
            return store.mint_pairing_code()

    def redeem(self, code, url=URL):
        with self.requester:
            return store.redeem_pairing(url, code)

    def responder_db(self):
        return sqlite3.connect(str(self.responder.db))


class HappyPathTest(PairingTest):
    def test_a_code_gets_the_teammate_the_secret_once(self):
        code = self.mint()["code"]
        self.assertEqual(len(code.replace("-", "")), store.PAIR_CODE_LEN)
        result = self.redeem(code)
        self.assertEqual(result["herd_secret"], RESPONDER_SECRET)
        self.assertEqual(result["name"], "brooklyn")
        self.assertEqual(result["url"], URL)
        self.assertTrue(result["gateway_id"])

    def test_the_code_is_typed_loosely(self):
        code = self.mint()["code"]
        sloppy = code.lower().replace("-", " ")
        self.assertEqual(self.redeem(sloppy)["herd_secret"], RESPONDER_SECRET)

    def test_the_code_itself_is_not_stored(self):
        code = self.mint()["code"]
        with self.responder_db() as conn:
            stored = [r[0] for r in conn.execute("SELECT digest FROM pairing_codes")]
            values = [r[0] for r in conn.execute("SELECT value FROM meta")]
        self.assertEqual(len(stored), 1)
        self.assertNotIn(code.replace("-", ""), stored)
        self.assertNotIn(code.replace("-", ""), values)

    def test_the_exchange_saves_nothing_on_the_requester(self):
        code = self.mint()["code"]
        self.redeem(code)
        with self.requester:
            self.assertEqual(store.configured_peers(), [])

    def test_mint_needs_a_herd_secret(self):
        self.responder.settings["__secrets__"].pop("HERD_SECRET")
        with self.responder:
            with self.assertRaises(store.HerdError) as ctx:
                store.mint_pairing_code()
        self.assertEqual(ctx.exception.status, 409)


class SingleUseAndExpiryTest(PairingTest):
    def test_a_replayed_code_is_refused(self):
        code = self.mint()["code"]
        self.redeem(code)
        with self.assertRaises(store.HerdError) as ctx:
            self.redeem(code)
        self.assertEqual(ctx.exception.status, 502)
        self.assertIn("refused that code", ctx.exception.message)
        self.assertIn("already used", ctx.exception.message)

    def test_an_expired_code_is_refused(self):
        code = self.mint()["code"]
        real = store.time.time()
        fake = types.SimpleNamespace(time=lambda: real + store.PAIR_TTL_S + 1)
        with mock.patch.object(store, "time", fake):
            with self.assertRaises(store.HerdError):
                self.redeem(code)

    def test_a_code_is_good_until_its_ttl(self):
        code = self.mint()["code"]
        real = store.time.time()
        fake = types.SimpleNamespace(time=lambda: real + store.PAIR_TTL_S - 30)
        with mock.patch.object(store, "time", fake):
            self.assertEqual(self.redeem(code)["herd_secret"], RESPONDER_SECRET)

    def test_a_new_code_replaces_the_live_one(self):
        first = self.mint()["code"]
        second = self.mint()["code"]
        with self.assertRaises(store.HerdError):
            self.redeem(first)
        self.assertEqual(self.redeem(second)["herd_secret"], RESPONDER_SECRET)

    def test_a_setup_gap_does_not_burn_the_code(self):
        code = self.mint()["code"]
        self.responder.settings["__secrets__"].pop("HERD_SECRET")
        with self.assertRaises(store.HerdError):
            self.redeem(code)
        self.responder.settings["__secrets__"]["HERD_SECRET"] = RESPONDER_SECRET
        self.assertEqual(self.redeem(code)["herd_secret"], RESPONDER_SECRET)


class WrongCodeAndLockoutTest(PairingTest):
    def test_a_wrong_code_is_refused(self):
        self.mint()
        with self.assertRaises(store.HerdError):
            self.redeem("ZZZZZ-ZZZZZ")

    def test_one_wrong_try_does_not_burn_the_real_code(self):
        code = self.mint()["code"]
        with self.assertRaises(store.HerdError):
            self.redeem("AAAAA-AAAAA")
        self.assertEqual(self.redeem(code)["herd_secret"], RESPONDER_SECRET)

    def test_the_failure_count_is_kept(self):
        self.mint()
        for _ in range(3):
            with self.assertRaises(store.HerdError):
                self.redeem("AAAAA-AAAAA")
        with self.responder_db() as conn:
            value = conn.execute("SELECT value FROM meta WHERE key='pair_failures'").fetchone()[0]
        self.assertEqual(value, "3")

    def test_five_wrong_tries_pause_pairing_and_kill_the_code(self):
        code = self.mint()["code"]
        for _ in range(store.PAIR_MAX_FAILURES):
            with self.assertRaises(store.HerdError):
                self.redeem("AAAAA-AAAAA")
        with self.assertRaises(store.HerdError) as ctx:
            self.redeem(code)  # the right code is refused during the lockout
        self.assertIn("Too many wrong codes", ctx.exception.message)
        real = store.time.time()
        fake = types.SimpleNamespace(time=lambda: real + store.PAIR_LOCKOUT_S + 1)
        with mock.patch.object(store, "time", fake):
            with self.assertRaises(store.HerdError):
                self.redeem(code)  # the lockout also killed that code
            self.assertEqual(self.redeem(self.mint()["code"])["herd_secret"], RESPONDER_SECRET)

    def test_the_lockout_message_is_only_seen_by_the_responder_side(self):
        self.mint()
        for _ in range(store.PAIR_MAX_FAILURES):
            with self.responder:
                with self.assertRaises(store.HerdError):
                    store.handle_pair_request({"code": "AAAAAAAAAA", "nonce": "a" * 32,
                                               "requester": {"gateway_id": "tyler-gw"}})
        with self.responder:
            with self.assertRaises(store.HerdError) as ctx:
                store.handle_pair_request({"code": "AAAAAAAAAA", "nonce": "a" * 32,
                                           "requester": {"gateway_id": "tyler-gw"}})
        self.assertEqual(ctx.exception.status, 429)


class BindingTest(PairingTest):
    def test_a_responder_without_the_code_cannot_fake_a_reply(self):
        code = self.mint()["code"]
        good = self.responder_reply(code)
        good["herd_secret"] = "an-attacker-secret-0123456789abcdef"  # the mac was made for the real secret
        store.PAIR_TRANSPORT = lambda url, body: good
        with self.assertRaises(store.HerdError) as ctx:
            self.redeem(code)
        self.assertEqual(ctx.exception.status, 502)
        self.assertIn("didn't prove the code", ctx.exception.message)

    def test_a_reply_made_for_another_request_is_refused(self):
        code = self.mint()["code"]
        reply = self.responder_reply(code, nonce="b" * 32)  # a reply to some other nonce
        store.PAIR_TRANSPORT = lambda url, body: dict(reply, mac=reply["mac"])
        with self.assertRaises(store.HerdError) as ctx:
            self.redeem(code)
        self.assertIn("didn't prove the code", ctx.exception.message)

    def test_a_reply_signed_with_the_wrong_code_is_refused(self):
        code = self.mint()["code"]
        other = "ABCDEFGHJK"
        forged = self.responder_reply(other)
        store.PAIR_TRANSPORT = lambda url, body: forged
        with self.assertRaises(store.HerdError):
            self.redeem(code)

    def responder_reply(self, code, nonce=None):
        """What the responder would send for a request with this code and nonce (built the way it builds it)."""
        with self.responder:
            norm = store._normalize_code(code)
            digest_ok = store._pair_digest(norm)
            with store.connect() as conn:
                conn.execute("UPDATE pairing_codes SET digest = ?, used_at = ''", (digest_ok,))
            reply = store.handle_pair_request({"code": norm, "nonce": nonce or "c" * 32,
                                               "requester": {"gateway_id": "tyler-gw"}})
        return reply


class DowngradeTest(PairingTest):
    def test_a_reply_without_a_proof_is_refused(self):
        code = self.mint()["code"]
        reply = self.responder_reply_plain(code)
        reply.pop("mac")
        store.PAIR_TRANSPORT = lambda url, body: reply
        with self.assertRaises(store.HerdError) as ctx:
            self.redeem(code)
        self.assertEqual(ctx.exception.status, 502)

    def test_a_reply_that_is_not_pairing_shaped_is_refused(self):
        code = self.mint()["code"]
        for bad in ({}, {"herd_secret": "x"}, {"pair": "herd-pair-v0", "mac": "x", "herd_secret": "y",
                                               "from": {"gateway_id": "brooklyn-gw"}}):
            store.PAIR_TRANSPORT = lambda url, body, bad=bad: bad
            with self.assertRaises(store.HerdError):
                self.redeem(code)

    def test_cleartext_to_another_machine_is_refused_before_any_request(self):
        code = self.mint()["code"]
        with self.assertRaises(store.HerdError) as ctx:
            self.redeem(code, url="http://brooklyn-mac.local:8642")
        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(self.calls, [])  # the code never left this machine

    def test_loopback_cleartext_is_allowed_as_the_peer_policy_allows(self):
        code = self.mint()["code"]
        self.assertEqual(self.redeem(code, url="http://127.0.0.1:8642")["herd_secret"], RESPONDER_SECRET)
        self.assertEqual(self.calls[0][0], "http://127.0.0.1:8642")

    def test_a_network_error_is_a_plain_message(self):
        store.PAIR_TRANSPORT = lambda url, body: (_ for _ in ()).throw(urllib.error.URLError("nope"))
        with self.assertRaises(store.HerdError) as ctx:
            self.redeem("ABCDE-FGHJK")
        self.assertIn("Couldn't reach that gateway", ctx.exception.message)

    def responder_reply_plain(self, code):
        with self.responder:
            norm = store._normalize_code(code)
            with store.connect() as conn:
                conn.execute("UPDATE pairing_codes SET digest = ?, used_at = ''", (store._pair_digest(norm),))
            return store.handle_pair_request({"code": norm, "nonce": "d" * 32, "requester": {"gateway_id": "tyler-gw"}})


class RequestShapeTest(PairingTest):
    def test_self_pairing_is_refused(self):
        code = self.mint()["code"]
        with self.responder:
            local = store.identity()["gateway_id"]
            with self.assertRaises(store.HerdError) as ctx:
                store.handle_pair_request({"code": code, "nonce": "e" * 32, "requester": {"gateway_id": local}})
        self.assertEqual(ctx.exception.status, 422)

    def test_malformed_requests_are_422(self):
        self.mint()
        bad_bodies = [None, "x", {"code": "ABCDEFGHJK"}, {"code": "x", "nonce": "short", "requester": {"gateway_id": "t"}},
                      {"code": "x", "nonce": "f" * 32, "requester": {"gateway_id": "BAD ID"}}]
        for body in bad_bodies:
            with self.responder:
                with self.assertRaises(store.HerdError) as ctx:
                    store.handle_pair_request(body)
            self.assertEqual(ctx.exception.status, 422, repr(body))

    def test_a_wrong_length_code_is_refused_by_the_requester_too(self):
        with self.assertRaises(store.HerdError) as ctx:
            self.redeem("ABC")
        self.assertEqual(ctx.exception.status, 422)

    def test_the_wire_path_is_stable(self):
        self.assertEqual(store.PAIR_PATH, "/herd/v1/pair")

    def test_a_code_has_no_look_alike_letters(self):
        for _ in range(20):
            code = self.mint()["code"].replace("-", "")
            self.assertFalse(set(code) & set("ILOU"), code)


if __name__ == "__main__":
    unittest.main()
