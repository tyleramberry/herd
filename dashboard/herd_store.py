"""Herd core: SQLite store + two-gateway sync. Framework-free (stdlib only).

Shared by every Herd surface:

* ``dashboard/plugin_api.py`` (FastAPI router at ``/api/plugins/herd/``, the desktop half's backend)
* ``tools.py`` (agent tools ``herd_list_channels`` / ``herd_post`` / ``herd_read_channel``)
* ``__init__.py`` (the peer endpoint ``POST /herd/v1/sync`` on the gateway's ``api_server``)

Fan-out model (see README "How sync works"):

* Every message has a globally unique id (client UUID) and a local monotonic ``seq``. Inserts are
  ``INSERT OR IGNORE`` on the id, so replays and duplicate deliveries converge to one row.
* A gateway that has a peer configured runs ``sync_all()``: ONE ``POST <peer>/herd/v1/sync`` per
  round that pushes its messages after ``push_seq`` and pulls the peer's messages after
  ``pull_seq``. Cursors advance only on success, so an unreachable peer simply catches up later.
  Because the linked side both pushes and pulls, linking on one side is enough for both directions.
* Public channel ids are their normalized names, so ``general`` on gateway A *is* ``general`` on B.
  A DM is a channel with ``is_dm=1`` and exactly two members (N-1 cut-list): no separate model.
"""

from __future__ import annotations

import contextvars
import json
import re
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

PLUGIN_ID = "herd"
DEFAULT_CHANNEL = "general"
PEER_SYNC_PATH = "/herd/v1/sync"
PROTOCOL_VERSION = 1

MAX_CONTENT = 20_000
MAX_NAME = 64
BATCH_LIMIT = 200
SYNC_TIMEOUT_S = 10
SECRET_ENV = "HERD_PEER_KEY"

REACTIONS = ["👍", "❤️", "👁️", "🎉"]

_CHANNEL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_AUTHOR_TYPES = {"human", "agent"}

# Tests point this at a temp file; production resolves Hermes's per-profile plugin data dir.
DB_PATH_OVERRIDE: Optional[Path] = None
# Tests replace the peer transport; production uses ``_http_sync``.
TRANSPORT: Optional[Callable[[dict, dict], dict]] = None
# Tests replace the settings source; production reads ``plugins.entries.herd.settings``.
SETTINGS_OVERRIDE: Optional[dict] = None
# Tests turn off the post-triggered background sync and drive ``sync_all()`` explicitly.
AUTO_SYNC = True
# Set by the plugin's register(): ``fn(session_key, text) -> bool`` (wraps ctx.inject_message).
WAKE_HANDLER: Optional[Callable[[str, str], bool]] = None
WAKE_MAX_PER_MINUTE = 6


class HerdError(Exception):
    """A user-facing error with an HTTP-ish status (422 bad input, 404 unknown, 409 conflict)."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    is_dm INTEGER NOT NULL DEFAULT 0,
    members TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE NOT NULL,
    channel_id TEXT NOT NULL,
    author_type TEXT NOT NULL,
    author_name TEXT NOT NULL,
    gateway_id TEXT NOT NULL,
    gateway_name TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id, created_at, id);
CREATE TABLE IF NOT EXISTS participants (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    is_self INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS peer_state (
    url TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    push_seq INTEGER NOT NULL DEFAULT 0,
    pull_seq INTEGER NOT NULL DEFAULT 0,
    push_rseq INTEGER NOT NULL DEFAULT 0,
    pull_rseq INTEGER NOT NULL DEFAULT 0,
    remote_gateway_id TEXT NOT NULL DEFAULT '',
    remote_name TEXT NOT NULL DEFAULT '',
    last_attempt TEXT NOT NULL DEFAULT '',
    last_ok TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS incoming_peers (
    gateway_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    last_seen TEXT NOT NULL DEFAULT '',
    syncs INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reactions (
    rseq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE NOT NULL,
    message_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    emoji TEXT NOT NULL,
    gateway_id TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reactions_message ON reactions(message_id, emoji, active);
"""

_init_lock = threading.Lock()
_initialized: set[str] = set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def db_path() -> Path:
    if DB_PATH_OVERRIDE is not None:
        return Path(DB_PATH_OVERRIDE)
    from plugins.plugin_storage import plugin_data_dir  # Hermes per-profile data root

    return Path(plugin_data_dir(PLUGIN_ID)) / "herd.db"


