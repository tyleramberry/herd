"""S-16 / F4: an agent's answer links to the Kanban board (explicit task_id, read-only title)."""
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

try:  # the route test is the badge's real transport; skip cleanly where fastapi isn't installed
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # noqa: BLE001
    FastAPI = TestClient = None

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

hermes_multiplayer, store, tools = _pkg.load()
from hermes_multiplayer.dashboard import kanban_tasks  # noqa: E402

TITLE = "S-16: Agent response links to the Kanban board"


def make_kanban_db(path: Path, rows=None) -> Path:
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, title TEXT)")
        conn.executemany("INSERT INTO tasks(id, title) VALUES (?, ?)",
                         rows if rows is not None else [("t_e7741438", TITLE), ("t_other001", "Another task")])
        conn.commit()
    finally:
        conn.close()
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class KanbanBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._saved = (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC,
                       kanban_tasks.DB_PATH_OVERRIDE, kanban_tasks.hermes_root)
        store.DB_PATH_OVERRIDE = self.root / "hermes-multiplayer.db"
        store.SETTINGS_OVERRIDE = {"display_name": "tyler", "__secrets__": {}}
        store.AUTO_SYNC = False
        kanban_tasks.DB_PATH_OVERRIDE = None

    def tearDown(self):
        (store.DB_PATH_OVERRIDE, store.SETTINGS_OVERRIDE, store.AUTO_SYNC,
         kanban_tasks.DB_PATH_OVERRIDE, kanban_tasks.hermes_root) = self._saved
        self.tmp.cleanup()


class NormalizeTest(unittest.TestCase):
    def test_normalize_task_id(self):
        self.assertEqual(kanban_tasks.normalize_task_id("t_e7741438"), "t_e7741438")  # control
        for bad in ("", None, 123, "e7741438", "t_", "t_ ", "t_" + "a" * 70, "../t_abc", "x t_ab",
                    "t_ab c", "T_AB"):
            with self.subTest(bad=bad):
                self.assertIsNone(kanban_tasks.normalize_task_id(bad))
        self.assertEqual(kanban_tasks.normalize_task_id(" t_ab "), "t_ab")


class TaskTitleTest(KanbanBase):
    def test_title_lookup_and_soft_degrade(self):
        db = make_kanban_db(self.root / "kanban.db")
        kanban_tasks.DB_PATH_OVERRIDE = db
        self.assertEqual(kanban_tasks.task_title("t_e7741438"), TITLE)  # control: exact title
        self.assertIsNone(kanban_tasks.task_title("t_missing1"))
        self.assertIsNone(kanban_tasks.task_title("nope"))

    def test_blank_title_is_none(self):
        kanban_tasks.DB_PATH_OVERRIDE = make_kanban_db(
            self.root / "kanban.db", [("t_blank001", "   "), ("t_empty001", ""), ("t_null0001", None)])
        for tid in ("t_blank001", "t_empty001", "t_null0001"):
            self.assertIsNone(kanban_tasks.task_title(tid))

    def test_no_tasks_table(self):
        db = self.root / "kanban.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE other(x)")
        conn.commit()
        conn.close()
        kanban_tasks.DB_PATH_OVERRIDE = db
        self.assertIsNone(kanban_tasks.task_title("t_e7741438"))

    def test_missing_file_is_not_created(self):
        db = self.root / "absent.db"
        kanban_tasks.DB_PATH_OVERRIDE = db
        self.assertIsNone(kanban_tasks.task_title("t_e7741438"))
        self.assertFalse(db.exists())

    def test_garbage_file(self):
        db = self.root / "kanban.db"
        db.write_bytes(b"not a database!!")  # 16 bytes
        kanban_tasks.DB_PATH_OVERRIDE = db
        self.assertIsNone(kanban_tasks.task_title("t_e7741438"))

    def test_directory_as_file(self):
        d = self.root / "kanban.db"
        d.mkdir()
        kanban_tasks.DB_PATH_OVERRIDE = d
        self.assertIsNone(kanban_tasks.task_title("t_e7741438"))

    def test_read_only_proof(self):
        db = make_kanban_db(self.root / "kanban.db")
        kanban_tasks.DB_PATH_OVERRIDE = db
        before = sha(db)
        self.assertEqual(kanban_tasks.task_title("t_e7741438"), TITLE)
        self.assertEqual(kanban_tasks.task_title("t_other001"), "Another task")
        self.assertEqual(sha(db), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir() if p.name.startswith("kanban.db")),
                         ["kanban.db"])  # no -wal / -journal appeared

    def test_task_link_never_raises(self):
        kanban_tasks.DB_PATH_OVERRIDE = make_kanban_db(self.root / "kanban.db")
        ok = kanban_tasks.task_link("t_e7741438")
        self.assertEqual((ok["task_id"], ok["valid"], ok["title"]), ("t_e7741438", True, TITLE))
        bad = kanban_tasks.task_link("nope")
        self.assertEqual((bad["task_id"], bad["valid"], bad["title"]), ("", False, None))


