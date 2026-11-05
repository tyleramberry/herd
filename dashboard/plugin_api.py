"""Herd backend: FastAPI router mounted at /api/plugins/herd/ plus shared SQLite logic.

The agent-side tools (``tools.py``) import the plain functions below directly — they
run in the same gateway process, so no HTTP round-trip to localhost is needed.
"""
from __future__ import annotations

import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

PLUGIN_ID = "herd"
DEFAULT_CHANNEL = "general"

# Resolved once at import: used only when the Hermes storage helper is unavailable
# (standalone dev / tests). Never inside the repo.
_FALLBACK_DIR = Path(tempfile.gettempdir()) / "herd"

_init_lock = threading.Lock()
_initialized: set[str] = set()


def _db_path() -> Path:
    """Hermes ``<home>/plugin-data/herd/herd.db`` if available, else a system-temp fallback."""
    try:
        from plugins.plugin_storage import plugin_data_dir

        return Path(plugin_data_dir(PLUGIN_ID)) / "herd.db"
    except Exception:
        _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
        return _FALLBACK_DIR / "herd.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Logical gateway identity, set from plugin settings
# (``plugins.entries.herd.settings.gateway_id``) by ``register()``.
_GATEWAY_ID: str | None = None


def set_gateway_id(value: str | None) -> None:
    """Set the default gateway identity stamped on messages and participants."""
    global _GATEWAY_ID
    cleaned = str(value).strip() if value is not None else ""
    _GATEWAY_ID = cleaned or None


def _gateway_id(value: Any = None) -> str:
    """Explicit value, else the configured setting, else ``"local"``."""
    return str(value or _GATEWAY_ID or "local")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    topic TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    author_type TEXT NOT NULL,
    author_name TEXT,
    gateway_id TEXT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_channel_created ON messages(channel_id, created_at);