def _ensure_schema(conn: sqlite3.Connection, key: str) -> None:
    if key in _initialized:
        return
    with _init_lock:
        if key in _initialized:
            return
        conn.executescript(_SCHEMA)
        # Pre-S-12 DBs have peer_state without the reaction cursors (CREATE IF NOT EXISTS won't add them).
        have = {r[1] for r in conn.execute("PRAGMA table_info(peer_state)").fetchall()}
        for col in ("push_rseq", "pull_rseq"):
            if col not in have:
                conn.execute(f"ALTER TABLE peer_state ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            "INSERT OR IGNORE INTO channels(id, name, topic, is_dm, members, created_at) "
            "VALUES (?, ?, '', 0, '[]', ?)",
            (DEFAULT_CHANNEL, DEFAULT_CHANNEL, _now()),
        )
        conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('gateway_id', ?)", (uuid.uuid4().hex,)
        )
        conn.commit()
        _initialized.add(key)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        _ensure_schema(conn, str(path))
        with conn:  # one transaction: commit on success, rollback on error (no half-written rows)
            yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Settings + identity
# ---------------------------------------------------------------------------


def settings() -> dict:
    """``plugins.entries.herd.settings`` from config.yaml (Settings → Plugins → Herd form)."""
    if SETTINGS_OVERRIDE is not None:
        return dict(SETTINGS_OVERRIDE)
    try:
        from hermes_cli.config import load_config_readonly

        cfg = load_config_readonly() or {}
        entry = ((cfg.get("plugins") or {}).get("entries") or {}).get(PLUGIN_ID) or {}
        value = entry.get("settings") or {}
        return dict(value) if isinstance(value, dict) else {}
    except Exception:
        return {}


def _secret(name: str) -> str:
    """Credentials only through Hermes's secret route (catalog rule 11)."""
    if SETTINGS_OVERRIDE is not None:
        return str(SETTINGS_OVERRIDE.get("__secrets__", {}).get(name, ""))
    try:
        from agent.secret_scope import get_secret

        return str(get_secret(name, "") or "").strip()
    except Exception:
        return ""


def _clean_name(value: Any, fallback: str = "") -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:MAX_NAME] or fallback


def identity() -> dict:
    """This gateway: a stable random id (in herd.db) + the human-facing display name."""
    with connect() as conn:
        gateway_id = conn.execute("SELECT value FROM meta WHERE key='gateway_id'").fetchone()[0]
    default_name = socket.gethostname().split(".")[0] or "me"
    return {"gateway_id": gateway_id, "display_name": _clean_name(settings().get("display_name"), default_name)}


def _touch_participant(conn: sqlite3.Connection, gateway_id: str, display_name: str, is_self: bool) -> None:
    if not gateway_id:
        return
    conn.execute(
        "INSERT INTO participants(id, display_name, is_self, last_seen) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name, "
        "is_self=excluded.is_self, last_seen=excluded.last_seen",
        (gateway_id, display_name, 1 if is_self else 0, _now()),
    )


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


def _channel_row(row: sqlite3.Row) -> dict:
    out = dict(row)
    try:
        out["members"] = json.loads(out.get("members") or "[]")
    except ValueError:
        out["members"] = []
    out["is_dm"] = bool(out.get("is_dm"))
    return out


def normalize_channel_name(name: Any) -> str:
    raw = str(name or "").strip().lstrip("#").strip().lower()
    return re.sub(r"\s+", "-", raw)


def list_channels() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.*, COUNT(m.id) AS message_count, MAX(m.created_at) AS last_message_at "
            "FROM channels c LEFT JOIN messages m ON m.channel_id = c.id "
            "GROUP BY c.id ORDER BY c.is_dm, c.name COLLATE NOCASE"
        ).fetchall()
    return [_channel_row(r) for r in rows]


def get_channel(channel_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
    return _channel_row(row) if row else None


def resolve_channel(ref: Any) -> Optional[dict]:
    """Find a channel by id, by name (``general`` / ``#general``), or a DM by the other member's name."""
    key = str(ref or "").strip()
    if not key:
        return None
    found = get_channel(key) or get_channel(normalize_channel_name(key))
    if found:
        return found
    wanted = key.lstrip("@").strip().lower()
    for ch in list_channels():
        if ch["is_dm"] and any(str(m.get("name", "")).lower() == wanted for m in ch["members"]):
            return ch
    return None


def create_channel(name: Any, topic: Any = "") -> dict:
    clean = normalize_channel_name(name)
    if not clean:
        raise HerdError(422, "Channel name is required.")
    if not _CHANNEL_NAME_RE.match(clean):
        raise HerdError(422, "Use lowercase letters, numbers, - or _ (max 48 characters).")
    channel = {"id": clean, "name": clean, "topic": str(topic or "")[:200], "is_dm": 0,
               "members": "[]", "created_at": _now()}
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO channels(id, name, topic, is_dm, members, created_at) "
                "VALUES (:id, :name, :topic, :is_dm, :members, :created_at)", channel)
        except sqlite3.IntegrityError as exc:
            raise HerdError(409, f"#{clean} already exists.") from exc
    request_sync()
    return {**channel, "is_dm": False, "members": [], "message_count": 0, "last_message_at": None}


