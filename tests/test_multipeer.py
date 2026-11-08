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
URL = {"tyler": "http://127.0.0.1:8640", "riley": "http://127.0.0.1:8641", "ash": "http://127.0.0.1:8642",
       "kai": "http://127.0.0.1:8643", "noor": "http://127.0.0.1:8644"}


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

    def gid(self, name):
        with self.gw(name):
            return store.identity()["gateway_id"]

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



class _MeshHarness(_Base):
    """Shared setup for the mesh tests (no tests of its own)."""

    @staticmethod
    def star(hub, leaves):
        """``hub`` links to every leaf; a leaf links only to the hub (the usual case: Tyler in the middle)."""
        links = {hub: list(leaves)}
        for leaf in leaves:
            links[leaf] = [hub]
        return links

    def build(self, names, links):
        self.mesh = Mesh(Path(self.tmp.name), names, links)
        self.addCleanup(self.mesh.close)
        return self.mesh


class MeshSyncTest(_MeshHarness):
    """Spec §1.3-1.5: fan-out to every teammate, no echo to the author, convergence, per-teammate isolation."""

    # --- fan-out ------------------------------------------------------------------------------

    def test_three_gateways_converge_through_the_hub(self):
        m = self.build(["tyler", "riley", "ash"], self.star("tyler", ["riley", "ash"]))
        with m.gw("riley"):
            store.post_message("general", "from riley")
        m.sync("riley")                       # riley -> tyler
        self.assertEqual(m.texts("tyler"), ["from riley"])
        m.sync("tyler")                       # tyler forwards riley's message to ash (not back to riley)
        self.assertEqual(m.texts("ash"), ["from riley"])
        with m.gw("ash"):
            store.post_message("general", "from ash")
        m.sync("ash")
        m.sync("tyler")
        m.sync("riley")
        for name in ("tyler", "riley", "ash"):
            self.assertEqual(m.texts(name), ["from ash", "from riley"], name)

    def test_five_gateways_fan_out_from_the_hub_and_back(self):
        leaves = ["riley", "ash", "kai", "noor"]
        names = ["tyler", *leaves]
        m = self.build(names, self.star("tyler", leaves))
        with m.gw("tyler"):
            store.post_message("general", "hello mesh")
        m.sync("tyler")
        for leaf in leaves:
            with m.gw(leaf):
                store.post_message("general", f"hi from {leaf}")
            m.sync(leaf)
        m.sync("tyler")
        for leaf in leaves:
            m.sync(leaf)
        expected = sorted(["hello mesh", *(f"hi from {leaf}" for leaf in leaves)])
        for name in names:
            self.assertEqual(m.texts(name), expected, name)

    def test_a_gateway_with_no_link_gets_nothing_and_breaks_nothing(self):
        # ash is configured with nobody; the rest of the mesh still converges.
        links = {"tyler": ["riley"], "riley": ["tyler"], "ash": []}
        m = self.build(["tyler", "riley", "ash"], links)
        with m.gw("tyler"):
            store.post_message("general", "two of us")
        m.sync("tyler")
        m.sync("riley")
        self.assertEqual(m.texts("riley"), ["two of us"])
        self.assertEqual(m.texts("ash"), [])

    # --- no echo ------------------------------------------------------------------------------

    def test_inbound_message_is_never_sent_back_to_its_author(self):
        # riley's message reaches tyler through ash (ash has no direct link to tyler's riley pass),
        # then tyler must forward it to ash but never back to riley, its author.
        links = {"tyler": ["riley", "ash"], "riley": ["ash"], "ash": ["riley", "tyler"]}
        m = self.build(["tyler", "riley", "ash"], links)
        with m.gw("riley"):
            store.post_message("general", "riley's own words")
        m.sync("riley")      # ash now holds riley's message
        m.sync("tyler")      # tyler pulls it from ash
        m.sync("riley")
        m.sync("tyler")
        riley_gid = m.gid("riley")
        to_riley = [body for (_sender, url, _key, body) in m.calls if m.by_url[url] == "riley"]
        self.assertTrue(to_riley)
        for body in to_riley:
            self.assertNotIn(riley_gid, {row["gateway_id"] for row in body["messages"]})
        self.assertEqual(m.texts("tyler"), ["riley's own words"])

    def test_first_request_to_a_new_teammate_carries_no_rows(self):
        # Until a teammate identifies itself, our rows (which may include its own) are not sent to it.
        m = self.build(["tyler", "riley", "ash"], self.star("tyler", ["riley", "ash"]))
        with m.gw("ash"):
            store.post_message("general", "relayed")
        m.sync("ash")
        m.sync("tyler")                       # tyler now holds ash's row; riley is not identified yet
        first_to_riley = next(body for (_s, url, _k, body) in m.calls if m.by_url[url] == "riley")
        self.assertEqual(first_to_riley["messages"], [])
        # The same pass identifies riley in round one and carries the window in round two: ash's row goes
        # out, riley's own rows never do (riley has none here, and origin exclusion would drop them anyway).
        self.assertEqual(m.texts("riley"), ["relayed"])
        riley_rows = [row for row in m.rows("riley") if row[3] == m.gid("riley")]
        self.assertEqual(riley_rows, [])

    # --- convergence ----------------------------------------------------------------------------

    def test_simultaneous_posts_converge_to_the_same_rows_everywhere(self):
        names = ["tyler", "riley", "ash"]
        m = self.build(names, self.star("tyler", ["riley", "ash"]))
        # Everyone posts before anyone syncs: the two leaves write at the same moment as the hub.
        for name in names:
            with m.gw(name):
                for i in range(3):
                    store.post_message("general", f"{name}-{i}")
        for _ in range(3):
            for name in names:
                m.sync(name)
        reference = m.rows("tyler")
        self.assertEqual(len(reference), 9)
        for name in names:
            self.assertEqual(m.rows(name), reference, name)

    def test_reactions_and_thread_replies_converge_through_the_hub(self):
        m = self.build(["tyler", "riley", "ash", "kai"], self.star("tyler", ["riley", "ash", "kai"]))
        with m.gw("riley"):
            root = store.post_message("general", "root from riley")["id"]
        m.sync("riley")
        m.sync("tyler")
        with m.gw("ash"):
            store.toggle_reaction("general", root, "\U0001f44d")           # a relayed reaction (origin ash)
            store.post_message("general", "reply from ash", thread_parent_id=root)
        with m.gw("kai"):
            store.toggle_reaction("general", root, "\U0001f44d")
        m.sync("ash")
        m.sync("kai")
        m.sync("tyler")
        m.sync("riley")
        m.sync("ash")
        for name in ("tyler", "riley", "ash", "kai"):
            with m.gw(name):
                [parent] = [x for x in store.list_messages("general") if x["id"] == root]
                self.assertEqual(parent["reply_count"], 1, name)
                self.assertEqual(parent["reactions"], [{"emoji": "\U0001f44d", "count": 2,
                                                        "mine": name in ("ash", "kai")}], name)
                reply = store.list_thread(root)["replies"][0]
                self.assertEqual(reply["content"], "reply from ash", name)
                self.assertEqual(reply["gateway_id"], m.gid("ash"), name)  # origin kept on every gateway

    def test_the_same_message_delivered_by_two_paths_is_one_row(self):
        m = self.build(["tyler", "riley", "ash"], self.star("tyler", ["riley", "ash"]))
        with m.gw("riley"):
            store.post_message("general", "once", message_id="00000000-0000-4000-8000-000000000001")
        for _ in range(2):
            m.sync("riley")
            m.sync("ash")
            m.sync("tyler")
        for name in ("tyler", "riley", "ash"):
            self.assertEqual(m.texts(name), ["once"], name)

    # --- isolation ------------------------------------------------------------------------------

    def test_one_failing_teammate_does_not_stop_the_others(self):
        m = self.build(["tyler", "riley", "ash", "kai"], self.star("tyler", ["riley", "ash", "kai"]))
        m.down.add("riley")                   # riley's address refuses every request
        with m.gw("tyler"):
            store.post_message("general", "still goes out")
            results = store.sync_all()
            st = store.status()
        by_name = {r["name"]: r for r in results}
        self.assertFalse(by_name["riley"]["ok"])
        self.assertTrue(by_name["ash"]["ok"])
        self.assertTrue(by_name["kai"]["ok"])
        peers = {p["name"]: p for p in st["peers"]}
        self.assertFalse(peers["riley"]["connected"])
        self.assertTrue(peers["ash"]["connected"])
        self.assertTrue(peers["kai"]["connected"])
        self.assertEqual(m.texts("ash"), ["still goes out"])
        self.assertEqual(m.texts("kai"), ["still goes out"])
        self.assertEqual(m.texts("riley"), [])
        # riley's own cursor did not move, so it catches up once it is back.
        m.down.clear()
        m.sync("tyler")
        self.assertEqual(m.texts("riley"), ["still goes out"])

    def test_a_teammate_that_throws_is_one_error_line_not_a_crash(self):
        m = self.build(["tyler", "riley", "ash"], self.star("tyler", ["riley", "ash"]))
        real = store.TRANSPORT

        def boom_for_riley(peer, body):
            if peer["name"] == "riley":
                raise RuntimeError("internal detail that must not reach the pane")
            return real(peer, body)

        store.TRANSPORT = boom_for_riley
        try:
            with m.gw("tyler"):
                store.post_message("general", "x")
                results = store.sync_all()
                st = store.status()
        finally:
            store.TRANSPORT = real
        by_name = {r["name"]: r for r in results}
        self.assertEqual(by_name["riley"]["error"], "Sync failed.")
        self.assertNotIn("internal detail", json.dumps(st))
        self.assertTrue(by_name["ash"]["ok"])

    def test_each_request_carries_only_its_own_teammates_key(self):
        m = self.build(["tyler", "riley", "ash", "kai"], self.star("tyler", ["riley", "ash", "kai"]))
        with m.gw("tyler"):
            store.post_message("general", "keys")
        m.sync("tyler")
        self.assertTrue(m.calls)
        for (_sender, url, key, _body) in m.calls:
            self.assertEqual(key, "k-" + m.by_url[url])

    def test_status_lists_every_teammate_and_never_a_key(self):
        m = self.build(["tyler", "riley", "ash", "kai", "noor"], self.star("tyler", ["riley", "ash", "kai", "noor"]))
        m.sync("tyler")
        with m.gw("tyler"):
            st = store.status()
        self.assertEqual(sorted(p["name"] for p in st["peers"]), ["ash", "kai", "noor", "riley"])
        self.assertTrue(all(p["connected"] for p in st["peers"]))
        blob = json.dumps(st)
        for name in ("riley", "ash", "kai", "noor"):
            self.assertNotIn("k-" + name, blob)



