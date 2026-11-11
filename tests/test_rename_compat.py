"""The Herd -> Hermes Multiplayer rename keeps installs set up before it working.

Old secret slots (HERD_*) are read when the new ones are empty, the old data file (herd.db) is adopted once, the old
peer routes (/herd/v1/*) are still served and retried on a 404, and pairing works with a build that speaks the old
exchange in either direction.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_pairing import PairingTest, RESPONDER_SECRET, URL  # noqa: E402
from test_peer_secret_scope import HAVE_AIOHTTP, B_SECRET, Routes, http  # noqa: E402

_, store, _tools = _pkg.load()


class LegacySecrets(unittest.TestCase):
    def tearDown(self):
        store.SETTINGS_OVERRIDE = None

    def test_empty_new_slot_reads_the_old_name(self):
        store.SETTINGS_OVERRIDE = {"__secrets__": {"HERD_SECRET": "old-local", "HERD_PEER_KEY_2": "old-peer-2",
                                                   "HERD_RELAY_KEY": "old-room"}}
        self.assertEqual(store._secret("HERMES_MULTIPLAYER_SECRET"), "old-local")
        self.assertEqual(store._secret("HERMES_MULTIPLAYER_PEER_KEY_2"), "old-peer-2")
        self.assertEqual(store._secret("HERMES_MULTIPLAYER_RELAY_KEY"), "old-room")
        self.assertEqual(store._secret("HERMES_MULTIPLAYER_PEER_KEY_3"), "")

    def test_new_slot_wins(self):
        store.SETTINGS_OVERRIDE = {"__secrets__": {"HERD_SECRET": "old", "HERMES_MULTIPLAYER_SECRET": "new"}}
        self.assertEqual(store.multiplayer_secret(), "new")

    def test_a_slot_never_reads_another_slots_old_name(self):
        store.SETTINGS_OVERRIDE = {"__secrets__": {"HERD_PEER_KEY": "teammate-1"}}
        self.assertEqual(store._secret("HERMES_MULTIPLAYER_PEER_KEY_2"), "")


class LegacyDataFile(unittest.TestCase):
    def test_old_file_and_sidecars_are_adopted_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name, text in (("herd.db", "main"), ("herd.db-wal", "wal"), ("herd.db-shm", "shm")):
                (folder / name).write_text(text)
            target = folder / "hermes-multiplayer.db"
            store._adopt_legacy_db(target)
            self.assertEqual(target.read_text(), "main")
            self.assertEqual((folder / "hermes-multiplayer.db-wal").read_text(), "wal")
            self.assertEqual((folder / "hermes-multiplayer.db-shm").read_text(), "shm")
            self.assertFalse((folder / "herd.db").exists())

    def test_an_existing_new_file_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "herd.db").write_text("old")
            (folder / "hermes-multiplayer.db").write_text("new")
            store._adopt_legacy_db(folder / "hermes-multiplayer.db")
            self.assertEqual((folder / "hermes-multiplayer.db").read_text(), "new")
            self.assertTrue((folder / "herd.db").exists())


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class LegacyPathRetry(unittest.TestCase):
    def test_a_404_on_the_new_path_retries_the_old_one(self):
        seen = []

        def opener(req, timeout):
            seen.append(req.full_url)
            if "/hermes-multiplayer/v1/" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 404, "nope", {}, io.BytesIO(b"{}"))
            return _Resp(b'{"ok": true}')

        with mock.patch.object(store, "_OPEN_PEER", opener):
            with store._open_peer_route("https://peer", store.PEER_SYNC_PATH, 5, data=b"{}", method="POST") as resp:
                self.assertEqual(json.loads(resp.read()), {"ok": True})
        self.assertEqual(seen, ["https://peer/hermes-multiplayer/v1/sync", "https://peer/herd/v1/sync"])

    def test_other_errors_are_not_retried(self):
        seen = []

        def opener(req, timeout):
            seen.append(req.full_url)
            raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b"{}"))

        with mock.patch.object(store, "_OPEN_PEER", opener):
            with self.assertRaises(urllib.error.HTTPError):
                store._open_peer_route("https://peer", store.PEER_SYNC_PATH, 5, data=b"{}", method="POST")
        self.assertEqual(len(seen), 1)


class LegacyPairing(PairingTest):
    def test_an_old_requester_gets_the_old_reply(self):
        code = store._normalize_code(self.mint()["code"])
        with self.responder:
            reply = store.handle_pair_request({"code": code, "nonce": "a" * 32, "requester": {"gateway_id": "tyler-gw"}})
        self.assertEqual(reply["pair"], "herd-pair-v1")
        self.assertEqual(reply["herd_secret"], RESPONDER_SECRET)
        self.assertNotIn("multiplayer_secret", reply)
        expected = store._pair_proof(code, "a" * 32, "tyler-gw", reply["from"]["gateway_id"], RESPONDER_SECRET,
                                     "herd-pair-v1")
        self.assertEqual(reply["mac"], expected)

    def test_a_new_requester_accepts_an_old_responder(self):
        code = self.mint()["code"]

        def old_responder(url, body):
            body = dict(body)
            body.pop("pair", None)  # an old responder never looks at it
            with self.responder:
                return json.loads(json.dumps(store.handle_pair_request(body)))

        store.PAIR_TRANSPORT = old_responder
        with self.requester:
            result = store.redeem_pairing(URL, code)
        self.assertEqual(result["multiplayer_secret"], RESPONDER_SECRET)

    def test_new_to_new_uses_the_new_exchange(self):
        code = self.mint()["code"]
        with self.requester:
            store.redeem_pairing(URL, code)
        self.assertEqual(self.calls[-1][1]["pair"], store.PAIR_PROTOCOL)


@unittest.skipUnless(HAVE_AIOHTTP, "aiohttp not installed")
class LegacyRoutes(Routes):
    def test_old_routes_are_still_served(self):
        status, body = http("POST", self.server.url + "/herd/v1/sync", {}, key=B_SECRET)
        self.assertEqual(status, 200, body)
        status, body = http("GET", self.server.url + "/herd/v1/ping", key=B_SECRET)
        self.assertEqual(status, 200, body)


if __name__ == "__main__":
    unittest.main()