def dm_channel_id(a: str, b: str) -> str:
    return "dm:" + "+".join(sorted([a, b]))


def open_dm(participant_id: str) -> dict:
    """Get or create the DM between this gateway's human and a peer gateway's human."""
    me = identity()
    with connect() as conn:
        other = conn.execute(
            "SELECT id, display_name FROM participants WHERE id = ? AND is_self = 0", (participant_id,)
        ).fetchone()
        if not other:
            raise HerdError(404, "That person isn't connected yet.")
        members = sorted(
            [{"id": me["gateway_id"], "name": me["display_name"]},
             {"id": other["id"], "name": other["display_name"]}],
            key=lambda m: m["id"])
        channel_id = dm_channel_id(me["gateway_id"], other["id"])
        conn.execute(
            "INSERT OR IGNORE INTO channels(id, name, topic, is_dm, members, created_at) "
            "VALUES (?, ?, '', 1, ?, ?)",
            (channel_id, " & ".join(m["name"] for m in members), json.dumps(members), _now()))
        row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
    request_sync()
    return _channel_row(row)


def _upsert_channel(conn: sqlite3.Connection, ch: dict) -> None:
    """Accept a channel from a peer. Validated: never trust peer input to shape our rows."""
    cid = str(ch.get("id") or "")
    is_dm = bool(ch.get("is_dm"))
    if is_dm:
        members = ch.get("members") if isinstance(ch.get("members"), list) else []
        clean = [{"id": str(m.get("id", ""))[:64], "name": _clean_name(m.get("name"), "?")}
                 for m in members if isinstance(m, dict)][:2]
        if len(clean) != 2 or cid != dm_channel_id(clean[0]["id"], clean[1]["id"]):
            return
        name = " & ".join(m["name"] for m in clean)
        conn.execute(
            "INSERT INTO channels(id, name, topic, is_dm, members, created_at) VALUES (?, ?, '', 1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, members=excluded.members",
            (cid, name, json.dumps(clean), str(ch.get("created_at") or _now())[:40]))
    else:
        if cid != normalize_channel_name(cid) or not _CHANNEL_NAME_RE.match(cid):
            return
        conn.execute(
            "INSERT OR IGNORE INTO channels(id, name, topic, is_dm, members, created_at) "
            "VALUES (?, ?, ?, 0, '[]', ?)",
            (cid, cid, str(ch.get("topic") or "")[:200], str(ch.get("created_at") or _now())[:40]))


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

_MESSAGE_COLS = "seq, id, channel_id, author_type, author_name, gateway_id, gateway_name, content, created_at"


def _notify(event: str, payload: dict) -> None:
    """Tell every desktop connected to this process to refresh. Polling covers the rest."""
    try:
        from hermes_cli.plugin_events import broadcast_plugin_event

        broadcast_plugin_event(PLUGIN_ID, event, payload)
    except Exception:
        pass


def post_message(channel_ref: str, content: Any, *, author_type: str = "human",
                 author_name: Any = None, message_id: Any = None) -> dict:
    text = str(content or "")
    if not text.strip():
        raise HerdError(422, "Message is empty.")
    if len(text) > MAX_CONTENT:
        raise HerdError(422, f"Message is too long (max {MAX_CONTENT} characters).")
    if author_type not in _AUTHOR_TYPES:
        raise HerdError(422, "author_type must be 'human' or 'agent'.")
    channel = resolve_channel(channel_ref)
    if not channel:
        raise HerdError(404, f"No channel or DM named '{channel_ref}'.")
    me = identity()
    default_author = me["display_name"] if author_type == "human" else f"{me['display_name']}'s Hermes"
    mid = str(message_id or "").strip() or str(uuid.uuid4())
    if len(mid) > 64:
        raise HerdError(422, "Message id is too long.")
    row = {
        "id": mid, "channel_id": channel["id"], "author_type": author_type,
        "author_name": _clean_name(author_name, default_author), "gateway_id": me["gateway_id"],
        "gateway_name": me["display_name"], "content": text, "created_at": _now(),
    }
    with connect() as conn:
        _touch_participant(conn, me["gateway_id"], me["display_name"], True)
        cur = conn.execute(
            "INSERT OR IGNORE INTO messages(id, channel_id, author_type, author_name, gateway_id, "
            "gateway_name, content, created_at) VALUES (:id, :channel_id, :author_type, :author_name, "
            ":gateway_id, :gateway_name, :content, :created_at)", row)
        inserted = bool(cur.rowcount)
        stored = dict(conn.execute(f"SELECT {_MESSAGE_COLS} FROM messages WHERE id = ?", (mid,)).fetchone())
    if not inserted:
        # A row with this id already exists. Replaying it into the SAME channel is
        # the cross-gateway convergence path (INSERT OR IGNORE): return it silently.
        # A different channel means the caller is reusing a global message id — refuse.
        if stored["channel_id"] != channel["id"]:
            raise HerdError(409, f"Message id '{mid}' already exists in another channel.")
        return stored
    _notify("message.created", {"channel_id": stored["channel_id"], "id": stored["id"]})
    request_sync()
    return stored


