"""S-11 threads: storage, sync, HTTP routes and agent tools (reply-in-thread)."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, tools = _pkg.load()


class Gateway:
    """Point the store at one gateway's database/settings (same idea as test_store.Gateway)."""

    def __init__(self, root: Path, name: str, peer=None):
        self.db = root / f"{name}.db"
        self.settings = {"display_name": name, "__secrets__": {}}
        if peer:
            self.settings.update({"peer_name": peer, "peer_url": "http://127.0.0.1:8642"})  # loopback: allowed by the default cleartext policy
            self.settings["__secrets__"]["HERMES_MULTIPLAYER_PEER_KEY"] = "k-" + peer

    def __enter__(self):
        self._saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE)
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = self.db, self.settings
        return self

    def __exit__(self, *exc):
        store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE = self._saved


class ThreadBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.A = Gateway(self.root, "tyler", peer="riley")
        self.B = Gateway(self.root, "riley")
        store.AUTO_SYNC = False

        def transport(peer, body):
            with self.B:
                return json.loads(json.dumps(store.handle_peer_sync(json.loads(json.dumps(body)))))

        store.TRANSPORT = transport

    def tearDown(self):
        store.TRANSPORT = None
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        self.tmp.cleanup()

    def sync(self):
        with self.A:
            return store.sync_all()