class PathResolutionTest(KanbanBase):
    def setUp(self):
        super().setUp()
        self.hroot = self.root / "hermes"
        (self.hroot / "kanban").mkdir(parents=True)
        kanban_tasks.hermes_root = lambda: self.hroot

    def board(self, slug="multiplayer"):
        d = self.hroot / "kanban" / "boards" / slug
        d.mkdir(parents=True)
        return make_kanban_db(d / "kanban.db")

    def test_current_board(self):
        db = self.board("multiplayer")
        (self.hroot / "kanban" / "current").write_text("multiplayer\n")
        self.assertEqual(kanban_tasks.board_slug(), "multiplayer")
        self.assertEqual(kanban_tasks.kanban_db_path(), db)

    def test_malformed_current_falls_back(self):
        legacy = make_kanban_db(self.hroot / "kanban.db")
        for text in ("../evil", ""):
            with self.subTest(text=text):
                (self.hroot / "kanban" / "current").write_text(text)
                self.assertEqual(kanban_tasks.board_slug(), "default")
                self.assertEqual(kanban_tasks.kanban_db_path(), legacy)

    def test_missing_board_file_uses_root_db(self):
        legacy = make_kanban_db(self.hroot / "kanban.db")
        (self.hroot / "kanban" / "current").write_text("multiplayer\n")
        self.assertEqual(kanban_tasks.kanban_db_path(), legacy)

    def test_nothing_present(self):
        (self.hroot / "kanban" / "current").write_text("multiplayer\n")
        self.assertIsNone(kanban_tasks.kanban_db_path())
        self.assertFalse((self.hroot / "kanban.db").exists())

    def test_no_root(self):
        kanban_tasks.hermes_root = lambda: None
        self.assertIsNone(kanban_tasks.kanban_db_path())
        self.assertEqual(kanban_tasks.board_slug(), "default")


class StoreTest(KanbanBase):
    def test_post_with_task_id(self):
        stored = store.post_message("general", "x", author_type="agent", task_id="t_e7741438")
        self.assertEqual(stored["task_id"], "t_e7741438")
        with self.assertRaises(store.MultiplayerError) as cm:
            store.post_message("general", "x", author_type="agent", task_id="nope")
        self.assertEqual(cm.exception.status, 422)
        self.assertIsNone(store.post_message("general", "plain", author_type="agent")["task_id"])

    def test_never_guessed_from_text(self):
        stored = store.post_message("general", "done — see t_deadbeef", author_type="agent")
        self.assertIsNone(stored["task_id"])
        self.assertIsNone(store.get_message(stored["id"])["task_id"])

    def test_round_trip(self):
        a = store.post_message("general", "answer", author_type="agent", task_id="t_e7741438")
        reply = store.post_message("general", "reply", author_type="agent", thread_parent_id=a["id"],
                                   task_id="t_other001")
        self.assertEqual([m["task_id"] for m in store.list_messages("general")], ["t_e7741438"])
        self.assertEqual(store.get_message(a["id"])["task_id"], "t_e7741438")
        thread = store.list_thread(a["id"])
        self.assertEqual(thread["parent"]["task_id"], "t_e7741438")
        self.assertEqual([r["task_id"] for r in thread["replies"]], ["t_other001"])
        self.assertEqual(reply["task_id"], "t_other001")


