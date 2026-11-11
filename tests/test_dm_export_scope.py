"""S-22: peer sync never exports a DM to a gateway that is not one of its two members.

B is linked TO by both A and C (multi-incoming). B's DB holds ``general``, ``dm:A+B``, ``dm:B+C`` and a
foreign ``dm:C+A`` row (what an old multi-incoming leak left on B). Every assertion is about the ids
the real ``export_batch`` / ``handle_peer_sync`` / ``sync_all`` return or send.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_store import Gateway  # noqa: E402

_, store, tools = _pkg.load()

UP, HEART, EYES, PARTY = store.REACTIONS


def _ids(rows, key="id"):
    return {r[key] for r in rows}


class DmExportScopeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.A = Gateway(root, "ash", peer="blair")
        self.C = Gateway(root, "cole", peer="blair")
        self.B = Gateway(root, "blair")
        store.AUTO_SYNC = False

        def transport(peer, body):
            with self.B:
                return json.loads(json.dumps(store.handle_peer_sync(json.loads(json.dumps(body)))))

        store.TRANSPORT = transport
        self.build_b_side()

    def tearDown(self):
        store.TRANSPORT = None
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        self.tmp.cleanup()

    def sync(self, gw):
        with gw:
            [res] = store.sync_all()
        self.assertTrue(res["ok"], res)

    def build_b_side(self):
        for gw, attr in ((self.A, "a_id"), (self.B, "b_id"), (self.C, "c_id")):
            with gw:
                setattr(self, attr, store.identity()["gateway_id"])
        self.sync(self.A)
        self.sync(self.C)
        # Public channel: one message authored on A, one on C.
        with self.A:
            self.gen_a = store.post_message("general", "hello from ash")["id"]
        with self.C:
            self.gen_c = store.post_message("general", "hello from cole")["id"]
        self.sync(self.A)
        self.sync(self.C)
        # dm:A+B — a message from each side plus a reaction by B on A's message.
        with self.A:
            self.dm_ab = store.open_dm(self.b_id)["id"]
            self.ab_from_a = store.post_message(self.dm_ab, "ash to blair")["id"]
        self.sync(self.A)
        with self.B:
            self.ab_from_b = store.post_message(self.dm_ab, "blair to ash")["id"]
            store.toggle_reaction(self.dm_ab, self.ab_from_a, UP)
        self.sync(self.A)
        # A foreign dm:C+A stored on B (what a multi-incoming leak leaves behind), ingested from C.
        # Stored before dm:B+C so that, for caller A, the rows above dm:B+C's first seq are all foreign.
        self.dm_ca = store.dm_channel_id(self.c_id, self.a_id)
        with self.B:
            self.ingest_dm_ca()
        # dm:B+C — a message from each side plus a reaction by C on B's message.
        with self.C:
            self.dm_bc = store.open_dm(self.b_id)["id"]
            self.bc_from_c = store.post_message(self.dm_bc, "cole to blair")["id"]
        self.sync(self.C)
        with self.B:
            self.bc_from_b = store.post_message(self.dm_bc, "blair to cole")["id"]
        self.sync(self.C)
        with self.C:
            store.toggle_reaction(self.dm_bc, self.bc_from_b, HEART)
        self.sync(self.C)
        self.foreign = {self.dm_bc}  # the DM caller A is not in (A IS a member of dm:C+A)
        # Preconditions: B really holds every row this test is about.
        with self.B, store.connect() as conn:
            self.assertEqual({r[0] for r in conn.execute("SELECT id FROM channels")},
                             {"general", self.dm_ab, self.dm_bc, self.dm_ca})
            held = {r[0]: r[1] for r in conn.execute("SELECT channel_id, COUNT(*) FROM reactions GROUP BY channel_id")}
        self.assertEqual(held, {self.dm_ab: 1, self.dm_bc: 1, self.dm_ca: 1})
        self.assertEqual(self.dm_ab, store.dm_channel_id(self.a_id, self.b_id))
        self.assertEqual(self.dm_bc, store.dm_channel_id(self.b_id, self.c_id))

    def ingest_dm_ca(self):
        """Store a dm:C+A channel, one message from C and C's reaction on it, into the current gateway."""
        store.ingest({
            "from": {"gateway_id": self.c_id, "display_name": "cole"},
            "channels": [{"id": self.dm_ca, "is_dm": True,
                          "members": [{"id": self.c_id, "name": "cole"}, {"id": self.a_id, "name": "ash"}]}],
            "messages": [{"id": "leak-ca-1", "channel_id": self.dm_ca, "author_type": "human",
                          "author_name": "cole", "gateway_id": self.c_id, "gateway_name": "cole",
                          "content": "cole to ash", "created_at": "2026-11-07T12:00:00.000+00:00"}],
            "reactions": [{"message_id": "leak-ca-1", "emoji": PARTY, "gateway_id": self.c_id,
                           "active": 1, "created_at": "2026-11-07T12:00:01.000+00:00"}],
        })

    def export_on_b(self, *args, **kwargs):
        with self.B:
            return store.export_batch(*args, **kwargs)

    def assert_no_foreign(self, out):
        self.assertFalse(_ids(out["channels"]) & self.foreign, _ids(out["channels"]))
        self.assertFalse(_ids(out["messages"], "channel_id") & self.foreign)
        self.assertFalse(_ids(out["reactions"], "channel_id") & self.foreign)

    # 1
    def test_third_gateway_cannot_pull_another_pairs_dm(self):
        out = self.export_on_b(0, exclude_gateway=self.a_id, viewer_gateway=self.a_id)
        self.assertNotIn(self.dm_bc, _ids(out["channels"]))
        self.assertNotIn(self.dm_bc, _ids(out["messages"], "channel_id"))
        self.assertNotIn(self.dm_bc, _ids(out["reactions"], "channel_id"))
        self.assertFalse({self.bc_from_b, self.bc_from_c} & _ids(out["messages"]))
        self.assert_no_foreign(out)
        # Same through the real route, as A.
        with self.B:
            resp = store.handle_peer_sync({"v": store.PROTOCOL_VERSION,
                                           "from": {"gateway_id": self.a_id, "display_name": "ash"},
                                           "after_seq": 0, "after_rseq": 0})
        self.assert_no_foreign(resp)
        self.assertEqual(_ids(resp["channels"]), {"general", self.dm_ab, self.dm_ca})  # A is in dm:C+A
        # A caller in neither DM gets neither:
        stranger = self.export_on_b(0, viewer_gateway="f" * 32)
        self.assertEqual(_ids(stranger["channels"]), {"general"})

    # 2 — the regression test that matters
    def test_linked_peer_still_receives_its_own_dm(self):
        out = self.export_on_b(0, exclude_gateway=self.a_id, viewer_gateway=self.a_id)
        self.assertIn(self.dm_ab, _ids(out["channels"]))
        self.assertIn(self.ab_from_b, _ids(out["messages"]))  # A's own row is excluded as before
        reacts = [(r["message_id"], r["emoji"], r["gateway_id"]) for r in out["reactions"]]
        self.assertIn((self.ab_from_a, UP, self.b_id), reacts)
        # Without the exclusion, every dm:A+B row is there (both sides).
        full = self.export_on_b(0, viewer_gateway=self.a_id)
        self.assertTrue({self.ab_from_a, self.ab_from_b} <= _ids(full["messages"]))
        # C still gets its own DM with B.
        out_c = self.export_on_b(0, exclude_gateway=self.c_id, viewer_gateway=self.c_id)
        self.assertIn(self.dm_bc, _ids(out_c["channels"]))
        self.assertIn(self.bc_from_b, _ids(out_c["messages"]))
        self.assertIn(self.dm_ca, _ids(out_c["channels"]))  # C is a member of dm:C+A
        self.assertNotIn(self.dm_ab, _ids(out_c["channels"]))

    # 3
    def test_public_channels_and_messages_untouched(self):
        public = {}
        for who in (self.a_id, self.b_id, self.c_id):
            out = self.export_on_b(0, viewer_gateway=who)
            self.assertIn("general", _ids(out["channels"]))
            public[who] = {m["id"] for m in out["messages"] if m["channel_id"] == "general"}
            self.assertEqual(public[who], {self.gen_a, self.gen_c})
        self.assertEqual(public[self.a_id], public[self.b_id])
        self.assertEqual(public[self.b_id], public[self.c_id])

    # 4
    def test_cursor_advances_past_filtered_rows(self):
        with self.B, store.connect() as conn:
            seqs = conn.execute("SELECT seq, channel_id FROM messages ORDER BY seq").fetchall()
            rseqs = conn.execute("SELECT rseq, channel_id FROM reactions ORDER BY rseq").fetchall()
        first_foreign = min(s for s, ch in seqs if ch in self.foreign)
        cursor = first_foreign - 1
        above = [(s, ch) for s, ch in seqs if s > cursor]
        self.assertTrue(above and all(ch in self.foreign for _, ch in above), above)  # only foreign rows above
        rfirst = min(s for s, ch in rseqs if ch in self.foreign)
        rcursor = rfirst - 1
        rabove = [(s, ch) for s, ch in rseqs if s > rcursor]
        self.assertTrue(rabove and all(ch in self.foreign for _, ch in rabove), rabove)

        out = self.export_on_b(cursor, exclude_gateway=self.a_id, viewer_gateway=self.a_id, after_rseq=rcursor)
        self.assertEqual(out["messages"], [])
        self.assertEqual(out["reactions"], [])
        self.assertEqual(out["next_seq"], max(s for s, _ in above))
        self.assertEqual(out["next_rseq"], max(s for s, _ in rabove))
        self.assertIs(out["more"], False)
        self.assertIs(out["rmore"], False)

        again = self.export_on_b(out["next_seq"], exclude_gateway=self.a_id, viewer_gateway=self.a_id,
                                 after_rseq=out["next_rseq"])
        self.assertEqual(again["messages"], [])
        self.assertEqual(again["reactions"], [])
        self.assertEqual(again["next_seq"], out["next_seq"])
        self.assertEqual(again["next_rseq"], out["next_rseq"])

        # With a LIMIT that stops inside the filtered rows, the cursor still walks them once each.
        step = self.export_on_b(cursor, exclude_gateway=self.a_id, viewer_gateway=self.a_id, limit=1)
        self.assertEqual(step["messages"], [])
        self.assertEqual(step["next_seq"], above[0][0])
        self.assertIs(step["more"], True)

    # 5 — the client (push) call site
    def test_pushing_to_a_peer_drops_foreign_dm(self):
        # A holds general, dm:A+B and a dm:C+A (A is in it; B is not). A pushes to B.
        with self.A:
            self.ingest_dm_ca()
            with store.connect() as conn:
                self.assertEqual(conn.execute("SELECT remote_gateway_id FROM peer_state").fetchone()[0], self.b_id)
                conn.execute("UPDATE peer_state SET push_seq = 0, push_rseq = 0")  # re-push A's full history
        with self.B:
            b_ident = store.identity()
        sent = []

        def recording(peer, body):
            sent.append(json.loads(json.dumps(body)))
            return {"v": store.PROTOCOL_VERSION, "from": b_ident, "accepted": 0, "dropped": 0,
                    "channels": [], "messages": [], "next_seq": 0, "more": False,
                    "reactions": [], "next_rseq": 0, "rmore": False}

        store.TRANSPORT = recording
        with self.A:
            [res] = store.sync_all()
        self.assertTrue(res["ok"], res)
        self.assertEqual(len(sent), 1)
        body = sent[0]
        self.assertNotIn(self.dm_ca, _ids(body["channels"]))
        self.assertNotIn(self.dm_ca, _ids(body["messages"], "channel_id"))
        self.assertNotIn(self.dm_ca, _ids(body["reactions"], "channel_id"))
        self.assertNotIn("leak-ca-1", _ids(body["messages"]))
        self.assertEqual(_ids(body["channels"]), {"general", self.dm_ab})
        self.assertIn(self.gen_a, _ids(body["messages"]))
        self.assertIn(self.ab_from_a, _ids(body["messages"]))

    def test_first_contact_push_still_delivers_own_dm(self):
        # B links to A with a fresh peer_state (peer not identified yet) while already holding dm:A+B.
        with self.A:
            a_ident = store.identity()
        self.B.settings.update({"peer_name": "ash", "peer_url": "http://127.0.0.1:8642"})
        self.B.settings["__secrets__"]["HERMES_MULTIPLAYER_PEER_KEY"] = "k-ash"
        sent = []

        def recording(peer, body):
            sent.append(json.loads(json.dumps(body)))
            return {"v": store.PROTOCOL_VERSION, "from": a_ident, "accepted": 0, "dropped": 0,
                    "channels": [], "messages": [], "next_seq": 0, "more": False,
                    "reactions": [], "next_rseq": 0, "rmore": False}

        store.TRANSPORT = recording
        with self.B:
            [res] = store.sync_all()
        self.assertTrue(res["ok"], res)
        self.assertEqual(len(sent), 2)  # handshake round, then the round that knows the peer
        self.assertFalse(any(c.startswith("dm:") for c in _ids(sent[0]["channels"])))  # fail closed
        last = sent[1]
        self.assertIn(self.dm_ab, _ids(last["channels"]))
        self.assertIn(self.ab_from_b, _ids(last["messages"]))
        self.assertIn((self.ab_from_a, UP), {(r["message_id"], r["emoji"]) for r in last["reactions"]})
        self.assertNotIn(self.dm_bc, _ids(last["channels"]) | _ids(last["messages"], "channel_id")
                         | _ids(last["reactions"], "channel_id"))
        with self.B, store.connect() as conn:
            st = conn.execute("SELECT push_seq, remote_gateway_id FROM peer_state").fetchone()
            top = conn.execute("SELECT MAX(seq) FROM messages").fetchone()[0]
        self.assertEqual(st["remote_gateway_id"], self.a_id)
        self.assertEqual(st["push_seq"], top)

    # 6
    def test_caller_with_no_gateway_id_gets_no_dms(self):
        out = self.export_on_b(0, viewer_gateway="")
        self.assertEqual(_ids(out["channels"]), {"general"})
        self.assertEqual(_ids(out["messages"], "channel_id"), {"general"})
        self.assertEqual(out["reactions"], [])
        # The route with no "from" at all.
        with self.B:
            resp = store.handle_peer_sync({"v": store.PROTOCOL_VERSION, "after_seq": 0, "after_rseq": 0})
        self.assertEqual(_ids(resp["channels"]), {"general"})
        self.assertEqual(_ids(resp["messages"], "channel_id"), {"general"})
        self.assertEqual(resp["reactions"], [])


