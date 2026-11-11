"""Message reactions: local toggle, validation, decoration, sync (cursor, tombstones, old peers), migration."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_store import Gateway  # noqa: E402

_, store, _tools = _pkg.load()
UP, HEART, EYES, PARTY = store.REACTIONS


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.A = Gateway(root, "tyler", peer="riley")
        self.B = Gateway(root, "riley")
        self.old_peer = False
        store.AUTO_SYNC = False

        def transport(peer, body):
            body = json.loads(json.dumps(body))
            with self.B:
                resp = json.loads(json.dumps(store.handle_peer_sync(body)))
            if self.old_peer:
                for k in ("reactions", "next_rseq", "rmore"):
                    resp.pop(k)
            return resp

        store.TRANSPORT = transport

    def tearDown(self):
        store.TRANSPORT = None
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        self.tmp.cleanup()

    def reactions_of(self, gw, mid):
        with gw:
            return {m["id"]: m["reactions"] for m in store.list_messages("general")}[mid]

    def sync(self):
        with self.A:
            [res] = store.sync_all()
        self.assertTrue(res["ok"], res)
        return res


class LocalTests(Base):
    def test_toggle_and_aggregate(self):
        with self.A:
            mid = store.post_message("general", "hi")["id"]
            r = store.toggle_reaction("general", mid, UP)
            self.assertTrue(r["active"])
            self.assertEqual(r["reactions"], [{"emoji": UP, "count": 1, "mine": True}])
            r = store.toggle_reaction("general", mid, UP)
            self.assertFalse(r["active"])
            self.assertEqual(r["reactions"], [])
            self.assertEqual(store.list_messages("general")[0]["reactions"], [])
            store.toggle_reaction("general", mid, UP)
            peer = {"from": {"gateway_id": "peer1", "display_name": "p"},
                    "reactions": [{"message_id": mid, "emoji": UP, "gateway_id": "peer1", "active": 1}]}
            store.ingest(peer)
            self.assertEqual(store.list_messages("general")[0]["reactions"],
                             [{"emoji": UP, "count": 2, "mine": True}])

    def test_validation(self):
        with self.A:
            mid = store.post_message("general", "hi")["id"]
            with self.assertRaises(store.MultiplayerError) as c:
                store.toggle_reaction("general", mid, "lol")  # a reaction is an emoji, never text
            self.assertEqual(c.exception.status, 422)
            with self.assertRaises(store.MultiplayerError) as c:
                store.toggle_reaction("general", "nope", UP)
            self.assertEqual(c.exception.status, 404)
            with self.assertRaises(store.MultiplayerError) as c:
                store.toggle_reaction("nochan", mid, UP)
            self.assertEqual(c.exception.status, 404)

    def test_decoration_order_and_mine(self):
        with self.A:
            mid = store.post_message("general", "hi")["id"]
            store.toggle_reaction("general", mid, PARTY)
            store.toggle_reaction("general", mid, UP)
            store.ingest({"reactions": [
                {"message_id": mid, "emoji": EYES, "gateway_id": "p1", "active": 1},
                {"message_id": mid, "emoji": PARTY, "gateway_id": "p1", "active": 0}]})
            got = store.list_messages("general")[0]["reactions"]
            self.assertEqual(got, [{"emoji": UP, "count": 1, "mine": True},
                                   {"emoji": EYES, "count": 1, "mine": False},
                                   {"emoji": PARTY, "count": 1, "mine": True}])
            self.assertEqual(store.list_reactions("general")[mid], got)

    def test_protocol_shape(self):
        with self.A:
            out = store.handle_peer_sync({"from": {"gateway_id": "x"}})
            for k in ("reactions", "next_rseq", "rmore"):
                self.assertIn(k, out)
            with self.assertRaises(store.MultiplayerError) as c:
                store.handle_peer_sync({"after_rseq": "abc"})
            self.assertEqual(c.exception.status, 422)

    def test_ingest_robustness(self):
        with self.A:
            mid = store.post_message("general", "hi")["id"]
            store.ingest({"reactions": [
                "junk", 5, None,
                {"message_id": mid, "emoji": "not an emoji", "gateway_id": "p", "active": 1},
                {"message_id": "ghost", "emoji": UP, "gateway_id": "p", "active": 1}]})
            self.assertEqual(store.list_messages("general")[0]["reactions"], [])
            with store.connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM reactions").fetchone()[0], 0)


class SyncTests(Base):
    def test_replayed_older_reaction_does_not_resurrect(self):
        """QA S2 (PR #24): a re-linked peer's full re-push replays an add we removed.

        INSERT OR REPLACE used to revive it; newest created_at must win so convergence
        depends on time, not arrival order.
        """
        with self.A:
            mid = store.post_message("general", "hi")["id"]
            early = {"message_id": mid, "emoji": UP, "gateway_id": "riley", "active": 1,
                     "created_at": "2026-11-06T12:00:00.000+00:00"}
            store.ingest({"reactions": [early]})
            self.assertEqual(self.reactions_of(self.A, mid), [{"emoji": UP, "count": 1, "mine": False}])
            store.ingest({"reactions": [dict(early, active=0,
                                             created_at="2026-11-06T12:00:05.000+00:00")]})
            self.assertEqual(self.reactions_of(self.A, mid), [])
            store.ingest({"reactions": [early]})  # the replayed old add
            self.assertEqual(self.reactions_of(self.A, mid), [])
            # A genuinely newer add still applies: the rule is last-write-wins, not freeze.
            store.ingest({"reactions": [dict(early, active=1,
                                             created_at="2026-11-06T12:00:09.000+00:00")]})
            self.assertEqual(self.reactions_of(self.A, mid), [{"emoji": UP, "count": 1, "mine": False}])

    def test_timestamp_ordering_ignores_spelling(self):
        # Peers may spell the same instant differently; ordering is by instant.
        self.assertGreater(store._ts("2026-11-06T12:00:01Z"), store._ts("2026-11-06T12:00:00.500+00:00"))
        self.assertEqual(store._ts("2026-11-06T12:00:00+00:00"), store._ts("2026-11-06T12:00:00Z"))
        self.assertLess(store._ts("garbage"), store._ts("2026-01-01T00:00:00+00:00"))
        self.assertLess(store._ts(""), store._ts("2026-01-01T00:00:00+00:00"))

    def test_flow_both_ways_tombstone_and_idempotency(self):
        with self.A:
            mid = store.post_message("general", "hello")["id"]
        self.sync()
        with self.A:
            store.toggle_reaction("general", mid, UP)
        with self.B:
            store.toggle_reaction("general", mid, HEART)
        res = self.sync()
        self.assertEqual(res["reactions_pushed"], 1)
        want_a = [{"emoji": UP, "count": 1, "mine": True}, {"emoji": HEART, "count": 1, "mine": False}]
        want_b = [{"emoji": UP, "count": 1, "mine": False}, {"emoji": HEART, "count": 1, "mine": True}]
        self.assertEqual(self.reactions_of(self.A, mid), want_a)
        self.assertEqual(self.reactions_of(self.B, mid), want_b)
        # Second round: nothing new either way.
        res = self.sync()
        self.assertEqual(res["reactions_pushed"], 0)
        # Un-react on A: B sees the count drop.
        with self.A:
            store.toggle_reaction("general", mid, UP)
        self.sync()
        self.assertEqual(self.reactions_of(self.B, mid), [{"emoji": HEART, "count": 1, "mine": True}])
        # Un-react on B flows to A.
        with self.B:
            store.toggle_reaction("general", mid, HEART)
        self.sync()
        self.assertEqual(self.reactions_of(self.A, mid), [])

    def test_old_peer_without_reactions(self):
        self.old_peer = True
        with self.A:
            mid = store.post_message("general", "m1")["id"]
            store.toggle_reaction("general", mid, UP)
        self.sync()
        with self.B:
            store.post_message("general", "from-b")
        self.sync()
        with self.A:
            self.assertEqual([m["content"] for m in store.list_messages("general")], ["m1", "from-b"])
            with store.connect() as conn:
                self.assertEqual(conn.execute("SELECT pull_rseq FROM peer_state").fetchone()[0], 0)


class MigrationTest(unittest.TestCase):
    def test_old_peer_state_gets_cursor_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE peer_state (url TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', "
                         "push_seq INTEGER NOT NULL DEFAULT 0, pull_seq INTEGER NOT NULL DEFAULT 0, "
                         "remote_gateway_id TEXT NOT NULL DEFAULT '', remote_name TEXT NOT NULL DEFAULT '', "
                         "last_attempt TEXT NOT NULL DEFAULT '', last_ok TEXT NOT NULL DEFAULT '', "
                         "last_error TEXT NOT NULL DEFAULT '')")
            conn.execute("INSERT INTO peer_state(url, push_seq) VALUES ('http://127.0.0.1:8642', 0)")  # matches the Gateway fixture's loopback peer URL
            conn.commit()
            conn.close()
            root = Path(tmp)
            A = Gateway(root, "old", peer="riley")
            A.db = db
            B = Gateway(root, "riley")
            store.AUTO_SYNC = False
            store.TRANSPORT = lambda peer, body: store_with(B, body)
            try:
                with A:
                    mid = store.post_message("general", "hi")["id"]
                    store.toggle_reaction("general", mid, UP)
                    [res] = store.sync_all()
                    self.assertTrue(res["ok"], res)
                    with store.connect() as c:
                        cols = {r[1] for r in c.execute("PRAGMA table_info(peer_state)")}
                        row = c.execute("SELECT push_seq, push_rseq FROM peer_state").fetchone()
                    self.assertTrue({"push_rseq", "pull_rseq"} <= cols)
                    self.assertGreaterEqual(row[0], 1)
                    self.assertGreaterEqual(row[1], 1)
                with B:
                    self.assertEqual(store.list_messages("general")[0]["reactions"][0]["count"], 1)
            finally:
                store.TRANSPORT = None
                store.DB_PATH_OVERRIDE = None
                store.SETTINGS_OVERRIDE = None


def store_with(gw, body):
    with gw:
        return json.loads(json.dumps(store.handle_peer_sync(json.loads(json.dumps(body)))))


if __name__ == "__main__":
    unittest.main()