class SyncTest(KanbanBase):
    def peer(self, mid, **extra):
        return {"from": {"gateway_id": "gw-b", "display_name": "riley"},
                "channels": [{"id": "general", "name": "general"}],
                "messages": [dict({"id": mid, "channel_id": "general", "content": "hello",
                                   "author_type": "agent", "author_name": "r", "gateway_id": "gw-b"},
                                  **extra)]}

    def test_export_includes_task_id(self):
        store.post_message("general", "tied", author_type="agent", task_id="t_e7741438")
        self.assertEqual([m["task_id"] for m in store.export_batch(0)["messages"]], ["t_e7741438"])

    def test_ingest_variants(self):
        self.assertEqual(store.ingest(self.peer("p1", task_id="t_e7741438")), 1)
        self.assertEqual(store.ingest(self.peer("p2", task_id="not a task")), 1)
        self.assertEqual(store.ingest(self.peer("p3")), 1)
        self.assertEqual(store.ingest(self.peer("p4", future=1)), 1)  # unknown key: forward compat
        got = {m["id"]: m["task_id"] for m in store.list_messages("general")}
        self.assertEqual(got, {"p1": "t_e7741438", "p2": None, "p3": None, "p4": None})

    def test_valid_message_drops_bad_task_id(self):
        base = {"id": "m", "channel_id": "general", "content": "x"}
        self.assertEqual(store._valid_message(dict(base, task_id="bad id"))["task_id"], "")
        self.assertEqual(store._valid_message(dict(base, task_id="t_e7741438"))["task_id"], "t_e7741438")
        self.assertEqual(store._valid_message(base)["task_id"], "")

    def test_share_dm_keeps_task_id(self):
        store.ingest({"from": {"gateway_id": "gw-b", "display_name": "riley"}})
        dm = store.open_dm("gw-b")
        store.post_message(dm["id"], "tied", author_type="agent", task_id="t_e7741438")
        store.post_message(dm["id"], "plain", author_type="agent")
        store.share_dm(dm["id"], "launch")
        self.assertEqual([m["task_id"] for m in store.list_messages("launch")], ["t_e7741438", None])


class MigrationTest(KanbanBase):
    """A hermes-multiplayer.db created before S-16 has no task_id column; the schema memo must add it."""

    def test_pre_s16_db_gains_task_id(self):
        db = self.root / "hermes-multiplayer.db"
        conn = sqlite3.connect(db)
        conn.executescript(
            "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
            "CREATE TABLE channels (id TEXT PRIMARY KEY, name TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '',"
            " is_dm INTEGER NOT NULL DEFAULT 0, members TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);"
            "CREATE TABLE messages (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,"
            " channel_id TEXT NOT NULL, author_type TEXT NOT NULL, author_name TEXT NOT NULL,"
            " gateway_id TEXT NOT NULL, gateway_name TEXT NOT NULL DEFAULT '', content TEXT NOT NULL,"
            " created_at TEXT NOT NULL, thread_parent_id TEXT, promoted_from TEXT);")
        conn.commit()
        conn.close()
        store._initialized.discard(str(db))  # what a gateway that never saw this file does
        store.post_message("general", "old db", author_type="agent", task_id="t_e7741438")
        with sqlite3.connect(db) as check:
            columns = {r[1] for r in check.execute("PRAGMA table_info(messages)")}
        self.assertIn("task_id", columns)
        self.assertEqual(store.list_messages("general")[-1]["task_id"], "t_e7741438")


class ToolsTest(KanbanBase):
    def test_multiplayer_post_task_id(self):
        out = json.loads(tools.multiplayer_post({"channel": "general", "content": "x", "task_id": "t_e7741438"}))
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["message"]["task_id"], "t_e7741438")
        bad = json.loads(tools.multiplayer_post({"channel": "general", "content": "x", "task_id": "nope"}))
        self.assertFalse(bad["ok"])
        self.assertIn("task id", bad["error"].lower())

    def test_read_channel_exposes_task_id(self):
        tools.multiplayer_post({"channel": "general", "content": "x", "task_id": "t_e7741438"})
        tools.multiplayer_post({"channel": "general", "content": "see t_deadbeef"})
        msgs = json.loads(tools.multiplayer_read_channel({"channel": "general"}))["messages"]
        self.assertEqual([m["task_id"] for m in msgs], ["t_e7741438", None])


class RouterTest(KanbanBase):
    @unittest.skipIf(TestClient is None, "fastapi/httpx not installed")
    def test_task_route(self):
        import hermes_multiplayer.dashboard.plugin_api as api
        kanban_tasks.DB_PATH_OVERRIDE = make_kanban_db(self.root / "kanban.db")
        app = FastAPI()
        app.include_router(api.router, prefix="/api/plugins/hermes-multiplayer")
        client = TestClient(app)
        ok = client.get("/api/plugins/hermes-multiplayer/tasks/t_e7741438")
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["valid"])
        self.assertEqual(ok.json()["title"], TITLE)
        bad = client.get("/api/plugins/hermes-multiplayer/tasks/nope")
        self.assertEqual(bad.status_code, 200)
        self.assertFalse(bad.json()["valid"])
        self.assertIsNone(bad.json()["title"])


if __name__ == "__main__":
    unittest.main()
