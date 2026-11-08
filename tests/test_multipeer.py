"""Up to five gateways: the teammate list, per-teammate state, fan-out, convergence, isolation, membership.

Runs in-process (stdlib only). Each gateway is a separate SQLite file; a transport routes a sync request to the
gateway whose URL it was sent to, exactly as ``POST <url>/herd/v1/sync`` would. Tests that need the real
urllib path use a local HTTP stand-in instead.
"""
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, tools = _pkg.load()

# Loopback http is allowed by the default cleartext policy, so every test teammate can use a local URL.
URL = {"riley": "http://127.0.0.1:8641", "ash": "http://127.0.0.1:8642", "kai": "http://127.0.0.1:8643",
       "noor": "http://127.0.0.1:8644"}


def _roundtrip(gw, body):
    """What ``POST /herd/v1/sync`` does on the receiving gateway, with JSON on both sides of the wire."""
    with gw:
        return json.loads(json.dumps(store.handle_peer_sync(json.loads(json.dumps(body)))))


class Mesh:
    """N gateways in one process. Gateway ``name`` is reachable at ``URL[name]``; ``links`` says who syncs
    with whom (the caller's peer list). Each gateway's database and settings are swapped in only while it runs."""

    def __init__(self, root: Path, names, links):
        self.dbs = {n: root / f"{n}.db" for n in names}
        self.settings = {}
        for n in names:
            slots = store.PEER_KEY_ENVS
            peers = [{"name": other, "url": URL[other], "key_env": slots[i]}
                     for i, other in enumerate(links.get(n, []))]
            secrets = {slots[i]: f"k-{other}" for i, other in enumerate(links.get(n, []))}
            self.settings[n] = {"display_name": n, "peers": peers, "__secrets__": secrets}
        self.calls = []  # (sender, url, key, body) for every request that left a gateway
        self.down = set()  # names whose URL refuses connections
        self.by_url = {URL[n]: n for n in names}
        store.AUTO_SYNC = False
        store.TRANSPORT = self._transport

    def close(self):
        store.TRANSPORT = None
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None

    def _transport(self, peer, body):
        target = self.by_url[peer["url"]]
        self.calls.append((self._current, peer["url"], peer["key"], json.loads(json.dumps(body))))
        if target in self.down:
            raise ConnectionError("unreachable")
        return _roundtrip(self.gw(target), body)

    _current = None

    def gw(self, name):
        return _Gateway(self, name)

    def sync(self, name):
        with self.gw(name):
            return store.sync_all()

    def texts(self, name, channel="general"):
        with self.gw(name):
            return sorted(m["content"] for m in store.list_messages(channel, limit=500))

    def rows(self, name):
        """Every message on a gateway as comparable tuples: convergence means these are equal everywhere."""
        with self.gw(name):
            with store.connect() as conn:
                return sorted(tuple(r) for r in conn.execute(
                    "SELECT id, channel_id, content, gateway_id FROM messages ORDER BY id"))


class _Gateway:
    def __init__(self, mesh, name):
        self.mesh, self.name = mesh, name

    def __enter__(self):
        self._saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, self.mesh._current)
        store.DB_PATH_OVERRIDE = self.mesh.dbs[self.name]
        store.SETTINGS_OVERRIDE = self.mesh.settings[self.name]
        self.mesh._current = self.name
        return self

    def __exit__(self, *exc):
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, self.mesh._current = self._saved


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = (store.AUTO_SYNC, store.TRANSPORT, store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE)

    def tearDown(self):
        store.AUTO_SYNC, store.TRANSPORT, store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = self._saved
        self.tmp.cleanup()

    def with_settings(self, settings, db="single.db"):
        store.DB_PATH_OVERRIDE = Path(self.tmp.name) / db
        store.SETTINGS_OVERRIDE = settings
        store.AUTO_SYNC = False


