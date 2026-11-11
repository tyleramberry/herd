"""Track 1: full-text search over message bodies (FTS5), its query escaping, ranking, backfill and surfaces."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except Exception:  # noqa: BLE001
    FastAPI = TestClient = None

sys.path.insert(0, os.path.dirname(__file__))
import _pkg  # noqa: E402

_, store, tools = _pkg.load()


def peer_msg(content, mid, *, gw="other-gw", channel="general", thread=None, created="2026-11-05T00:00:00Z"):
    row = {"id": mid, "channel_id": channel, "author_type": "human", "author_name": "Brooklyn",
           "gateway_id": gw, "gateway_name": "Brooklyn", "content": content, "created_at": created}
    if thread:
        row["thread_parent_id"] = thread
    return {"from": {"gateway_id": gw, "display_name": "Brooklyn"}, "channels": [], "messages": [row]}


class SearchBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        store.AUTO_SYNC = False
        store.DB_PATH_OVERRIDE = Path(self.tmp.name) / "s.db"
        store.SETTINGS_OVERRIDE = {"display_name": "Tyler"}
        store.WAKE_HANDLER = None

    def tearDown(self):
        store.DB_PATH_OVERRIDE = None
        store.SETTINGS_OVERRIDE = None
        self.tmp.cleanup()

    def ids(self, query, **kw):
        return [r["id"] for r in store.search_messages(query, **kw)]

    def db(self):
        return sqlite3.connect(str(store.db_path()))


class IndexParityTest(SearchBase):
    def test_every_message_is_indexed_once_with_its_body(self):
        store.ingest(peer_msg("disk full on the build box", "p1"))
        store.post_message("general", "local note about the cache", author_type="human")
        store.ingest(peer_msg("another line", "p2", channel="general"))
        with store.connect() as conn:
            msgs = {r[0]: r[1] for r in conn.execute("SELECT id, content FROM messages")}
            fts = {r[0]: r[1] for r in conn.execute("SELECT message_id, content FROM messages_fts")}
            counts = conn.execute("SELECT (SELECT COUNT(*) FROM messages), (SELECT COUNT(*) FROM messages_fts)").fetchone()
        self.assertEqual(counts[0], counts[1])
        self.assertEqual(msgs, fts)

    def test_rowid_is_the_message_seq(self):
        store.ingest(peer_msg("alpha", "x1"))
        with store.connect() as conn:
            pairs = conn.execute("SELECT m.seq, f.rowid FROM messages m JOIN messages_fts f ON f.rowid = m.seq").fetchall()
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][0], pairs[0][1])

    def test_backfill_indexes_rows_that_predate_the_index(self):
        store.ingest(peer_msg("legacy deploy note", "old1"))
        with store.connect() as conn:
            conn.execute("DELETE FROM messages_fts")  # as if the table were new and empty
        self.assertEqual(self.ids("legacy"), [])
        store._initialized.clear()  # the next connect runs the schema pass again
        with store.connect() as conn:
            store._backfill_search_index(conn)
        self.assertEqual(self.ids("legacy"), ["old1"])

    def test_backfill_is_idempotent(self):
        store.ingest(peer_msg("once only", "dup1"))
        with store.connect() as conn:
            store._backfill_search_index(conn)
            store._backfill_search_index(conn)
            n = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
        self.assertEqual(n, 1)

    def test_triggers_follow_an_update_and_a_delete(self):
        # No edit or delete feature exists yet; the triggers keep the index honest if one is added.
        store.ingest(peer_msg("kafka consumer lag", "u1"))
        with store.connect() as conn:
            conn.execute("UPDATE messages SET content = 'redis eviction storm' WHERE id = 'u1'")
        self.assertEqual(self.ids("kafka"), [])
        self.assertEqual(self.ids("redis"), ["u1"])
        with store.connect() as conn:
            conn.execute("DELETE FROM messages WHERE id = 'u1'")
        self.assertEqual(self.ids("redis"), [])

    def test_a_pre_search_database_is_upgraded_on_connect(self):
        raw = store.db_path()
        conn = sqlite3.connect(str(raw))
        conn.executescript("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE channels (id TEXT PRIMARY KEY, name TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '',
              is_dm INTEGER NOT NULL DEFAULT 0, members TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
            CREATE TABLE messages (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
              channel_id TEXT NOT NULL, author_type TEXT NOT NULL, author_name TEXT NOT NULL,
              gateway_id TEXT NOT NULL, gateway_name TEXT NOT NULL DEFAULT '', content TEXT NOT NULL,
              created_at TEXT NOT NULL, thread_parent_id TEXT, promoted_from TEXT, task_id TEXT);
            INSERT INTO messages(id, channel_id, author_type, author_name, gateway_id, gateway_name, content, created_at)
              VALUES ('pre1', 'general', 'human', 'Brooklyn', 'gw', 'Brooklyn', 'pre existing outage', '2026-11-01T00:00:00Z');
        """)
        conn.commit()
        conn.close()
        store._initialized.clear()
        self.assertEqual(self.ids("outage"), ["pre1"])