def list_messages(channel_ref: str, *, after_seq: Optional[int] = None, limit: int = 200) -> list[dict]:
    """Messages in a channel, oldest first (newest last). ``after_seq`` is a local cursor, immune
    to clock skew between gateways; without it, the latest ``limit`` messages are returned."""
    channel = resolve_channel(channel_ref)
    if not channel:
        raise HerdError(404, f"No channel or DM named '{channel_ref}'.")
    limit = max(1, min(int(limit or 200), 500))
    with connect() as conn:
        if after_seq is not None:
            rows = conn.execute(
                f"SELECT {_MESSAGE_COLS} FROM messages WHERE channel_id = ? AND seq > ? "
                "ORDER BY created_at, id LIMIT ?", (channel["id"], int(after_seq), limit)).fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM (SELECT {_MESSAGE_COLS} FROM messages WHERE channel_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?) ORDER BY created_at, id",
                (channel["id"], limit)).fetchall()
        reactions = _reaction_map(conn, channel["id"])
    out = [dict(r) for r in rows]
    for m in out:
        m["reactions"] = reactions.get(m["id"], [])
    return out


def _reaction_map(conn: sqlite3.Connection, channel_id: str, me: Optional[str] = None,
                  message_id: Optional[str] = None) -> dict[str, list[dict]]:
    """message_id -> [{emoji, count, mine}] (active only, whitelist order). One aggregate query."""
    me = me if me is not None else conn.execute("SELECT value FROM meta WHERE key='gateway_id'").fetchone()[0]
    sql = ("SELECT message_id, emoji, COUNT(*) AS n, MAX(gateway_id = ?) AS mine FROM reactions "
           "WHERE channel_id = ? AND active = 1")
    args: list = [me, channel_id]
    if message_id:
        sql += " AND message_id = ?"
        args.append(message_id)
    out: dict[str, list[dict]] = {}
    for r in conn.execute(sql + " GROUP BY message_id, emoji", args).fetchall():
        if r["emoji"] in REACTIONS:
            out.setdefault(r["message_id"], []).append(
                {"emoji": r["emoji"], "count": r["n"], "mine": bool(r["mine"])})
    for items in out.values():
        items.sort(key=lambda x: REACTIONS.index(x["emoji"]))
    return out


def list_reactions(channel_id: str) -> dict[str, list[dict]]:
    with connect() as conn:
        return _reaction_map(conn, channel_id)


def toggle_reaction(channel_ref: str, message_id: str, emoji: Any) -> dict:
    """React to a message, or remove our reaction if we already have it (one row per message+emoji+gateway)."""
    channel = resolve_channel(channel_ref)
    if not channel:
        raise HerdError(404, f"No channel or DM named '{channel_ref}'.")
    mid = str(message_id or "").strip()
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM messages WHERE id = ? AND channel_id = ?",
                            (mid, channel["id"])).fetchone():
            raise HerdError(404, "No message with that id.")
    if emoji not in REACTIONS:
        raise HerdError(422, "Pick one of " + " ".join(REACTIONS) + ".")
    me = identity()["gateway_id"]
    rid = f"{mid}|{emoji}|{me}"
    with connect() as conn:
        row = conn.execute("SELECT active FROM reactions WHERE id = ?", (rid,)).fetchone()
        active = 0 if (row and row["active"]) else 1
        # INSERT OR REPLACE without rseq: old row is deleted, new AUTOINCREMENT rseq moves the sync cursor.
        conn.execute(
            "INSERT OR REPLACE INTO reactions(id, message_id, channel_id, emoji, gateway_id, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", (rid, mid, channel["id"], emoji, me, active, _now()))
        aggregate = _reaction_map(conn, channel["id"], me, mid).get(mid, [])
    _notify("reactions.changed", {"channel_id": channel["id"]})
    request_sync()
    return {"emoji": emoji, "active": bool(active), "reactions": aggregate}


def list_participants() -> list[dict]:
    me = identity()
    with connect() as conn:
        _touch_participant(conn, me["gateway_id"], me["display_name"], True)
        rows = conn.execute(
            "SELECT * FROM participants ORDER BY is_self DESC, display_name COLLATE NOCASE").fetchall()
    return [{**dict(r), "is_self": bool(r["is_self"])} for r in rows]