class TwoGatewayUnchangedTest(unittest.TestCase):
    # 7
    def test_two_gateway_topology_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            A = Gateway(root, "ash", peer="blair")
            B = Gateway(root, "blair")
            store.AUTO_SYNC = False

            def transport(peer, body):
                with B:
                    return json.loads(json.dumps(store.handle_peer_sync(json.loads(json.dumps(body)))))

            store.TRANSPORT = transport
            try:
                with A:
                    a_id = store.identity()["gateway_id"]
                with B:
                    b_id = store.identity()["gateway_id"]
                with A:
                    store.sync_all()
                    store.post_message("general", "from ash")
                    dm = store.open_dm(b_id)["id"]
                    a_dm = store.post_message(dm, "ash to blair")["id"]
                    store.sync_all()
                with B:
                    store.post_message("general", "from blair")
                    store.post_message(dm, "blair to ash")
                    store.toggle_reaction(dm, a_dm, UP)
                with A:
                    store.sync_all()

                with B:
                    out = store.export_batch(0, exclude_gateway=a_id, viewer_gateway=a_id)
                    with store.connect() as conn:
                        all_channels = {r[0] for r in conn.execute("SELECT id FROM channels")}
                        not_a = {r[0] for r in conn.execute("SELECT id FROM messages WHERE gateway_id != ?", (a_id,))}
                        r_not_a = {r[0] for r in conn.execute("SELECT id FROM reactions WHERE gateway_id != ?", (a_id,))}
                    # The pre-fix payload: same call with the membership rule switched off.
                    with mock.patch.object(store, "_dm_export_allowed", lambda *_: True):
                        before = store.export_batch(0, exclude_gateway=a_id)
                self.assertEqual(all_channels, {"general", dm})
                self.assertEqual(_ids(out["channels"]), all_channels)
                self.assertEqual(_ids(out["messages"]), not_a)
                self.assertEqual(_ids(out["reactions"]), r_not_a)
                self.assertEqual(len(r_not_a), 1)
                self.assertEqual(out, before)  # same keys, order, values, cursors
            finally:
                store.TRANSPORT = None
                store.DB_PATH_OVERRIDE = None
                store.SETTINGS_OVERRIDE = None


if __name__ == "__main__":
    unittest.main()