CREATE TABLE IF NOT EXISTS participants (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    gateway_id TEXT,
    kind TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
"""


def _ensure_schema(conn: sqlite3.Connection, key: str) -> None:
    if key in _initialized:
        return
    with _init_lock:
        if key in _initialized:
            return
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO channels(id, name, topic, created_at) VALUES (?, ?, ?, ?)",
            (str(uuid4()), DEFAULT_CHANNEL, "", _now()),
        )
        conn.commit()
        _initialized.add(key)


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        _ensure_schema(conn, str(path))
        with conn:  # commit on success, rollback on error
            yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Logic (shared by the HTTP routes and the agent tools)
# ---------------------------------------------------------------------------


def list_channels() -> list[dict[str, Any]]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT c.id, c.name, c.topic, c.created_at, COUNT(m.id) AS message_count "
            "FROM channels c LEFT JOIN messages m ON m.channel_id = c.id "
            "GROUP BY c.id ORDER BY c.name COLLATE NOCASE"
        ).fetchall()
    return [dict(r) for r in rows]


def create_channel(data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name") or "").strip().lstrip("#").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Channel name is required")
    channel = {
        "id": str(uuid4()),
        "name": name,
        "topic": str(data.get("topic") or ""),
        "created_at": _now(),
    }
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO channels(id, name, topic, created_at) "
                "VALUES (:id, :name, :topic, :created_at)",
                channel,
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=f"Channel '{name}' already exists") from exc
    return {**channel, "message_count": 0}


def _broadcast(message: dict[str, Any]) -> None:
    """Tell every connected desktop to refresh. No-op when Hermes is absent (tests)."""
    try:
        from hermes_cli.plugin_events import broadcast_plugin_event

        broadcast_plugin_event(PLUGIN_ID, "message.created", dict(message))
    except Exception:
        pass


def post_message(channel_id: str, data: dict[str, Any]) -> dict[str, Any]:
    content = str(data.get("content") or "")
    if not content.strip():
        raise HTTPException(status_code=422, detail="Message content is required")
    message = {
        "id": str(data.get("id") or uuid4()),
        "channel_id": channel_id,
        "author_type": str(data.get("author_type") or "human"),
        "author_name": data.get("author_name") or None,
        "gateway_id": _gateway_id(data.get("gateway_id")),
        "content": content,
        "created_at": str(data.get("created_at") or _now()),
    }
    with _db() as conn:
        if not conn.execute("SELECT 1 FROM channels WHERE id = ?", (channel_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Channel not found")
        # Client-generated UUIDs: a replayed / fanned-out message converges instead of duplicating.
        conn.execute(
            "INSERT OR IGNORE INTO messages"
            "(id, channel_id, author_type, author_name, gateway_id, content, created_at) "
            "VALUES (:id, :channel_id, :author_type, :author_name, :gateway_id, :content, :created_at)",
            message,
        )
        stored = dict(conn.execute("SELECT * FROM messages WHERE id = ?", (message["id"],)).fetchone())
    _broadcast(stored)
    return stored


def resolve_channel(channel: str) -> dict[str, Any] | None:
    key = str(channel or "").strip().lstrip("#").strip()
    with _db() as conn:
        row = conn.execute(
            "SELECT id, name, topic, created_at FROM channels WHERE id = ? OR name = ?", (key, key)
        ).fetchone()
    return dict(row) if row else None


def post_agent_message(
    channel: str, content: str, author_name: str | None = None, gateway_id: str | None = None
) -> dict[str, Any]:
    found = resolve_channel(channel)
    if not found:
        raise HTTPException(status_code=404, detail=f"Channel '{channel}' not found")
    return post_message(
        found["id"],
        {
            "content": content,
            "author_type": "agent",
            "author_name": author_name or "Hermes",
            "gateway_id": gateway_id,
        },
    )


def list_messages(channel_id: str, after: str | None = None) -> list[dict[str, Any]]:
    with _db() as conn:
        if after:
            rows = conn.execute(
                "SELECT * FROM messages WHERE channel_id = ? AND created_at > ? ORDER BY created_at, id",
                (channel_id, after),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE channel_id = ? ORDER BY created_at, id", (channel_id,)
            ).fetchall()
    return [dict(r) for r in rows]


def list_participants() -> list[dict[str, Any]]:
    with _db() as conn:
        rows = conn.execute("SELECT * FROM participants ORDER BY display_name COLLATE NOCASE").fetchall()
    return [dict(r) for r in rows]


def register_participant(data: dict[str, Any]) -> dict[str, Any]:
    display_name = str(data.get("display_name") or "").strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="display_name is required")
    participant = {
        "id": str(data.get("id") or uuid4()),
        "display_name": display_name,
        "gateway_id": _gateway_id(data.get("gateway_id")),
        "kind": str(data.get("kind") or "human"),
        "last_seen": _now(),
    }
    with _db() as conn:
        conn.execute(
            "INSERT INTO participants(id, display_name, gateway_id, kind, last_seen) "
            "VALUES (:id, :display_name, :gateway_id, :kind, :last_seen) "
            "ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name, "
            "gateway_id=excluded.gateway_id, kind=excluded.kind, last_seen=excluded.last_seen",
            participant,
        )
    return participant


# ---------------------------------------------------------------------------
# Routes — mounted under /api/plugins/herd/
# ---------------------------------------------------------------------------


@router.get("/channels")
def get_channels():
    return list_channels()


@router.post("/channels")
def post_channel(body: dict[str, Any]):
    return create_channel(body)


@router.get("/channels/{channel_id}/messages")
def get_messages(channel_id: str, after: str | None = Query(default=None)):
    return list_messages(channel_id, after)


@router.post("/channels/{channel_id}/messages")
def create_message(channel_id: str, body: dict[str, Any]):
    return post_message(channel_id, body)


@router.get("/participants")
def get_participants():
    return list_participants()


@router.post("/participants")
def post_participant(body: dict[str, Any]):
    return register_participant(body)