# ---------------------------------------------------------------------------
# Peer protocol (both sides)
# ---------------------------------------------------------------------------


def _valid_message(m: Any) -> Optional[dict]:
    if not isinstance(m, dict):
        return None
    try:
        out = {
            "id": str(m["id"])[:64], "channel_id": str(m["channel_id"])[:200],
            "author_type": str(m.get("author_type") or "human"),
            "author_name": _clean_name(m.get("author_name"), "someone"),
            "gateway_id": str(m.get("gateway_id") or "")[:64],
            "gateway_name": _clean_name(m.get("gateway_name"), ""),
            "content": str(m.get("content") or ""), "created_at": str(m.get("created_at") or _now())[:40],
        }
    except (KeyError, TypeError):
        return None
    if not out["id"] or not out["content"].strip() or len(out["content"]) > MAX_CONTENT:
        return None
    if out["author_type"] not in _AUTHOR_TYPES:
        return None
    return out


def _valid_reaction(r: Any) -> Optional[dict]:
    if not isinstance(r, dict):
        return None
    emoji = r.get("emoji")
    if emoji not in REACTIONS:
        return None
    mid = str(r.get("message_id") or "")[:64]
    gateway_id = str(r.get("gateway_id") or "")[:64]
    if not mid or not gateway_id:
        return None
    return {"message_id": mid, "emoji": emoji, "gateway_id": gateway_id,
            "active": 1 if r.get("active") else 0, "created_at": str(r.get("created_at") or _now())[:40]}


def ingest(batch: dict) -> int:
    """Store channels + messages received from a peer. Idempotent. Returns rows newly inserted."""
    sender = batch.get("from") if isinstance(batch.get("from"), dict) else {}
    channels = batch.get("channels") if isinstance(batch.get("channels"), list) else []
    messages = batch.get("messages") if isinstance(batch.get("messages"), list) else []
    reactions = batch.get("reactions") if isinstance(batch.get("reactions"), list) else []
    inserted = 0
    touched: set[str] = set()
    rtouched: set[str] = set()
    wakes: list[dict] = []
    with connect() as conn:
        if sender.get("gateway_id"):
            _touch_participant(conn, str(sender["gateway_id"])[:64],
                               _clean_name(sender.get("display_name"), "peer"), False)
        for ch in channels[:BATCH_LIMIT]:
            if isinstance(ch, dict):
                _upsert_channel(conn, ch)
        for raw in messages[:BATCH_LIMIT]:
            m = _valid_message(raw)
            if not m:
                continue
            if not conn.execute("SELECT 1 FROM channels WHERE id = ?", (m["channel_id"],)).fetchone():
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO messages(id, channel_id, author_type, author_name, gateway_id, "
                "gateway_name, content, created_at) VALUES (:id, :channel_id, :author_type, :author_name, "
                ":gateway_id, :gateway_name, :content, :created_at)", m)
            if cur.rowcount:
                inserted += 1
                touched.add(m["channel_id"])
                wakes.append(m)
        for raw in reactions[:BATCH_LIMIT]:
            r = _valid_reaction(raw)
            if not r:
                continue
            msg = conn.execute("SELECT channel_id FROM messages WHERE id = ?", (r["message_id"],)).fetchone()
            if not msg:
                continue
            r["channel_id"] = msg["channel_id"]
            r["id"] = f"{r['message_id']}|{r['emoji']}|{r['gateway_id']}"[:200]
            conn.execute(
                "INSERT OR REPLACE INTO reactions(id, message_id, channel_id, emoji, gateway_id, active, "
                "created_at) VALUES (:id, :message_id, :channel_id, :emoji, :gateway_id, :active, :created_at)", r)
            rtouched.add(r["channel_id"])
    _maybe_wake(wakes)
    for channel_id in touched:
        _notify("message.created", {"channel_id": channel_id})
    for channel_id in rtouched:
        _notify("reactions.changed", {"channel_id": channel_id})
    if channels and not touched:
        _notify("channels.changed", {})
    return inserted