class StorageTest(ThreadBase):
    def test_reply_hidden_from_channel_and_counted_on_parent(self):
        with self.A:
            parent = store.post_message("general", "parent")
            reply = store.post_message("general", "reply", thread_parent_id=parent["id"])
            self.assertEqual(reply["thread_parent_id"], parent["id"])
            top = store.list_messages("general")
        self.assertEqual([m["content"] for m in top], ["parent"])
        self.assertIsNone(top[0]["thread_parent_id"])
        self.assertEqual(top[0]["reply_count"], 1)
        self.assertEqual(top[0]["last_reply_at"], reply["created_at"])

    def test_no_replies_means_zero_and_none(self):
        with self.A:
            store.post_message("general", "solo")
            [m] = store.list_messages("general")
        self.assertEqual((m["reply_count"], m["last_reply_at"]), (0, None))

    def test_after_seq_cursor_view_also_hides_replies(self):
        with self.A:
            parent = store.post_message("general", "parent")
            store.post_message("general", "reply", thread_parent_id=parent["id"])
            later = store.post_message("general", "later")
            got = store.list_messages("general", after_seq=parent["seq"])
        self.assertEqual([m["content"] for m in got], ["later"])
        self.assertEqual(got[0]["id"], later["id"])

    def test_list_thread_oldest_first_and_from_reply_id(self):
        with self.A:
            parent = store.post_message("general", "parent")
            r1 = store.post_message("general", "r1", thread_parent_id=parent["id"])
            r2 = store.post_message("general", "r2", thread_parent_id=parent["id"])
            t = store.list_thread(parent["id"])
            self.assertEqual(t["parent"]["id"], parent["id"])
            self.assertEqual(t["parent"]["reply_count"], 2)
            self.assertEqual([m["content"] for m in t["replies"]], ["r1", "r2"])
            self.assertEqual(store.list_thread(r2["id"]), t)
            self.assertEqual(store.list_thread(r1["id"])["parent"]["id"], parent["id"])

    def test_reply_to_a_reply_attaches_to_root(self):
        with self.A:
            parent = store.post_message("general", "parent")
            r1 = store.post_message("general", "r1", thread_parent_id=parent["id"])
            inner = store.post_message("general", "inner", thread_parent_id=r1["id"])
            self.assertEqual(inner["thread_parent_id"], parent["id"])
            [top] = store.list_messages("general")
            self.assertEqual(top["reply_count"], 2)
            t = store.list_thread(parent["id"])
            self.assertEqual(t["replies"][-1]["reply_count"], 0)
            self.assertEqual([m["content"] for m in t["replies"]], ["r1", "inner"])

    def test_unknown_parent_is_404(self):
        with self.A:
            with self.assertRaises(store.MultiplayerError) as e:
                store.post_message("general", "x", thread_parent_id="nope")
            self.assertEqual(e.exception.status, 404)
            self.assertIn("No message with id 'nope' to reply to.", e.exception.message)
            with self.assertRaises(store.MultiplayerError) as e:
                store.list_thread("nope")
            self.assertEqual(e.exception.status, 404)
            long_id = "z" * 500
            with self.assertRaises(store.MultiplayerError) as e:
                store.post_message("general", "x", thread_parent_id=long_id)
            self.assertLess(len(e.exception.message), 200)

    def test_parent_in_other_channel_is_422(self):
        with self.A:
            store.create_channel("design")
            parent = store.post_message("design", "over there")
            with self.assertRaises(store.MultiplayerError) as e:
                store.post_message("general", "x", thread_parent_id=parent["id"])
            self.assertEqual(e.exception.status, 422)
            self.assertEqual(e.exception.message, "You can only reply in a thread within the same channel.")

    def test_empty_string_parent_is_top_level(self):
        with self.A:
            for blank in ("", "   ", None):
                m = store.post_message("general", "hi " + repr(blank), thread_parent_id=blank)
                self.assertIsNone(m["thread_parent_id"])
            self.assertEqual(len(store.list_messages("general")), 3)

    def test_get_message(self):
        with self.A:
            m = store.post_message("general", "hello")
            got = store.get_message(m["id"])
            self.assertEqual(got["content"], "hello")
            self.assertEqual(got["channel_id"], "general")
            self.assertIsNone(store.get_message("missing"))

    def test_migration_adds_column_to_old_db(self):
        old = self.root / "old.db"
        conn = sqlite3.connect(str(old))
        conn.executescript("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE channels (id TEXT PRIMARY KEY, name TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '',
                is_dm INTEGER NOT NULL DEFAULT 0, members TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
            CREATE TABLE messages (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                channel_id TEXT NOT NULL, author_type TEXT NOT NULL, author_name TEXT NOT NULL,
                gateway_id TEXT NOT NULL, gateway_name TEXT NOT NULL DEFAULT '', content TEXT NOT NULL,
                created_at TEXT NOT NULL);
            CREATE INDEX idx_messages_channel ON messages(channel_id, created_at, id);
            INSERT INTO channels VALUES ('general', 'general', '', 0, '[]', '2026-01-01T00:00:00.000+00:00');
            INSERT INTO messages(id, channel_id, author_type, author_name, gateway_id, content, created_at)
                VALUES ('old1', 'general', 'human', 'tyler', 'g', 'from before', '2026-01-01T00:00:01.000+00:00');
        """)
        conn.commit()
        conn.close()
        # Fresh path => the process-level "initialized" cache has not seen it.
        with Gateway(self.root, "old") as _:
            store.DB_PATH_OVERRIDE = old
            [m] = store.list_messages("general")
            self.assertEqual((m["id"], m["reply_count"]), ("old1", 0))
            reply = store.post_message("general", "after upgrade", thread_parent_id="old1")
            self.assertEqual(reply["thread_parent_id"], "old1")
            self.assertEqual(store.list_thread("old1")["replies"][0]["content"], "after upgrade")
        conn = sqlite3.connect(str(old))
        names = {r[1] for r in conn.execute("PRAGMA index_list(messages)")}
        conn.close()
        self.assertIn("idx_messages_thread", names)


class SyncTest(ThreadBase):
    def test_round_trip_both_directions(self):
        with self.A:
            parent = store.post_message("general", "question?")
        self.assertTrue(self.sync()[0]["ok"])
        with self.B:
            [top] = store.list_messages("general")
            self.assertEqual(top["id"], parent["id"])
            store.post_message("general", "answer", thread_parent_id=parent["id"])
        self.assertTrue(self.sync()[0]["ok"])
        with self.A:
            t = store.list_thread(parent["id"])
            self.assertEqual([m["content"] for m in t["replies"]], ["answer"])
            self.assertEqual(t["replies"][0]["author_name"], "riley")
            self.assertEqual([m["content"] for m in store.list_messages("general")], ["question?"])
            self.assertEqual(store.list_messages("general")[0]["reply_count"], 1)

    def test_reply_from_a_to_b(self):
        with self.A:
            parent = store.post_message("general", "p")
            store.post_message("general", "r", thread_parent_id=parent["id"])
        self.assertTrue(self.sync()[0]["ok"])
        with self.B:
            self.assertEqual([m["content"] for m in store.list_thread(parent["id"])["replies"]], ["r"])

    def test_valid_message_thread_parent_id(self):
        base = {"id": "m1", "channel_id": "general", "content": "x"}
        self.assertEqual(store._valid_message({**base, "thread_parent_id": "p" * 64})["thread_parent_id"], "p" * 64)
        self.assertEqual(store._valid_message({**base, "thread_parent_id": "p" * 100})["thread_parent_id"], "p" * 64)
        self.assertEqual(store._valid_message({**base, "thread_parent_id": ""})["thread_parent_id"], "")
        self.assertEqual(store._valid_message(base)["thread_parent_id"], "")

    def test_export_includes_thread_parent_id(self):
        with self.A:
            parent = store.post_message("general", "p")
            store.post_message("general", "r", thread_parent_id=parent["id"])
            rows = store.export_batch(0)["messages"]
        self.assertEqual([r["thread_parent_id"] for r in rows], [None, parent["id"]])

    def test_ingest_stores_empty_string_as_null(self):
        with self.A:
            store.ingest({"channels": [{"id": "general"}], "messages": [
                {"id": "m1", "channel_id": "general", "content": "x", "thread_parent_id": ""}]})
            self.assertIsNone(store.get_message("m1")["thread_parent_id"])

    def test_orphan_reply_resolves_when_parent_arrives(self):
        with self.A:
            reply = {"id": "r1", "channel_id": "general", "content": "reply", "thread_parent_id": "p1",
                     "created_at": "2026-01-01T00:00:02.000+00:00"}
            parent = {"id": "p1", "channel_id": "general", "content": "parent",
                      "created_at": "2026-01-01T00:00:01.000+00:00"}
            self.assertEqual(store.ingest({"messages": [reply]}), 1)
            self.assertEqual(store.list_messages("general"), [])  # reply stays hidden, parent unknown
            self.assertEqual(store.ingest({"messages": [parent]}), 1)
            [top] = store.list_messages("general")
            self.assertEqual((top["id"], top["reply_count"]), ("p1", 1))
            self.assertEqual([m["id"] for m in store.list_thread("p1")["replies"]], ["r1"])

    def test_ingest_drops_cross_channel_parent(self):
        # TC-7.8: a reply claiming a root that lives in another channel renders in no
        # channel and no thread view, so ingest drops it (the local path is a loud 422).
        with self.A:
            store.ingest({"channels": [{"id": "general"}, {"id": "ops"}],
                          "messages": [{"id": "R", "channel_id": "general", "content": "root"}]})
            self.assertEqual(store.ingest({"messages": [
                {"id": "X", "channel_id": "ops", "content": "claims general root",
                 "thread_parent_id": "R"}]}), 0)
            self.assertIsNone(store.get_message("X"))
            self.assertEqual(store.list_thread("R")["replies"], [])

    def test_ingest_flattens_nested_parent_to_root(self):
        # A non-conforming peer may send a reply-to-a-reply; the local path flattens it
        # onto the root, so ingest resolves it the same way, keeping both sides equal.
        with self.A:
            store.ingest({"channels": [{"id": "general"}], "messages": [
                {"id": "p1", "channel_id": "general", "content": "root"},
                {"id": "c1", "channel_id": "general", "content": "child",
                 "thread_parent_id": "p1"}]})
            self.assertEqual(store.ingest({"messages": [
                {"id": "g1", "channel_id": "general", "content": "grandchild",
                 "thread_parent_id": "c1"}]}), 1)
            self.assertEqual(store.get_message("g1")["thread_parent_id"], "p1")
            self.assertEqual([m["id"] for m in store.list_thread("p1")["replies"]], ["c1", "g1"])


@unittest.skipUnless(find_spec("fastapi"), "fastapi not installed")
class ApiTest(ThreadBase):
    def setUp(self):
        super().setUp()
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        spec_path = _pkg.ROOT / "dashboard" / "plugin_api.py"
        import importlib.util

        spec = importlib.util.spec_from_file_location("hermes_multiplayer.dashboard.plugin_api", spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        app = FastAPI()
        app.include_router(mod.router)
        self.client = TestClient(app)
        self.gw = self.A.__enter__()

    def tearDown(self):
        self.A.__exit__(None, None, None)
        super().tearDown()

    def test_post_reply_and_get_thread(self):
        parent = self.client.post("/channels/general/messages", json={"content": "p"}).json()
        r = self.client.post("/channels/general/messages",
                             json={"content": "r", "thread_parent_id": parent["id"]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["thread_parent_id"], parent["id"])
        t = self.client.get(f"/messages/{parent['id']}/thread").json()
        self.assertEqual(t["parent"]["reply_count"], 1)
        self.assertEqual([m["content"] for m in t["replies"]], ["r"])
        listing = self.client.get("/channels/general/messages").json()
        self.assertEqual([m["content"] for m in listing], ["p"])
        self.assertEqual(listing[0]["reply_count"], 1)
        self.assertIsNone(listing[0]["thread_parent_id"])
        self.assertIsNotNone(listing[0]["last_reply_at"])

    def test_bad_parent_is_404(self):
        r = self.client.post("/channels/general/messages",
                             json={"content": "r", "thread_parent_id": "ghost"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client.get("/messages/ghost/thread").status_code, 404)

    def test_notify_payload_carries_thread_parent_id(self):
        events = []
        saved = store._notify
        store._notify = lambda event, payload: events.append((event, payload))
        try:
            parent = self.client.post("/channels/general/messages", json={"content": "p"}).json()
            self.client.post("/channels/general/messages",
                             json={"content": "r", "thread_parent_id": parent["id"]})
        finally:
            store._notify = saved
        self.assertEqual(events[0][1]["thread_parent_id"], None)
        self.assertEqual(events[1][1]["thread_parent_id"], parent["id"])
        self.assertEqual(events[1][1]["channel_id"], "general")


class ToolsTest(ThreadBase):
    def setUp(self):
        super().setUp()
        self.A.__enter__()

    def tearDown(self):
        self.A.__exit__(None, None, None)
        super().tearDown()

    def test_multiplayer_post_reply_to(self):
        parent = store.post_message("general", "task?")
        out = json.loads(tools.multiplayer_post({"reply_to": parent["id"], "content": "done"}))
        self.assertTrue(out["ok"], out)
        reply = store.get_message(out["message"]["id"])
        self.assertEqual(reply["thread_parent_id"], parent["id"])
        self.assertEqual(reply["author_type"], "agent")
        out2 = json.loads(tools.multiplayer_post({"channel": "#general", "reply_to": parent["id"], "content": "again"}))
        self.assertTrue(out2["ok"], out2)

    def test_multiplayer_post_reply_to_unknown(self):
        out = json.loads(tools.multiplayer_post({"reply_to": "ghost", "content": "x"}))
        self.assertEqual(out, {"ok": False, "error": "No message with id 'ghost' to reply to."})

    def test_multiplayer_post_reply_to_disagreeing_channel(self):
        store.create_channel("design")
        parent = store.post_message("general", "p")
        out = json.loads(tools.multiplayer_post({"channel": "design", "reply_to": parent["id"], "content": "x"}))
        self.assertEqual(out, {"ok": False, "error": "That message is in a different channel."})

    def test_multiplayer_post_still_requires_channel_without_reply_to(self):
        out = json.loads(tools.multiplayer_post({"content": "x"}))
        self.assertFalse(out["ok"])

    def test_read_channel_has_id_and_replies_and_thread(self):
        parent = store.post_message("general", "p")
        store.post_message("general", "r1", thread_parent_id=parent["id"])
        read = json.loads(tools.multiplayer_read_channel({"channel": "general"}))
        [m] = read["messages"]
        self.assertEqual((m["id"], m["replies"], m["text"]), (parent["id"], 1, "p"))
        thread = json.loads(tools.multiplayer_read_channel({"channel": "general", "thread": parent["id"]}))
        self.assertTrue(thread["ok"])
        self.assertNotIn("messages", thread)
        self.assertEqual(thread["thread"]["parent"]["id"], parent["id"])
        self.assertEqual(thread["thread"]["parent"]["replies"], 1)
        [r] = thread["thread"]["replies"]
        self.assertEqual((r["text"], r["replies"], r["author_type"]), ("r1", 0, "human"))
        for key in ("author", "author_type", "from_machine", "at", "text", "id", "replies"):
            self.assertIn(key, r)

    def test_read_thread_unknown(self):
        out = json.loads(tools.multiplayer_read_channel({"channel": "general", "thread": "ghost"}))
        self.assertFalse(out["ok"])

    def test_schemas_document_new_params(self):
        from hermes_multiplayer import schemas

        self.assertIn("reply_to", schemas.MULTIPLAYER_POST["parameters"]["properties"])
        self.assertIn("thread", schemas.MULTIPLAYER_READ_CHANNEL["parameters"]["properties"])
        self.assertNotIn("reply_to", schemas.MULTIPLAYER_POST["parameters"].get("required", []))


if __name__ == "__main__":
    unittest.main()