class QueryEscapingTest(SearchBase):
    def setUp(self):
        super().setUp()
        store.ingest(peer_msg("alpha only here", "e1"))
        store.ingest(peer_msg("beta gamma pair", "e2"))
        store.ingest(peer_msg('quoted "phrase" text', "e3"))
        store.ingest(peer_msg("deploy finished ok", "e4"))

    def test_fts_operators_are_plain_words(self):
        # "OR" must not mean "either word": both terms are required.
        self.assertEqual(self.ids("alpha OR zzz"), [])
        self.assertEqual(self.ids("alpha OR"), [])
        self.assertEqual(self.ids("NOT alpha"), [])
        self.assertEqual(self.ids("alpha NEAR beta"), [])

    def test_hostile_syntax_never_raises(self):
        hostile = ['"', '""', '"unbalanced', 'col:foo', 'alpha*', '-alpha', '^alpha', '(alpha', 'alpha)',
                   'NEAR(alpha beta, 3)', '*', '**', '\\', "'; DROP TABLE messages; --", '"\' OR 1=1 --',
                   '\x00', 'alpha\nbeta', '!!!', '@tyler', '#general']
        for q in hostile:
            self.assertIsInstance(store.search_messages(q), list, repr(q))
        self.assertEqual(self.ids("'; DROP TABLE messages; --"), [])  # and the table is still there
        self.assertEqual(self.ids("alpha"), ["e1"])

    def test_fts_query_builder(self):
        self.assertEqual(store.fts_query("disk full"), '"disk" "full"*')
        self.assertEqual(store.fts_query('say "hi"'), '"say" """hi"""*')
        self.assertEqual(store.fts_query("   "), "")
        self.assertEqual(store.fts_query(None), "")

    def test_very_long_queries_are_capped(self):
        many = " ".join(f"w{i}" for i in range(500))
        self.assertEqual(store.fts_query(many).count('"'), 2 * store.SEARCH_MAX_TERMS)
        self.assertIsInstance(store.search_messages("x" * 10000), list)

    def test_quotes_inside_a_term_are_doubled(self):
        self.assertEqual(self.ids('"phrase"'), ["e3"])


