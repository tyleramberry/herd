"""S-13 / TC-10: promote a private DM into a shared room ("Share to a channel").

Same two-gateway harness as ``test_store.py``: A (``tyler``) has the peer configured, B (``riley``) is
the passive side, and the transport runs the OTHER side's ``handle_peer_sync`` through a JSON round
trip. The transport routes by peer URL so the mirror test (B links back to A) works too.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, tools = _pkg.load()


class Gateway:
    def __init__(self, root: Path, name: str, peer=None):
        self.name = name
        self.db = root / f"{name}.db"
        self.settings = {"display_name": name, "__secrets__": {}}
        if peer:
            self.link(peer)

    def link(self, peer):
        self.settings.update({"peer_name": peer, "peer_url": f"http://{peer}.test:8642"})
        self.settings["__secrets__"]["HERD_PEER_KEY"] = "k-" + peer

    def __enter__(self):
        self._saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE)
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = self.db, self.settings
        return self

    def __exit__(self, *exc):
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = self._saved


class PromoteTest(unittest.TestCase):
    def setUp(self):
        self._saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.TRANSPORT, store.AUTO_SYNC)
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.A = Gateway(root, "tyler", peer="riley")
        self.B = Gateway(root, "riley")
        self.down = False
        store.AUTO_SYNC = False

        def transport(peer, body):
            if self.down:
                raise ConnectionError("unreachable")
            target = self.A if "tyler" in peer["url"] else self.B
            with target:
                return json.loads(json.dumps(store.handle_peer_sync(json.loads(json.dumps(body)))))

        store.TRANSPORT = transport

    def tearDown(self):
        (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.TRANSPORT, store.AUTO_SYNC) = self._saved
        self.tmp.cleanup()

    # --- helpers ------------------------------------------------------------------------------

    def sync(self, gw=None):
        with (gw or self.A):
            return store.sync_all()

    def open_dm(self):
        """First contact, then the DM from A. Returns the DM id."""
        self.sync()
        with self.A:
            riley = [p for p in store.list_participants() if not p["is_self"]][0]
            return store.open_dm(riley["id"])["id"]

    def dm_with_five(self):
        dm_id = self.open_dm()
        with self.A:
            store.post_message(dm_id, "one")
            store.post_message(dm_id, "two", author_type="agent")
            store.post_message(dm_id, "three")
            store.post_message(dm_id, "four", author_type="agent")
            store.post_message(dm_id, "five")
        return dm_id

    def snapshot_dm(self, gw, dm_id):
        with gw:
            ch = store.get_channel(dm_id)
            with store.connect() as conn:
                rows = conn.execute(
                    "SELECT id, content, created_at, seq FROM messages WHERE channel_id = ? ORDER BY seq",
                    (dm_id,)).fetchall()
        return ({k: ch[k] for k in ("id", "name", "is_dm", "members", "created_at")},
                [tuple(r) for r in rows])

    def room(self, gw, name="dm-share"):
        with gw:
            return store.list_messages(name)

    # --- tests --------------------------------------------------------------------------------

    def test_tc10_2_promote_copies_in_order_and_leaves_the_dm_untouched(self):
        """TC-10.2 happy path + TC-10.7 the DM is byte-identical afterwards."""
        dm_id = self.dm_with_five()
        before = self.snapshot_dm(self.A, dm_id)
        with self.A:
            dm_msgs = store.list_messages(dm_id)
            ch = store.promote_dm(dm_id, "dm-share")
        self.assertIs(ch["is_dm"], False)
        self.assertEqual(ch["id"], "dm-share")
        self.assertEqual(ch["members"], [])
        self.assertEqual(ch["message_count"], 5)
        self.assertEqual(ch["messages_copied"], 5)
        self.assertEqual(ch["promoted_from"], dm_id)
        copies = self.room(self.A)
        self.assertEqual([m["content"] for m in copies], [m["content"] for m in dm_msgs])
        self.assertEqual([m["content"] for m in copies], ["one", "two", "three", "four", "five"])
        self.assertEqual([m["author_name"] for m in copies], [m["author_name"] for m in dm_msgs])
        self.assertEqual([m["author_type"] for m in copies], [m["author_type"] for m in dm_msgs])
        self.assertTrue(all(m["origin_channel_id"] == dm_id for m in copies))
        self.assertTrue(all(m["origin_channel_id"] == "" for m in dm_msgs))
        self.assertEqual(self.snapshot_dm(self.A, dm_id), before)
        with self.A:
            listed = {c["id"]: c for c in store.list_channels()}
        self.assertFalse(listed["dm-share"]["is_dm"])
        self.assertEqual(listed["dm-share"]["message_count"], 5)
        self.assertEqual(listed[dm_id]["message_count"], 5)

    def test_tc10_5_copy_ids_are_new_deterministic_and_bounded(self):
        """TC-10.5 copies carry fresh ids (never the source id), deterministic, <= 64 chars."""
        dm_id = self.dm_with_five()
        with self.A:
            source = [m["id"] for m in store.list_messages(dm_id)]
            store.promote_dm(dm_id, "dm-share")
        copies = [m["id"] for m in self.room(self.A)]
        self.assertEqual(len(copies), 5)
        self.assertTrue(set(copies).isdisjoint(source))
        for src, cp in zip(source, copies):
            self.assertNotEqual(src, cp)
            self.assertEqual(cp, store._promoted_message_id(dm_id, src, "dm-share"))
            self.assertLessEqual(len(cp), 64)
        self.assertEqual(store._promoted_message_id(dm_id, "x" * 64, "r"),
                         store._promoted_message_id(dm_id, "x" * 64, "r"))
        self.assertLessEqual(len(store._promoted_message_id(dm_id, "x" * 64, "r")), 64)
        self.assertNotEqual(store._promoted_message_id(dm_id, source[0], "a"),
                            store._promoted_message_id(dm_id, source[0], "b"))

    def test_tc10_3_order_survives_same_millisecond_ties(self):
        """TC-10.3 source created_at kept verbatim; ties keep the DM's own order."""
        dm_id = self.open_dm()
        with self.A:
            for text in ("1", "2", "3"):
                store.post_message(dm_id, text)
            dm_msgs = store.list_messages(dm_id)
            store.promote_dm(dm_id, "dm-share")
        copies = self.room(self.A)
        self.assertEqual([m["content"] for m in copies], [m["content"] for m in dm_msgs])
        self.assertEqual([m["created_at"] for m in copies], [m["created_at"] for m in dm_msgs])
        # Force an exact tie too, independent of clock resolution (ids deliberately out of insert order).
        with self.A:
            ts = "2026-11-06T00:00:00.000+00:00"
            ids = ["b-tie", "c-tie", "a-tie"]
            store.ingest({"channels": [], "messages": [
                {"id": i, "channel_id": dm_id, "author_type": "human", "author_name": "riley",
                 "gateway_id": "gw-riley", "gateway_name": "riley", "content": i, "created_at": ts}
                for i in ids]})
            dm_order = [m["id"] for m in store.list_messages(dm_id) if m["created_at"] == ts]
            store.promote_dm(dm_id, "tie-room")
            room_order = [m["content"] for m in store.list_messages("tie-room") if m["created_at"] == ts]
        self.assertEqual(dm_order, ["a-tie", "b-tie", "c-tie"])
        self.assertEqual(room_order, dm_order)

    def test_tc10_4_promoted_room_reaches_the_other_gateway_in_one_sync_cycle(self):
        """TC-10.4 A promotes -> ONE sync -> B has the room + every copy (incl. B's own message)."""
        dm_id = self.open_dm()
        with self.A:
            store.post_message(dm_id, "from tyler")
        self.sync()
        with self.B:
            store.post_message(dm_id, "from riley")
        self.sync()
        with self.A:
            self.assertEqual([m["content"] for m in store.list_messages(dm_id)], ["from tyler", "from riley"])
            store.promote_dm(dm_id, "dm-share")
        [res] = self.sync()
        self.assertTrue(res["ok"], res)
        with self.B:
            rooms = {c["id"]: c for c in store.list_channels()}
            self.assertIn("dm-share", rooms)
            self.assertIs(rooms["dm-share"]["is_dm"], False)
            humans = {p["display_name"] for p in store.list_participants()}
        self.assertEqual(humans, {"tyler", "riley"})
        a_room = [(m["id"], m["content"], m["author_name"]) for m in self.room(self.A)]
        b_room = [(m["id"], m["content"], m["author_name"]) for m in self.room(self.B)]
        self.assertEqual(len(a_room), 2)
        self.assertEqual(b_room, a_room)
        self.assertEqual([m[2] for m in b_room], ["tyler", "riley"])

    def test_tc10_4_promote_on_b_converges_to_a(self):
        """TC-10.4 mirror: B promotes (B linked back to A) -> one sync on B -> A has room + copies."""
        dm_id = self.open_dm()
        with self.A:
            store.post_message(dm_id, "hello riley")
        self.sync()
        self.B.link("tyler")
        with self.B:
            store.post_message(dm_id, "hi tyler")
            ch = store.promote_dm(dm_id, "dm-share")
        self.assertEqual(ch["messages_copied"], 2)
        [res] = self.sync(self.B)
        self.assertTrue(res["ok"], res)
        with self.A:
            self.assertIn("dm-share", {c["id"] for c in store.list_channels()})
        self.assertEqual([m["content"] for m in self.room(self.A)], ["hello riley", "hi tyler"])
        self.assertEqual([m["id"] for m in self.room(self.A)], [m["id"] for m in self.room(self.B)])

    def test_tc10_6_replay_is_idempotent_and_reshare_is_refused(self):
        """TC-10.6 dup delivery -> one row per message; same DM + same name twice -> clean 409."""
        dm_id = self.open_dm()
        with self.A:
            store.post_message(dm_id, "from tyler")
        self.sync()
        with self.B:
            store.post_message(dm_id, "from riley")
        self.sync()
        with self.A:
            store.promote_dm(dm_id, "dm-share")
        self.sync()
        for _ in range(3):
            self.sync()
        a_ids = {m["id"] for m in self.room(self.A)}
        b_ids = {m["id"] for m in self.room(self.B)}
        self.assertEqual(len(a_ids), 2)
        self.assertEqual(a_ids, b_ids)
        for gw in (self.A, self.B):
            with gw:
                counts = {c["id"]: c["message_count"] for c in store.list_channels()}
            self.assertEqual(counts["dm-share"], 2)
            self.assertEqual(counts[dm_id], 2)
        # Duplicate delivery of the exact export payload is a no-op.
        with self.A:
            replay = store.export_batch(0)
        with self.B:
            self.assertEqual(store.ingest(json.loads(json.dumps(replay))), 0)
        with self.A:
            with self.assertRaises(store.HerdError) as e:
                store.promote_dm(dm_id, "dm-share")
            self.assertEqual(e.exception.status, 409)
            self.assertEqual(e.exception.message, "#dm-share already exists.")
            self.assertEqual(len(store.list_messages("dm-share")), 2)
            with store.connect() as conn:
                total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        self.assertEqual(total, 4)

    def test_tc10_9_edges(self):
        """TC-10.9 / TC-3.3: wrong kind, unknown ref, bad names, empty DM, peer offline."""
        dm_id = self.open_dm()
        with self.A:
            for ref, name, status in (("general", "x-room", 422), ("nobody", "x-room", 404),
                                      (dm_id, "bad/name", 422), (dm_id, "a" * 49, 422), (dm_id, "  ", 422)):
                with self.assertRaises(store.HerdError) as e:
                    store.promote_dm(ref, name)
                self.assertEqual(e.exception.status, status, (ref, name))
            self.assertNotIn("x-room", {c["id"] for c in store.list_channels()})
            # 48 chars is the limit and is accepted; the DM is still empty -> empty room, no crash.
            ch = store.promote_dm(dm_id, "a" * 48)
            self.assertEqual((ch["message_count"], ch["messages_copied"]), (0, 0))
            self.assertEqual(store.list_messages("a" * 48), [])
            store.post_message(dm_id, "while offline")
        self.down = True
        with self.A:
            ch = store.promote_dm(dm_id, "offline-room")
            self.assertEqual(ch["message_count"], 1)
        [res] = self.sync()
        self.assertFalse(res["ok"])
        with self.B:
            self.assertNotIn("offline-room", {c["id"] for c in store.list_channels()})
        self.down = False
        [res] = self.sync()
        self.assertTrue(res["ok"], res)
        self.assertEqual([m["content"] for m in self.room(self.B, "offline-room")], ["while offline"])
        with self.B:
            dm = store.get_channel(dm_id)
            self.assertTrue(dm["is_dm"])
            self.assertEqual(len(dm["members"]), 2)

    def test_tc10_11_protocol_version_bumped_and_enforced(self):
        """Protocol v2: older peers accepted, newer/garbage refused; origin_channel_id survives the wire."""
        self.assertEqual(store.PROTOCOL_VERSION, 2)
        with self.B:
            self.assertEqual(store.handle_peer_sync({"v": 1, "channels": [], "messages": []})["v"], 2)
            self.assertEqual(store.handle_peer_sync({"channels": []})["v"], 2)
            for bad in (3, "abc", 0):
                with self.assertRaises(store.HerdError) as e:
                    store.handle_peer_sync({"v": bad})
                self.assertEqual(e.exception.status, 422, bad)
            self.assertEqual(store.ingest({"something_new": 1, "channels": [], "messages": []}), 0)
        dm_id = self.open_dm()
        with self.A:
            store.post_message(dm_id, "carry me")
            store.promote_dm(dm_id, "dm-share")
            batch = json.loads(json.dumps(store.export_batch(0)))
        copies = [store._valid_message(m) for m in batch["messages"] if m["channel_id"] == "dm-share"]
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0]["origin_channel_id"], dm_id)
        # A promoted copy authored by the peer is still exported TO that peer.
        with self.A:
            riley_id = store.get_channel(dm_id)["members"]
            riley_id = [m["id"] for m in riley_id if m["name"] == "riley"][0]
            store.ingest({"channels": [], "messages": [
                {"id": "r1", "channel_id": dm_id, "author_type": "human", "author_name": "riley",
                 "gateway_id": riley_id, "gateway_name": "riley", "content": "riley's", "created_at": store._now()}]})
            store.promote_dm(dm_id, "room-two")
            out = store.export_batch(0, exclude_gateway=riley_id)
        sent = {m["id"] for m in out["messages"]}
        self.assertNotIn("r1", sent)
        self.assertIn(store._promoted_message_id(dm_id, "r1", "room-two"), sent)

    def test_tc10_replayed_mention_does_not_wake(self):
        """A replayed copy (origin_channel_id set) never wakes an agent; the control message does."""
        saved = (store.WAKE_HANDLER, store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE)
        woken = []
        try:
            store.DB_PATH_OVERRIDE = Path(self.tmp.name) / "wake.db"
            store.SETTINGS_OVERRIDE = {"display_name": "Tyler", "mention_wake": True}
            store.WAKE_HANDLER = lambda key, text: woken.append((key, text)) or True
            store._wake_times.clear()
            store.set_mention_target("ses_abc")

            def batch(mid, origin):
                m = {"id": mid, "channel_id": "general", "author_type": "human", "author_name": "Brooklyn",
                     "gateway_id": "other-gw", "gateway_name": "Brooklyn", "content": "@tyler can you look?",
                     "created_at": "2026-11-05T00:00:00Z"}
                if origin:
                    m["origin_channel_id"] = origin
                return {"from": {"gateway_id": "other-gw", "display_name": "Brooklyn"}, "channels": [],
                        "messages": [m]}

            self.assertEqual(store.ingest(batch("copy-1", "dm:a+b")), 1)
            self.assertEqual(woken, [])
            self.assertEqual(store.ingest(batch("orig-1", "")), 1)
            self.assertEqual(len(woken), 1)
            self.assertEqual(woken[0][0], "ses_abc")
        finally:
            store.WAKE_HANDLER, store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = saved
            store._wake_times.clear()

    def test_tc10_8_agent_tools_see_the_promoted_room(self):
        """TC-10.8 herd_list_channels / herd_read_channel / herd_post against the promoted room."""
        dm_id = self.dm_with_five()
        with self.A:
            store.promote_dm(dm_id, "dm-share")
            listed = json.loads(tools.herd_list_channels({}))
            self.assertTrue(listed["ok"], listed)
            room = [c for c in listed["channels"] if c["id"] == "dm-share"][0]
            self.assertEqual(room["type"], "channel")
            self.assertEqual(room["message_count"], 5)
            self.assertNotIn("members", room)
            read = json.loads(tools.herd_read_channel({"channel": "dm-share"}))
            self.assertTrue(read["ok"], read)
            self.assertEqual([m["text"] for m in read["messages"]], ["one", "two", "three", "four", "five"])
            posted = json.loads(tools.herd_post({"channel": "dm-share", "content": "x"}))
            self.assertTrue(posted["ok"], posted)
            self.assertEqual(posted["message"]["channel_id"], "dm-share")
            counts = {c["id"]: c["message_count"] for c in store.list_channels()}
        self.assertEqual(counts["dm-share"], 6)
        self.assertEqual(counts[dm_id], 5)

    def test_tc10_10_reactions_are_not_copied(self):
        """TC-10.10 documented drop: reactions stay on the DM's messages; copies start with none."""
        if not hasattr(store, "toggle_reaction"):
            self.skipTest("S-12 reactions are not on this base")
        dm_id = self.open_dm()
        with self.A:
            m = store.post_message(dm_id, "react to me")
            store.toggle_reaction(dm_id, m["id"], "👍")
            store.promote_dm(dm_id, "dm-share")
            [dm_msg] = store.list_messages(dm_id)
            [copy] = store.list_messages("dm-share")
        self.assertEqual([(r["emoji"], r["count"]) for r in dm_msg["reactions"]], [("👍", 1)])
        self.assertEqual(copy["reactions"], [])


if __name__ == "__main__":
    unittest.main()