def export_batch(after_seq: int, exclude_gateway: str = "", limit: int = BATCH_LIMIT,
                 after_rseq: int = 0) -> dict:
    """Our channels + messages after ``after_seq`` (skipping ones that came from ``exclude_gateway``)."""
    with connect() as conn:
        examined = conn.execute(
            f"SELECT {_MESSAGE_COLS} FROM messages WHERE seq > ? ORDER BY seq LIMIT ?",
            (int(after_seq), int(limit))).fetchall()
        channels = [_channel_row(r) for r in conn.execute("SELECT * FROM channels").fetchall()]
        rexamined = conn.execute(
            "SELECT rseq, id, message_id, channel_id, emoji, gateway_id, active, created_at FROM reactions "
            "WHERE rseq > ? ORDER BY rseq LIMIT ?", (int(after_rseq), int(limit))).fetchall()
    # The cursor moves past excluded rows too (the peer already has its own messages).
    rows = [dict(r) for r in examined if not exclude_gateway or r["gateway_id"] != exclude_gateway]
    next_seq = examined[-1]["seq"] if examined else int(after_seq)
    rrows = [dict(r) for r in rexamined if not exclude_gateway or r["gateway_id"] != exclude_gateway]
    next_rseq = rexamined[-1]["rseq"] if rexamined else int(after_rseq)
    return {"channels": channels, "messages": rows, "next_seq": int(next_seq), "more": len(examined) >= limit,
            "reactions": rrows, "next_rseq": int(next_rseq), "rmore": len(rexamined) >= limit}


def _record_incoming(sender: dict) -> None:
    """Remember who synced to us. The route is already authenticated with our API_SERVER_KEY."""
    gid = str(sender.get("gateway_id") or "").strip()[:64]
    if not gid:
        return
    real = _clean_name(sender.get("display_name"), "")
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO incoming_peers(gateway_id, name) VALUES (?, ?)", (gid, real or "peer"))
        conn.execute(
            "UPDATE incoming_peers SET name = CASE WHEN ? != '' THEN ? ELSE name END, "
            "last_seen = ?, syncs = syncs + 1 WHERE gateway_id = ?", (real, real, _now(), gid))


def handle_peer_sync(body: Any) -> dict:
    """Server side of ``POST /herd/v1/sync`` (runs on the gateway that was linked TO).

    Body: ``{"v": 1, "from": {gateway_id, display_name}, "channels": [...], "messages": [...],
    "after_seq": <cursor into our messages>}``. Response: our identity + our messages after the cursor.
    """
    if not isinstance(body, dict):
        raise HerdError(422, "Body must be a JSON object.")
    accepted = ingest(body)
    sender = body.get("from") if isinstance(body.get("from"), dict) else {}
    _record_incoming(sender)
    try:
        after_seq = max(0, int(body.get("after_seq") or 0))
    except (TypeError, ValueError):
        raise HerdError(422, "after_seq must be an integer.")
    try:
        after_rseq = max(0, int(body.get("after_rseq") or 0))
    except (TypeError, ValueError):
        raise HerdError(422, "after_rseq must be an integer.")
    out = export_batch(after_seq, exclude_gateway=str(sender.get("gateway_id") or ""), after_rseq=after_rseq)
    return {"v": PROTOCOL_VERSION, "from": identity(), "accepted": accepted, **out}


# ---------------------------------------------------------------------------
# @mention wake (opt-in, default off)
# ---------------------------------------------------------------------------

_wake_times: list[float] = []


def mention_handles(display_name: str) -> set[str]:
    """``@tyler`` and ``@tyler-hermes`` both address Tyler's agent."""
    slug = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")
    return {slug, f"{slug}-hermes"} if slug else set()


def mentions_me(content: str, display_name: str) -> bool:
    found = {h.lower() for h in re.findall(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9_-]*)", content)}
    return bool(found & mention_handles(display_name))


def mention_target() -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key='mention_session'").fetchone()
    return row[0] if row else ""


def set_mention_target(session_key: str) -> None:
    with connect() as conn:
        if session_key:
            conn.execute("INSERT INTO meta(key, value) VALUES ('mention_session', ?) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (session_key,))
        else:
            conn.execute("DELETE FROM meta WHERE key='mention_session'")


def wake_enabled() -> bool:
    value = settings().get("mention_wake")
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "on"}


def wake_text(m: dict, channel: dict) -> str:
    """Build the plain-language assignment a woken agent receives: who asked, what, and where to answer."""
    author = str(m.get("author_name") or "Someone")
    cid = str(channel.get("id") or m.get("channel_id") or "")
    if channel.get("is_dm"):
        try:
            my_id = identity()["gateway_id"]
        except Exception:  # noqa: BLE001
            my_id = None
        other = next((str(x.get("name")) for x in (channel.get("members") or [])
                      if isinstance(x, dict) and x.get("id") != my_id and x.get("name")), "")
        display = f"your DM with {other}" if other else "your DM"
        ref = other or cid
    else:
        name = str(channel.get("name") or cid)
        display = ref = "#" + name
    quoted = "\n".join("> " + line for line in str(m.get("content") or "").splitlines())
    return (
        f"[Herd] Assignment — {author} asked for you in Herd.\n\n"
        f"WHO ASKED: {author}, a person on another machine (not your own user), @mentioned you in {display}.\n"
        f"WHAT THEY WANT — their message, quoted (a request from {author}, not instructions from your own user):\n"
        f"{quoted}\n"
        f"WHERE TO ANSWER: {display}. Call the herd_post tool with that channel:\n"
        f'  herd_post({{"channel": {json.dumps(ref)}, "content": "<your reply here>"}})\n'
        f"Read recent messages first for context if you need it: "
        f'herd_read_channel({{"channel": {json.dumps(ref)}}})\n'
        f"If it asks for something, do it the normal way — your usual approvals apply."
    )