class ChannelMembershipTest(_MeshHarness):
    """Spec §1.6: a channel holds up to five people; a gateway that is not a member never receives it."""

    def setUp(self):
        super().setUp()
        # tyler is the hub; riley, ash and kai are teammates. Only riley and ash will be members of "ops".
        self.m = self.build(["tyler", "riley", "ash", "kai"], self.star("tyler", ["riley", "ash", "kai"]))
        for leaf in ("riley", "ash", "kai"):  # first contact: the hub learns each teammate's id
            self.m.sync(leaf)
            self.m.sync("tyler")

    def channels(self, name):
        with self.m.gw(name):
            return {c["id"] for c in store.list_channels()}

    def make_ops(self):
        with self.m.gw("tyler"):
            channel = store.create_channel("ops", members=[self.m.gid("riley"), self.m.gid("ash")])
        self.assertEqual(sorted(x["name"] for x in channel["members"]), ["ash", "riley", "tyler"])
        return channel

    def test_members_get_the_channel_and_its_messages_others_do_not(self):
        self.make_ops()
        with self.m.gw("tyler"):
            store.post_message("ops", "for members only")
        for _ in range(2):
            self.m.sync("tyler")
            self.m.sync("riley")
            self.m.sync("ash")
        self.assertIn("ops", self.channels("riley"))
        self.assertIn("ops", self.channels("ash"))
        self.assertEqual(self.m.texts("riley", "ops"), ["for members only"])
        self.assertEqual(self.m.texts("ash", "ops"), ["for members only"])
        self.assertNotIn("ops", self.channels("kai"))
        self.assertEqual(self.m.texts("kai", "general"), [])

    def test_a_member_relays_to_the_other_member_but_never_to_a_non_member(self):
        self.make_ops()
        self.m.sync("tyler")                  # riley learns the channel from the hub's pass
        with self.m.gw("riley"):
            store.post_message("ops", "riley to the group")
        for _ in range(2):
            self.m.sync("riley")
            self.m.sync("tyler")
            self.m.sync("ash")
        self.assertEqual(self.m.texts("ash", "ops"), ["riley to the group"])
        kai_gid = self.m.gid("kai")
        for (_s, url, _k, body) in self.m.calls:
            if self.m.by_url[url] == "kai":
                self.assertNotIn("ops", {c["id"] for c in body["channels"]})
                self.assertNotIn("riley to the group", [row["content"] for row in body["messages"]])
                self.assertNotIn(kai_gid, [row["gateway_id"] for row in body["messages"]])

    def test_sharing_a_dm_copies_it_only_to_the_two_people_in_it(self):
        with self.m.gw("tyler"):
            dm = store.open_dm(self.m.gid("riley"))
            store.post_message(dm["id"], "private to us")
        self.m.sync("tyler")
        self.m.sync("riley")
        with self.m.gw("tyler"):
            shared = store.share_dm(dm["id"], "launch")
            self.assertEqual(sorted(x["name"] for x in shared["members"]), ["riley", "tyler"])
        for _ in range(2):
            self.m.sync("tyler")
            self.m.sync("riley")
            self.m.sync("ash")
            self.m.sync("kai")
        self.assertEqual(self.m.texts("riley", "launch"), ["private to us"])
        self.assertNotIn("launch", self.channels("ash"))
        self.assertNotIn("launch", self.channels("kai"))
        self.assertNotIn(dm["id"], self.channels("ash"))

    def test_a_non_member_cannot_inject_rows_into_a_member_listed_channel(self):
        self.make_ops()
        with self.m.gw("tyler"):
            channel = store.get_channel("ops")
            riley_gid, kai_gid = self.m.gid("riley"), self.m.gid("kai")
            spoof = {"id": "kai-spoof-1", "channel_id": "ops", "author_type": "human", "author_name": "kai",
                     "gateway_id": kai_gid, "gateway_name": "kai", "content": "let me in",
                     "created_at": "2026-11-08T00:00:00.000+00:00"}
            # kai sends its own row, and riley's relayed row that names kai as the origin is also refused.
            counts = {}
            store.ingest({"from": {"gateway_id": kai_gid, "display_name": "kai"}, "channels": [],
                          "messages": [spoof], "reactions": []}, stats=counts)
            self.assertEqual(counts["dropped"], 1)
            self.assertIsNone(store.get_message("kai-spoof-1"))
            self.assertEqual({x["id"] for x in channel["members"]}, {store.identity()["gateway_id"], riley_gid,
                                                                    self.m.gid("ash")})
            # The same row, relayed by a member (riley), still names a non-member origin: refused.
            counts = {}
            store.ingest({"from": {"gateway_id": riley_gid, "display_name": "riley"}, "channels": [],
                          "messages": [dict(spoof, id="kai-spoof-2")], "reactions": []}, stats=counts)
            self.assertEqual(counts["dropped"], 1)
            self.assertIsNone(store.get_message("kai-spoof-2"))

    def test_a_channel_row_that_does_not_include_this_gateway_is_refused(self):
        with self.m.gw("kai"):
            store.ingest({"from": {"gateway_id": "riley-gid-x", "display_name": "riley"},
                          "channels": [{"id": "ops", "is_dm": False, "members": [
                              {"id": "riley-gid-x", "name": "riley"}, {"id": "ash-gid-x", "name": "ash"}]}],
                          "messages": [], "reactions": []})
            self.assertNotIn("ops", {c["id"] for c in store.list_channels()})

    def test_more_than_five_people_is_refused_at_creation_and_on_arrival(self):
        with self.m.gw("tyler"):
            me = store.identity()["gateway_id"]
            three = [self.m.gid(n) for n in ("riley", "ash", "kai")]
            # Five people with a teammate of ours: self plus three known teammates is four, so a fifth
            # known person is needed to test the limit; the unknown ids below are refused before that.
            with self.assertRaises(store.HerdError) as caught:
                store.create_channel("too-many", members=[*three, "g-five", "g-six"])
            self.assertEqual(caught.exception.status, 422)
            self.assertIsNone(store.get_channel("too-many"))
            ok = store.create_channel("four-people", members=three)  # self + 3 = four
            self.assertEqual(len(ok["members"]), 4)
            self.assertIn(me, [x["id"] for x in ok["members"]])
        self.assertIsNone(store._clean_members([{"id": f"g{i}"} for i in range(6)]))
        self.assertEqual(len(store._clean_members([{"id": f"g{i}"} for i in range(5)])), 5)
        self.assertIsNone(store._clean_members([{"id": "bad id!"}]))

    def test_the_channels_route_passes_members_to_the_store(self):
        try:
            import herd.dashboard.plugin_api as api
        except Exception:  # noqa: BLE001 — fastapi is a test-only dependency
            self.skipTest("fastapi not installed (pip install -r requirements-dev.txt)")
        with self.m.gw("tyler"):
            body = {"name": "via-route", "members": [self.m.gid("riley")]}
            out = api.post_channel(body)
            self.assertEqual(sorted(x["name"] for x in out["members"]), ["riley", "tyler"])
            self.assertEqual(store.get_channel("via-route")["members"], out["members"])

    def test_unknown_or_malformed_member_ids_are_refused(self):
        with self.m.gw("tyler"):
            with self.assertRaises(store.HerdError):
                store.create_channel("ghosts", members=["nobody-we-know"])
            with self.assertRaises(store.HerdError):
                store.create_channel("odd", members="riley")
            self.assertIsNone(store._clean_members(["has spaces"]))




