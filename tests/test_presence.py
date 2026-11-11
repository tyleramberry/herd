"""Track 2: unread counts across peers, the teammate status phrase, and the incoming-message announcement.

Two real gateways (the same harness as test_store.TwoGatewayTest) talk through the JSON round trip, so the counts
and the status are checked through the sync path, not by poking tables.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402
from test_store import Gateway  # noqa: E402

_, store, _tools = _pkg.load()


class TwoGateways(unittest.TestCase):
    notify = False
    prime = False  # True: one sync before the test, so the peer's history is behind us (first contact is history)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.A = Gateway(root, "tyler", peer="riley")
        self.B = Gateway(root, "riley")
        self.A.settings["notify_messages"] = self.notify
        self.events = []
        self._saved = (store.AUTO_SYNC, store.TRANSPORT, store._notify)
        store.AUTO_SYNC = False
        store._notify = lambda event, payload: self.events.append((event, payload))

        def transport(peer, body):
            with self.B:
                return json.loads(json.dumps(store.handle_peer_sync(json.loads(json.dumps(body)))))
        store.TRANSPORT = transport
        store._peer_status.clear()
        store._status = None  # this gateway's own phrase is process-wide; both gateways here share one process
        if self.prime:
            self.sync()
            self.events.clear()

    def tearDown(self):
        store.AUTO_SYNC, store.TRANSPORT, store._notify = self._saved
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        store._peer_status.clear()
        store._status = None
        self.tmp.cleanup()

    def sync(self):
        with self.A:
            return store.sync_all()

    def post(self, gw, text, channel="general"):
        with gw:
            return store.post_message(channel, text, author_type="human")

    def unread(self, gw=None, channel="general"):
        with (gw or self.A):
            return {c["id"]: c["unread"] for c in store.list_channels()}[channel]

    def mark_read(self, channel="general"):
        with self.A:
            store.mark_read(channel)


class UnreadAcrossPeersTest(TwoGateways):
    def test_a_teammate_post_counts_and_an_own_post_does_not(self):
        self.post(self.B, "from riley one")
        self.sync()
        self.assertEqual(self.unread(), 1)
        self.post(self.A, "my own reply")
        self.assertEqual(self.unread(), 1)

    def test_reading_clears_and_later_posts_count_again(self):
        self.post(self.B, "one")
        self.post(self.B, "two")
        self.sync()
        self.assertEqual(self.unread(), 2)
        self.mark_read()
        self.assertEqual(self.unread(), 0)
        self.post(self.B, "three")
        self.sync()
        self.assertEqual(self.unread(), 1)

    def test_a_replayed_batch_is_counted_once(self):
        self.post(self.B, "once")
        self.sync()
        self.assertEqual(self.unread(), 1)
        # Force the whole history to be pulled again (a cursor reset, or a peer that resends its window).
        with self.A:
            with store.connect() as conn:
                conn.execute("UPDATE peer_state SET pull_seq = 0, pull_rseq = 0")
        self.sync()
        self.assertEqual(self.unread(), 1)

    def test_an_out_of_order_arrival_still_counts(self):
        # Riley posts a row whose created_at is OLDER than one A already holds; it is still new to A.
        with self.A:
            store.ingest({"from": {"gateway_id": "riley-gw", "display_name": "riley"}, "channels": [], "messages": [
                {"id": "late-1", "channel_id": "general", "author_type": "human", "author_name": "riley",
                 "gateway_id": "riley-gw", "gateway_name": "riley", "content": "newer",
                 "created_at": "2026-11-05T12:00:00Z"}]}, suppress_wakes=True)
            store.ingest({"from": {"gateway_id": "riley-gw", "display_name": "riley"}, "channels": [], "messages": [
                {"id": "late-0", "channel_id": "general", "author_type": "human", "author_name": "riley",
                 "gateway_id": "riley-gw", "gateway_name": "riley", "content": "older, arrives later",
                 "created_at": "2026-11-05T08:00:00Z"}]}, suppress_wakes=True)
        self.assertEqual(self.unread(), 2)

    def test_channels_are_counted_separately(self):
        with self.A:
            store.create_channel("ops", "")
        with self.B:
            store.create_channel("ops", "")  # both people hold the channel before either posts to it
        self.post(self.B, "general note")
        self.post(self.B, "ops note", channel="ops")
        self.sync()
        with self.A:
            counts = {c["id"]: c["unread"] for c in store.list_channels()}
        self.assertEqual(counts["general"], 1)
        self.assertEqual(counts["ops"], 1)

    def test_read_state_survives_a_restart(self):
        self.post(self.B, "before restart")
        self.sync()
        self.mark_read()
        store._initialized.clear()  # a new process re-reads the schema from disk
        self.assertEqual(self.unread(), 0)
        self.post(self.B, "after restart")
        self.sync()
        self.assertEqual(self.unread(), 1)

    def test_an_upgrade_starts_existing_channels_read(self):
        self.post(self.B, "old history")
        self.sync()
        with self.A:
            with store.connect() as conn:
                conn.execute("DROP TABLE read_cursors")  # as if this database predates read state
            store._initialized.clear()
        self.assertEqual(self.unread(), 0)  # existing history is not an unread flood on upgrade
        self.post(self.B, "new since upgrade")
        self.sync()
        self.assertEqual(self.unread(), 1)

    def test_marking_an_unknown_channel_is_a_404(self):
        with self.A:
            with self.assertRaises(store.MultiplayerError) as ctx:
                store.mark_read("nowhere")
        self.assertEqual(ctx.exception.status, 404)


class PeerStatusTest(TwoGateways):
    def test_the_phrase_reaches_the_peer(self):
        with self.A:
            store.set_status("writing the code")
        self.sync()
        with self.B:
            [entry] = store.peer_status_list()
        self.assertEqual(entry["phrase"], "writing the code")
        self.assertEqual(entry["agent"], "tyler")
        self.assertEqual(entry["name"], "tyler")

    def test_the_sync_request_carries_the_status_field(self):
        seen = []
        real = store.TRANSPORT

        def spy(peer, body):
            seen.append(body.get("status"))
            return real(peer, body)
        store.TRANSPORT = spy
        with self.A:
            store.set_status("reviewing")
        self.sync()
        self.assertIn({"phrase": "reviewing", "agent": "tyler"}, seen)

    def test_nothing_is_sent_when_no_phrase_is_set(self):
        with self.A:
            self.assertIsNone(store.status_for_peers())

    def test_a_status_is_not_relayed_on(self):
        with self.A:
            store.set_status("done")
        self.sync()
        self.assertEqual(store.peer_status_list()[0]["phrase"], "done")  # the receiving side holds it...
        # ...but B's own process has no phrase of its own, so its sync requests carry none, and A's never leaves.
        store._status = None
        with self.B:
            self.assertIsNone(store.status_for_peers())

    def test_a_malformed_phrase_clears_that_peer_only(self):
        store._record_peer_status({"gateway_id": "gw-x", "display_name": "x"}, {"phrase": "writing the code"})
        store._record_peer_status({"gateway_id": "gw-y", "display_name": "y"}, {"phrase": "writing the code"})
        store._record_peer_status({"gateway_id": "gw-x", "display_name": "x"}, {"phrase": "rm -rf /"})
        self.assertEqual([e["gateway_id"] for e in store.peer_status_list()], ["gw-y"])

    def test_a_missing_status_field_is_fine(self):
        store._record_peer_status({"gateway_id": "gw-old", "display_name": "old"}, None)
        self.assertEqual(store.peer_status_list(), [])

    def test_a_phrase_expires_with_the_ttl(self):
        store._record_peer_status({"gateway_id": "gw-z", "display_name": "z"}, {"phrase": "idle", "agent": "z"})
        self.assertEqual(len(store.peer_status_list()), 1)
        later = time.time() + store.STATUS_TTL_S + 1
        self.assertEqual(store.peer_status_list(now=later), [])

    def test_the_status_block_is_in_status(self):
        store._record_peer_status({"gateway_id": "gw-s", "display_name": "s"}, {"phrase": "done", "agent": "s"})
        with self.A:
            st = store.status()
        self.assertEqual(st["peer_status"][0]["phrase"], "done")
        self.assertIn("notify", st)


class FirstContactAnnouncementTest(TwoGateways):
    notify = True  # no priming: the very first sync is first contact

    def test_history_at_first_contact_is_not_announced(self):
        self.post(self.B, "history from before we linked")
        self.sync()  # the peer's first pass is history, not news
        self.assertEqual([p for e, p in self.events if e == "incoming.messages"], [])
        self.post(self.B, "a real new one")
        self.sync()
        announced = [i["preview"] for e, p in self.events if e == "incoming.messages" for i in p["items"]]
        self.assertEqual(announced, ["a real new one"])


class IncomingAnnouncementTest(TwoGateways):
    notify = True
    prime = True

    def incoming(self):
        return [p for e, p in self.events if e == "incoming.messages"]

    def test_a_teammate_post_is_announced_when_notify_is_on(self):
        self.post(self.B, "heads up: build is green")
        self.sync()
        [payload] = self.incoming()
        self.assertEqual(payload["count"], 1)
        item = payload["items"][0]
        self.assertEqual(item["channel_name"], "general")
        self.assertEqual(item["author_name"], "riley")
        self.assertIn("build is green", item["preview"])
        self.assertFalse(item["mention"])

    def test_nothing_is_announced_when_notify_is_off(self):
        self.A.settings["notify_messages"] = False
        self.post(self.B, "quiet please")
        self.sync()
        self.assertEqual(self.incoming(), [])

    def test_my_own_posts_are_not_announced(self):
        self.post(self.A, "I posted this")
        self.sync()
        self.assertEqual(self.incoming(), [])

    def test_a_replayed_batch_is_not_announced_twice(self):
        self.post(self.B, "only once please")
        self.sync()
        with self.A:
            with store.connect() as conn:
                conn.execute("UPDATE peer_state SET pull_seq = 0, pull_rseq = 0")
        self.sync()
        self.assertEqual(len(self.incoming()), 1)

    def test_mentions_are_flagged(self):
        self.post(self.B, "@tyler can you look")
        self.sync()
        self.assertTrue(self.incoming()[0]["items"][0]["mention"])

    def test_a_burst_is_capped_and_counted(self):
        for i in range(store.NOTIFY_MAX_ITEMS + 2):
            self.post(self.B, f"burst {i}")
        self.sync()
        [payload] = self.incoming()
        self.assertEqual(payload["count"], store.NOTIFY_MAX_ITEMS + 2)
        self.assertEqual(len(payload["items"]), store.NOTIFY_MAX_ITEMS)

    def test_the_preview_is_one_short_line(self):
        self.post(self.B, "line one\nline two " + "x" * 300)
        self.sync()
        preview = self.incoming()[0]["items"][0]["preview"]
        self.assertNotIn("\n", preview)
        self.assertLessEqual(len(preview), 120)

    def test_notify_flag_defaults_off(self):
        self.A.settings.pop("notify_messages")
        with self.A:
            self.assertFalse(store.notify_enabled())


if __name__ == "__main__":
    unittest.main()