class MatchingTest(SearchBase):
    def test_prefix_matches_the_last_word_being_typed(self):
        store.ingest(peer_msg("deploy finished", "m1"))
        self.assertEqual(self.ids("deplo"), ["m1"])
        self.assertEqual(self.ids("deploy fin"), ["m1"])
        self.assertEqual(self.ids("deploy fin"), ["m1"])
        # Only the last word is a prefix: an earlier, half-finished word does not match.
        self.assertEqual(self.ids("fin deploy"), [])

    def test_every_term_must_appear(self):
        store.ingest(peer_msg("alpha", "t1"))
        store.ingest(peer_msg("alpha beta", "t2"))
        self.assertEqual(self.ids("alpha beta"), ["t2"])

    def test_unicode_and_diacritics(self):
        store.ingest(peer_msg("café au lait", "u1"))
        store.ingest(peer_msg("日本語のテスト", "u2"))
        store.ingest(peer_msg("emoji 🎉 party", "u3"))
        self.assertEqual(self.ids("cafe"), ["u1"])
        self.assertEqual(self.ids("café"), ["u1"])
        self.assertEqual(self.ids("日本語"), ["u2"])
        self.assertEqual(self.ids("party"), ["u3"])

    def test_empty_and_punctuation_only_queries_return_nothing(self):
        store.ingest(peer_msg("anything at all", "z1"))
        for q in ["", "   ", "!!!", "...", "\"\""]:
            self.assertEqual(store.search_messages(q), [], repr(q))

    def test_no_match_is_an_empty_list(self):
        store.ingest(peer_msg("hello", "n1"))
        self.assertEqual(store.search_messages("zebra"), [])


class RankingTest(SearchBase):
    def test_better_matches_rank_first(self):
        store.ingest(peer_msg("login error", "r-weak", created="2026-11-01T00:00:00Z"))
        store.ingest(peer_msg("login error login error login error", "r-strong", created="2026-11-02T00:00:00Z"))
        ids = self.ids("login error")
        self.assertEqual(ids[0], "r-strong")

    def test_equal_scores_break_ties_by_newest_then_id(self):
        store.ingest(peer_msg("same words", "tie-a", created="2026-11-01T00:00:00Z"))
        store.ingest(peer_msg("same words", "tie-b", created="2026-11-03T00:00:00Z"))
        store.ingest(peer_msg("same words", "tie-c", created="2026-11-02T00:00:00Z"))
        self.assertEqual(self.ids("same"), ["tie-b", "tie-c", "tie-a"])

    def test_order_is_repeatable(self):
        for i in range(12):
            store.ingest(peer_msg(f"shared term {i % 3}", f"rep{i}"))
        first = self.ids("shared term")
        self.assertEqual(first, self.ids("shared term"))
        self.assertEqual(len(first), 12)


class ResultShapeTest(SearchBase):
    def test_results_carry_channel_author_time_and_a_snippet(self):
        store.ingest(peer_msg("the build broke at step four", "s1"))
        hit = store.search_messages("build")[0]
        self.assertEqual(hit["id"], "s1")
        self.assertEqual(hit["channel_name"], "general")
        self.assertEqual(hit["author_name"], "Brooklyn")
        self.assertEqual(hit["created_at"], "2026-11-05T00:00:00Z")
        self.assertIn("[build]", hit["snippet"])

    def test_thread_replies_are_included_and_flagged(self):
        store.ingest(peer_msg("root post", "root"))
        store.ingest(peer_msg("reply about the build", "rep", thread="root"))
        hits = {h["id"]: h for h in store.search_messages("build")}
        self.assertTrue(hits["rep"]["thread_parent_id"])

    def test_channel_filter(self):
        store.create_channel("ops", "")
        store.ingest(peer_msg("shared phrase here", "c-gen", channel="general"))
        store.ingest(peer_msg("shared phrase elsewhere", "c-ops", channel="ops"))
        self.assertEqual(sorted(self.ids("shared")), ["c-gen", "c-ops"])
        self.assertEqual(self.ids("shared", channel="general"), ["c-gen"])
        self.assertEqual(self.ids("shared", channel="#ops"), ["c-ops"])

    def test_unknown_channel_is_a_404_not_a_silent_empty_list(self):
        with self.assertRaises(store.MultiplayerError) as ctx:
            store.search_messages("anything", channel="nope")
        self.assertEqual(ctx.exception.status, 404)

    def test_limit_is_clamped_and_defaults(self):
        for i in range(60):
            store.ingest(peer_msg(f"bulk row {i}", f"b{i}"))
        self.assertEqual(len(store.search_messages("bulk", limit=5)), 5)
        self.assertEqual(len(store.search_messages("bulk")), store.SEARCH_DEFAULT_LIMIT)
        self.assertEqual(len(store.search_messages("bulk", limit=10_000)), store.SEARCH_MAX_LIMIT)
        self.assertEqual(len(store.search_messages("bulk", limit=0)), 1)
        self.assertEqual(len(store.search_messages("bulk", limit="lots")), store.SEARCH_DEFAULT_LIMIT)