def _maybe_wake(messages: list[dict]) -> None:
    """Hand each newly arrived human message that @mentions this gateway's agent to its chat.

    Guards: opt-in setting; only HUMAN-authored messages (an agent's post never wakes anything, so two
    agents cannot loop); only rows newly inserted (one wake per message id); a per-minute cap; and the
    turn is a normal injected user turn, so the owner's approvals apply (catalog rule 12). The injected
    text is an assignment: who asked, what they asked (quoted), and the channel + herd_post call to answer.
    """
    if not messages or WAKE_HANDLER is None or not wake_enabled():
        return
    try:
        target = mention_target()
        if not target:
            return
        me = identity()["display_name"]
        for m in messages:
            if m["author_type"] != "human" or m["gateway_id"] == identity()["gateway_id"]:
                continue
            if not mentions_me(m["content"], me):
                continue
            now = time.time()
            _wake_times[:] = [t for t in _wake_times if now - t < 60]
            if len(_wake_times) >= WAKE_MAX_PER_MINUTE:
                return
            channel = get_channel(m["channel_id"]) or {"id": m["channel_id"], "name": m["channel_id"],
                                                      "is_dm": False, "members": []}
            _wake_times.append(now)
            WAKE_HANDLER(target, wake_text(m, channel))
    except Exception:  # noqa: BLE001 — a failed wake must never break sync
        pass


# ---------------------------------------------------------------------------
# Peer protocol (client side)
# ---------------------------------------------------------------------------


def configured_peers() -> list[dict]:
    """The peer to sync with, from Herd's own settings (Settings → Plugins → Herd).

    The key is a declared ``config_schema`` secret read only through
    ``agent.secret_scope.get_secret`` (catalog rule 11). Returned as a list so the sync loop
    stays shape-stable; v1 links exactly two gateways (N-1 cut-list).
    """
    cfg = settings()
    peers: list[dict] = []
    url = str(cfg.get("peer_url") or "").strip().rstrip("/")
    if url:
        peers.append({"name": _clean_name(cfg.get("peer_name"), "peer"), "url": url, "key": _secret(SECRET_ENV)})
    seen: set[str] = set()
    out = []
    for p in peers:
        if p["url"].lower().startswith(("http://", "https://")) and p["url"] not in seen:
            seen.add(p["url"])
            out.append(p)
    return out


def _http_sync(peer: dict, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        peer["url"] + PEER_SYNC_PATH, data=data, method="POST",
        headers={"Authorization": f"Bearer {peer['key']}", "Content-Type": "application/json",
                 "User-Agent": "hermes-herd/0.1"})
    try:
        # Strips the bearer key if the peer redirects cross-origin (same helper `hermes peer` uses).
        from hermes_cli.urllib_security import open_credentialed_url as _open
    except Exception:
        _open = urllib.request.urlopen
    with _open(req, timeout=SYNC_TIMEOUT_S) as resp:
        parsed = json.loads(resp.read().decode("utf-8", "replace"))
    if not isinstance(parsed, dict):
        raise RuntimeError("peer returned a non-object")
    return parsed


def _peer_state(conn: sqlite3.Connection, peer: dict) -> sqlite3.Row:
    conn.execute("INSERT OR IGNORE INTO peer_state(url, name) VALUES (?, ?)", (peer["url"], peer["name"]))
    conn.execute("UPDATE peer_state SET name = ? WHERE url = ?", (peer["name"], peer["url"]))
    return conn.execute("SELECT * FROM peer_state WHERE url = ?", (peer["url"],)).fetchone()


def _describe_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 401:
            return "The peer rejected the key (check its API_SERVER_KEY)."
        if exc.code == 404:
            return "The peer doesn't have Herd enabled yet."
        return f"The peer answered HTTP {exc.code}."
    if isinstance(exc, (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError)):
        return "Couldn't reach the peer."
    return "Sync failed."