class TeammateListTest(_Base):
    """Spec §1.1: the single peer becomes a list, and an existing single-peer config keeps working."""

    def test_single_peer_config_is_teammate_one_with_its_stored_secret(self):
        self.with_settings({"display_name": "tyler", "peer_name": "riley", "peer_url": URL["riley"],
                            "__secrets__": {"HERD_PEER_KEY": "stored-secret"}})
        [peer] = store.configured_peers()
        self.assertEqual((peer["name"], peer["url"], peer["key"]), ("riley", URL["riley"], "stored-secret"))

    def test_single_peer_config_still_shows_in_status_with_no_keys(self):
        self.with_settings({"display_name": "tyler", "peer_name": "riley", "peer_url": URL["riley"],
                            "__secrets__": {"HERD_PEER_KEY": "stored-secret"}})
        st = store.status()
        self.assertEqual([p["name"] for p in st["peers"]], ["riley"])
        self.assertTrue(st["peers"][0]["has_key"])
        self.assertNotIn("stored-secret", json.dumps(st))

    def test_numbered_slots_give_each_teammate_its_own_key(self):
        self.with_settings({
            "display_name": "tyler",
            "peer_name": "riley", "peer_url": URL["riley"],
            "peer_name_2": "ash", "peer_url_2": URL["ash"],
            "peer_name_3": "kai", "peer_url_3": URL["kai"],
            "peer_name_4": "noor", "peer_url_4": URL["noor"],
            "__secrets__": {"HERD_PEER_KEY": "k-riley", "HERD_PEER_KEY_2": "k-ash",
                            "HERD_PEER_KEY_3": "k-kai", "HERD_PEER_KEY_4": "k-noor"},
        })
        peers = store.configured_peers()
        self.assertEqual([(p["name"], p["key"]) for p in peers],
                         [("riley", "k-riley"), ("ash", "k-ash"), ("kai", "k-kai"), ("noor", "k-noor")])
        self.assertEqual(store.refused_peers(), [])

    def test_peers_list_in_settings_names_its_own_secret_slot(self):
        self.with_settings({
            "display_name": "tyler",
            "peers": [{"name": "ash", "url": URL["ash"], "key_env": "HERD_PEER_KEY_2"}],
            "__secrets__": {"HERD_PEER_KEY_2": "k-ash"},
        })
        [peer] = store.configured_peers()
        self.assertEqual((peer["name"], peer["key"]), ("ash", "k-ash"))

    def test_legacy_peer_and_peers_list_are_both_kept(self):
        self.with_settings({
            "display_name": "tyler",
            "peer_name": "riley", "peer_url": URL["riley"],
            "peers": [{"name": "ash", "url": URL["ash"], "key_env": "HERD_PEER_KEY_2"}],
            "__secrets__": {"HERD_PEER_KEY": "k-riley", "HERD_PEER_KEY_2": "k-ash"},
        })
        self.assertEqual([(p["name"], p["key"]) for p in store.configured_peers()],
                         [("riley", "k-riley"), ("ash", "k-ash")])

    def test_a_teammate_never_gets_another_teammates_key(self):
        # Slot 2 holds ash's key. A list entry that names slot 3 must read slot 3 (empty), never slot 2.
        self.with_settings({"display_name": "tyler",
                            "peers": [{"name": "kai", "url": URL["kai"], "key_env": "HERD_PEER_KEY_3"}],
                            "__secrets__": {"HERD_PEER_KEY_2": "k-ash"}})
        [peer] = store.configured_peers()
        self.assertEqual(peer["key"], "")
        self.assertNotIn("k-ash", json.dumps(store.status()))

    def test_list_entry_without_a_slot_is_refused_not_guessed(self):
        self.with_settings({"display_name": "tyler",
                            "peers": [{"name": "kai", "url": URL["kai"]}],
                            "__secrets__": {"HERD_PEER_KEY": "k-kai"}})
        self.assertEqual(store.configured_peers(), [])
        [refused] = store.refused_peers()
        self.assertIn("Herd secret slot", refused["reason"])

    def test_duplicates_and_unknown_slots_are_refused_with_a_reason(self):
        self.with_settings({
            "display_name": "tyler",
            "peer_name": "riley", "peer_url": URL["riley"],
            "peers": [
                {"name": "riley", "url": URL["ash"], "key_env": "HERD_PEER_KEY_2"},       # name taken
                {"name": "ash", "url": URL["riley"], "key_env": "HERD_PEER_KEY_3"},       # url taken
                {"name": "kai", "url": URL["kai"], "key_env": "HERD_PEER_KEY"},           # slot taken
                {"name": "noor", "url": URL["noor"], "key_env": "HERD_PEER_KEY_4"},       # usable
                {"name": "fifth", "url": "http://127.0.0.1:8650", "key_env": "HERD_PEER_KEY_5"},  # no such slot
            ],
        })
        self.assertEqual([p["name"] for p in store.configured_peers()], ["riley", "noor"])
        reasons = {r["url"]: r["reason"] for r in store.refused_peers()}
        self.assertEqual(len(reasons), 4)
        self.assertIn("name", reasons[URL["ash"]])
        self.assertIn("URL", reasons[URL["riley"]])
        self.assertIn("slot", reasons[URL["kai"]])
        self.assertIn("slot", reasons["http://127.0.0.1:8650"])

    def test_non_http_entries_are_still_silently_ignored(self):
        self.with_settings({"display_name": "tyler", "peer_name": "riley", "peer_url": "ftp://example.test",
                            "__secrets__": {"HERD_PEER_KEY": "k"}})
        self.assertEqual(store.configured_peers(), [])
        self.assertEqual(store.refused_peers(), [])
        self.assertEqual(store.status()["peers"], [])