class AgentToolTest(SearchBase):
    def test_multiplayer_search_tool_returns_hits(self):
        store.ingest(peer_msg("we saw this error before in march", "tool1"))
        out = json.loads(tools.multiplayer_search({"query": "error before"}))
        self.assertTrue(out["ok"])
        self.assertEqual([r["id"] for r in out["results"]], ["tool1"])
        self.assertEqual(out["results"][0]["channel_id"], "general")
        self.assertIn("[error]", out["results"][0]["snippet"])

    def test_query_is_required(self):
        out = json.loads(tools.multiplayer_search({"query": "  "}))
        self.assertFalse(out["ok"])

    def test_unknown_channel_reports_a_clean_error(self):
        out = json.loads(tools.multiplayer_search({"query": "x", "channel": "missing"}))
        self.assertFalse(out["ok"])
        self.assertIn("missing", out["error"])

    def test_tool_is_built_but_held_out_of_registration(self):
        # The catalog locks the tool scope at four tools (TC-0.8). Registering multiplayer_search needs that re-approved,
        # so this test pins the held state: it fails loudly when someone turns the tool on.
        multiplayer_pkg = _pkg.load()[0]
        registered = []
        ctx = mock.Mock()
        ctx.register_tool.side_effect = lambda **kw: registered.append(kw["name"])
        multiplayer_pkg.register(ctx)
        self.assertNotIn("multiplayer_search", registered)
        self.assertEqual(sorted(registered), ["multiplayer_list_channels", "multiplayer_post", "multiplayer_read_channel", "multiplayer_set_status"])
        from hermes_multiplayer import schemas  # noqa: WPS433 - the package is loaded by _pkg
        self.assertEqual(schemas.MULTIPLAYER_SEARCH["name"], "multiplayer_search")
        self.assertEqual(schemas.MULTIPLAYER_SEARCH["parameters"]["required"], ["query"])


@unittest.skipUnless(TestClient is not None, "fastapi/httpx not installed")
class SearchRouteTest(SearchBase):
    def setUp(self):
        super().setUp()
        import importlib.util

        spec = importlib.util.spec_from_file_location("multiplayer_api_search_test",
                                                      _pkg.ROOT / "dashboard" / "plugin_api.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = FastAPI()
        app.include_router(module.router, prefix="/api/plugins/hermes-multiplayer")
        self.client = TestClient(app)

    def test_get_search_returns_results(self):
        store.ingest(peer_msg("route check phrase", "api1"))
        res = self.client.get("/api/plugins/hermes-multiplayer/search", params={"q": "route check"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["query"], "route check")
        self.assertEqual([r["id"] for r in body["results"]], ["api1"])

    def test_channel_and_limit_params(self):
        store.ingest(peer_msg("param check", "api2"))
        res = self.client.get("/api/plugins/hermes-multiplayer/search", params={"q": "param", "channel": "general", "limit": 1})
        self.assertEqual(len(res.json()["results"]), 1)

    def test_empty_query_is_an_empty_list(self):
        res = self.client.get("/api/plugins/hermes-multiplayer/search", params={"q": ""})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["results"], [])

    def test_unknown_channel_is_404(self):
        res = self.client.get("/api/plugins/hermes-multiplayer/search", params={"q": "x", "channel": "nope"})
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