def sync_peer(peer: dict, rounds: int = 5) -> dict:
    """Push our new messages to one peer and pull theirs, until both sides are drained."""
    transport = TRANSPORT or _http_sync
    me = identity()
    with connect() as conn:
        _peer_state(conn, peer)
        conn.execute("UPDATE peer_state SET last_attempt = ? WHERE url = ?", (_now(), peer["url"]))
    pushed = pulled = rpushed = 0
    try:
        if not peer.get("key"):
            raise PermissionError("no key")
        for _ in range(max(1, rounds)):
            with connect() as conn:
                st = _peer_state(conn, peer)
            out = export_batch(st["push_seq"], exclude_gateway=st["remote_gateway_id"],
                               after_rseq=st["push_rseq"])
            resp = transport(peer, {"v": PROTOCOL_VERSION, "from": me, "channels": out["channels"],
                                    "messages": out["messages"], "after_seq": st["pull_seq"],
                                    "reactions": out["reactions"], "after_rseq": st["pull_rseq"]})
            remote = resp.get("from") if isinstance(resp.get("from"), dict) else {}
            pulled += ingest(resp)
            pushed += len(out["messages"])
            rpushed += len(out["reactions"])
            next_pull = resp.get("next_seq")
            next_rpull = resp.get("next_rseq")
            with connect() as conn:
                conn.execute(
                    "UPDATE peer_state SET push_seq = ?, pull_seq = ?, push_rseq = ?, pull_rseq = ?, remote_gateway_id = ?, remote_name = ?, "
                    "last_ok = ?, last_error = '' WHERE url = ?",
                    (out["next_seq"], int(next_pull) if isinstance(next_pull, int) else st["pull_seq"],
                     out["next_rseq"],
                     int(next_rpull) if isinstance(next_rpull, int) else st["pull_rseq"],
                     str(remote.get("gateway_id") or st["remote_gateway_id"])[:64],
                     _clean_name(remote.get("display_name"), st["remote_name"]), _now(), peer["url"]))
            if not (out["more"] or out["rmore"] or resp.get("more") or resp.get("rmore")):
                break
        return {"name": peer["name"], "url": peer["url"], "ok": True, "pushed": pushed, "pulled": pulled,
                "reactions_pushed": rpushed}
    except Exception as exc:  # noqa: BLE001 — a peer being down is a normal state, not a crash
        message = "No key set for this peer." if isinstance(exc, PermissionError) else _describe_error(exc)
        with connect() as conn:
            conn.execute("UPDATE peer_state SET last_error = ? WHERE url = ?", (message, peer["url"]))
        return {"name": peer["name"], "url": peer["url"], "ok": False, "error": message,
                "pushed": pushed, "pulled": pulled}


_sync_lock = threading.Lock()


def sync_all() -> list[dict]:
    """One sync pass over every configured peer. Serialized per process; safe across processes."""
    if not _sync_lock.acquire(blocking=False):
        return []
    try:
        return [sync_peer(p) for p in configured_peers()]
    finally:
        _sync_lock.release()


_pending = threading.Event()
_kicker_lock = threading.Lock()


def request_sync() -> None:
    """Sync soon, off the caller's thread (posting never waits on the network)."""
    if not AUTO_SYNC:
        return
    with _kicker_lock:
        if _pending.is_set():
            return
        _pending.set()
    ctx = contextvars.copy_context()  # keep Hermes's per-profile secret scope in the worker

    def _run() -> None:
        try:
            time.sleep(0.05)
            _pending.clear()
            sync_all()
        except Exception:
            pass

    threading.Thread(target=lambda: ctx.run(_run), name="herd-sync-kick", daemon=True).start()


def status() -> dict:
    """Identity + per-peer link health, for the desktop's header and empty states."""
    me = identity()
    peers = configured_peers()
    with connect() as conn:
        states = {r["url"]: dict(r) for r in conn.execute("SELECT * FROM peer_state").fetchall()}
        inc_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM incoming_peers ORDER BY last_seen DESC").fetchall()]
    linked_ids = {states.get(p["url"], {}).get("remote_gateway_id") or "" for p in peers} - {""}
    incoming = [{"gateway_id": r["gateway_id"], "name": r["name"], "last_seen": r["last_seen"],
                 "syncs": r["syncs"], "linked_back": r["gateway_id"] in linked_ids} for r in inc_rows]
    out = []
    for p in peers:
        st = states.get(p["url"], {})
        out.append({
            "name": p["name"], "url": p["url"], "has_key": bool(p["key"]),
            "remote_name": st.get("remote_name") or "", "last_ok": st.get("last_ok") or "",
            "last_attempt": st.get("last_attempt") or "", "last_error": st.get("last_error") or "",
            "connected": bool(st.get("last_ok")) and not st.get("last_error"),
        })
    return {"self": me, "peers": out, "incoming": incoming, "protocol": PROTOCOL_VERSION}