class PeerStateMigrationTest(_Base):
    """Spec §1.2: peer state is one row per teammate name; an upgraded install keeps its cursors."""

    def _old_db(self, path):
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE peer_state (url TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', "
                     "push_seq INTEGER NOT NULL DEFAULT 0, pull_seq INTEGER NOT NULL DEFAULT 0, "
                     "push_rseq INTEGER NOT NULL DEFAULT 0, pull_rseq INTEGER NOT NULL DEFAULT 0, "
                     "remote_gateway_id TEXT NOT NULL DEFAULT '', remote_name TEXT NOT NULL DEFAULT '', "
                     "last_attempt TEXT NOT NULL DEFAULT '', last_ok TEXT NOT NULL DEFAULT '', "
                     "last_error TEXT NOT NULL DEFAULT '')")
        conn.execute("INSERT INTO peer_state(url, name, push_seq, pull_seq, remote_gateway_id) "
                     "VALUES (?, 'riley', 7, 4, 'gid-riley')", (URL["riley"],))
        conn.commit()
        conn.close()

    def test_url_keyed_table_is_rekeyed_by_name_and_keeps_cursors(self):
        db = Path(self.tmp.name) / "old.db"
        self._old_db(db)
        self.with_settings({"display_name": "tyler", "peer_name": "riley", "peer_url": URL["riley"],
                            "__secrets__": {"HERD_PEER_KEY": "k-riley"}}, db="old.db")
        with store.connect() as conn:
            pk = {r[1]: r[5] for r in conn.execute("PRAGMA table_info(peer_state)")}
            row = conn.execute("SELECT name, url, push_seq, pull_seq, remote_gateway_id FROM peer_state").fetchall()
        self.assertEqual(pk["name"], 1)
        self.assertEqual(pk["url"], 0)
        self.assertEqual([tuple(r) for r in row], [("riley", URL["riley"], 7, 4, "gid-riley")])

    def test_unnamed_legacy_row_is_adopted_by_its_teammate(self):
        db = Path(self.tmp.name) / "unnamed.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE peer_state (url TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', "
                     "push_seq INTEGER NOT NULL DEFAULT 0, pull_seq INTEGER NOT NULL DEFAULT 0, "
                     "remote_gateway_id TEXT NOT NULL DEFAULT '', remote_name TEXT NOT NULL DEFAULT '', "
                     "last_attempt TEXT NOT NULL DEFAULT '', last_ok TEXT NOT NULL DEFAULT '', "
                     "last_error TEXT NOT NULL DEFAULT '')")
        conn.execute("INSERT INTO peer_state(url, push_seq) VALUES (?, 3)", (URL["riley"],))
        conn.commit()
        conn.close()
        self.with_settings({"display_name": "tyler", "peer_name": "riley", "peer_url": URL["riley"],
                            "__secrets__": {"HERD_PEER_KEY": "k-riley"}}, db="unnamed.db")
        with store.connect() as conn:
            store._peer_state(conn, {"name": "riley", "url": URL["riley"]})
            rows = conn.execute("SELECT name, push_seq FROM peer_state").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("riley", 3)])

    def test_changed_url_resets_that_teammates_cursors_only(self):
        self.with_settings({"display_name": "tyler", "peer_name": "riley", "peer_url": URL["riley"],
                            "__secrets__": {"HERD_PEER_KEY": "k"}})
        with store.connect() as conn:
            store._peer_state(conn, {"name": "riley", "url": URL["riley"]})
            conn.execute("UPDATE peer_state SET push_seq = 9, remote_gateway_id = 'gid' WHERE name = 'riley'")
            store._peer_state(conn, {"name": "riley", "url": "http://127.0.0.1:8699"})
            row = conn.execute("SELECT url, push_seq, remote_gateway_id FROM peer_state WHERE name = 'riley'").fetchone()
        self.assertEqual(tuple(row), ("http://127.0.0.1:8699", 0, ""))


if __name__ == "__main__":
    unittest.main()