class ParallelIsolationTest(unittest.TestCase):
    """Production path (no transport seam): a hanging teammate costs its own timeout, not everyone else's."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = (store.AUTO_SYNC, store.TRANSPORT, store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE,
                       store.SYNC_TIMEOUT_S)
        self.fast_at = None
        self.started = time.time()
        test = self

        class Slow(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                time.sleep(1.5)  # longer than the timeout below: this teammate hangs
                self.send_response(503)
                self.send_header("Content-Length", "0")
                self.end_headers()

        class Fast(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                test.fast_at = time.time() - test.started
                body = json.dumps({"v": 2, "from": {"gateway_id": "g-fast", "display_name": "fast"},
                                   "channels": [], "messages": [], "reactions": [], "next_seq": 0,
                                   "more": False, "next_rseq": 0, "rmore": False}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.servers = []
        for handler in (Slow, Fast):
            srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.servers.append(srv)
        slow, fast = self.servers
        self.urls = {"slow": f"http://127.0.0.1:{slow.server_address[1]}",
                     "fast": f"http://127.0.0.1:{fast.server_address[1]}"}
        store.TRANSPORT = None
        store.AUTO_SYNC = False
        store.SYNC_TIMEOUT_S = 0.6
        store.DB_PATH_OVERRIDE = Path(self.tmp.name) / "a.db"
        # The hanging teammate is listed first: a sequential pass would make the fast one wait for it.
        store.SETTINGS_OVERRIDE = {"display_name": "tyler", "__secrets__": {"HERD_PEER_KEY": "k-slow",
                                                                             "HERD_PEER_KEY_2": "k-fast"},
                                   "peers": [{"name": "slow", "url": self.urls["slow"], "key_env": "HERD_PEER_KEY"},
                                             {"name": "fast", "url": self.urls["fast"],
                                              "key_env": "HERD_PEER_KEY_2"}]}

    def tearDown(self):
        for srv in self.servers:
            srv.shutdown()
            srv.server_close()
        (store.AUTO_SYNC, store.TRANSPORT, store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE,
         store.SYNC_TIMEOUT_S) = self._saved
        self.tmp.cleanup()

    def test_fast_teammate_is_not_held_up_by_a_hanging_one(self):
        results = store.sync_all()
        by_name = {r["name"]: r for r in results}
        self.assertFalse(by_name["slow"]["ok"])
        self.assertTrue(by_name["fast"]["ok"], by_name["fast"])
        self.assertIsNotNone(self.fast_at)
        self.assertLess(self.fast_at, 0.5, "the fast teammate waited for the hanging one")



if __name__ == "__main__":
    unittest.main()
