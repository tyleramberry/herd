"""Herd backend for the desktop half: FastAPI routes mounted at ``/api/plugins/herd/``.

Thin HTTP wrappers around ``herd_store`` (the same code the agent tools and the peer endpoint
use, so the surfaces cannot drift). The dashboard imports this file by path, so the sibling
store module is loaded by path too.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query


def _load_store():
    try:  # imported as part of the herd package (tests, agent process)
        from . import herd_store  # type: ignore[import-not-found]

        return herd_store
    except ImportError:
        # Reuse the copy the agent half already imported (read-only lookup) so both halves share
        # one module state, e.g. the @mention wake handler.
        import sys

        for name, mod in list(sys.modules.items()):
            if name.endswith("dashboard.herd_store") and hasattr(mod, "handle_peer_sync"):
                return mod
        path = Path(__file__).resolve().parent / "herd_store.py"
        spec = importlib.util.spec_from_file_location("herd_dashboard_store", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def _load_kanban():
    try:
        from . import kanban_tasks  # type: ignore[import-not-found]

        return kanban_tasks
    except ImportError:
        path = Path(__file__).resolve().parent / "kanban_tasks.py"
        spec = importlib.util.spec_from_file_location("herd_kanban_tasks", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


store = _load_store()
kanban = _load_kanban()
router = APIRouter()


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except store.HerdError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


@router.get("/status")
def get_status():
    return _call(store.status)


@router.get("/search")
def get_search(q: str = Query(default=""), channel: Optional[str] = Query(default=None),
               limit: int = Query(default=store.SEARCH_DEFAULT_LIMIT)):
    """Full-text search over message bodies (⌘K). ``q`` is plain text: every term must match; ``channel`` narrows."""
    results = _call(store.search_messages, q, channel=channel, limit=limit)
    return {"query": str(q or "")[:store.SEARCH_MAX_CHARS], "results": results}


@router.post("/wake-target")
def post_wake_target(body: dict[str, Any]):
    """One-click 'Answer @mentions here' from the pane: the active chat's session key becomes the wake target.
    An empty session_key clears it (the same as ``/herd-listen off``). Returns the fresh status."""
    session_key = str(body.get("session_key") or "").strip()
    if len(session_key) > 256 or any(ord(c) < 0x20 for c in session_key):
        raise HTTPException(status_code=422, detail="That chat's id isn't usable. Open the chat and try again.")
    _call(store.set_mention_target, session_key, str(body.get("label") or "")[:80] if session_key else "")
    return _call(store.status)


@router.post("/sync")
def post_sync():
    """Sync with peers now (the desktop calls this on its poll tick as a backstop)."""
    _call(store.sync_all)
    return _call(store.status)


@router.get("/channels")
def get_channels():
    return _call(store.list_channels)


@router.post("/channels")
def post_channel(body: dict[str, Any]):
    return _call(store.create_channel, body.get("name"), body.get("topic", ""), members=body.get("members"))


@router.post("/channels/{channel_id}/share")
def post_share(channel_id: str, body: dict[str, Any]):
    """Promote a DM into a new shared channel (copies its history)."""
    return _call(store.share_dm, channel_id, body.get("name"), body.get("topic", ""))


@router.post("/dms")
def post_dm(body: dict[str, Any]):
    return _call(store.open_dm, str(body.get("participant_id") or ""))


@router.get("/channels/{channel_id}/messages")
def get_messages(channel_id: str, after_seq: Optional[int] = Query(default=None),
                 limit: int = Query(default=200)):
    return _call(store.list_messages, channel_id, after_seq=after_seq, limit=limit)


@router.post("/channels/{channel_id}/messages")
def post_message(channel_id: str, body: dict[str, Any]):
    channel = _call(store.get_channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="That channel doesn't exist.")
    return _call(store.post_message, channel["id"], body.get("content"), author_type="human",
                 message_id=body.get("id"), thread_parent_id=body.get("thread_parent_id"))


@router.get("/messages/{message_id}/thread")
def get_thread(message_id: str):
    return _call(store.list_thread, message_id)


@router.post("/channels/{channel_id}/messages/{message_id}/reactions")
def post_reaction(channel_id: str, message_id: str, body: dict[str, Any]):
    return _call(store.toggle_reaction, channel_id, message_id, body.get("emoji"))


@router.get("/participants")
def get_participants():
    return _call(store.list_participants)


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """Kanban badge for one explicitly-passed task id (F4). Read-only, never raises."""
    try:
        return kanban.task_link(task_id)
    except Exception:
        return {"task_id": str(task_id or "")[:64], "valid": False, "title": None, "board": ""}
