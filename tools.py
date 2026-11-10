"""Agent tool handlers: ``(args, **kwargs) -> JSON string``, never raise."""

from __future__ import annotations

import json
from typing import Any


def _store():
    # Lazy: registration stays cheap and never opens the database.
    from .dashboard import herd_store

    return herd_store


def _fail(exc: Exception) -> str:
    message = getattr(exc, "message", None) or "Herd couldn't do that right now."
    return json.dumps({"ok": False, "error": message})


def _brief_channel(ch: dict) -> dict:
    out = {"id": ch["id"], "name": ch["name"], "type": "dm" if ch["is_dm"] else "channel",
           "message_count": ch.get("message_count", 0)}
    if ch["is_dm"]:
        out["members"] = [m.get("name") for m in ch.get("members", [])]
    if ch.get("topic"):
        out["topic"] = ch["topic"]
    return out


def herd_list_channels(args: dict, **kwargs: Any) -> str:
    try:
        store = _store()
        return json.dumps({"ok": True, "you_are": store.identity()["display_name"],
                           "channels": [_brief_channel(c) for c in store.list_channels()]})
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


def _brief_message(m: dict) -> dict:
    out = {"id": m["id"], "author": m["author_name"], "author_type": m["author_type"],
           "from_machine": m["gateway_name"], "at": m["created_at"], "text": m["content"],
           "replies": m.get("reply_count", 0), "task_id": m.get("task_id")}
    if m.get("wake_skip"):  # a mention this gateway did not hand to the agent: say why, never drop it silently
        out["mention_not_delivered"] = _store().WAKE_REASONS.get(m["wake_skip"], "Not handed to the agent.")
    return out


def herd_post(args: dict, **kwargs: Any) -> str:
    try:
        args = args or {}
        channel = str(args.get("channel") or "").strip()
        content = str(args.get("content") or "")
        reply_to = str(args.get("reply_to") or "").strip()
        task_id = str(args.get("task_id") or "").strip() or None
        store = _store()
        if reply_to:
            parent = store.get_message(reply_to)
            if not parent:
                return json.dumps({"ok": False, "error": f"No message with id '{reply_to[:64]}' to reply to."})
            if channel:
                found = store.resolve_channel(channel)
                if not found or found["id"] != parent["channel_id"]:
                    return json.dumps({"ok": False, "error": "That message is in a different channel."})
            channel = parent["channel_id"]
        if not channel:
            return json.dumps({"ok": False, "error": "channel is required"})
        message = store.post_message(channel, content, author_type="agent", thread_parent_id=reply_to or None,
                                     task_id=task_id)
        return json.dumps({"ok": True, "message": {k: message[k] for k in
                                                   ("id", "channel_id", "author_name", "created_at", "task_id")}})
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


def herd_read_channel(args: dict, **kwargs: Any) -> str:
    try:
        args = args or {}
        channel = str(args.get("channel") or "").strip()
        thread = str(args.get("thread") or "").strip()
        if thread:
            found = _store().list_thread(thread)
            return json.dumps({"ok": True, "thread": {"parent": _brief_message(found["parent"]),
                                                      "replies": [_brief_message(m) for m in found["replies"]]}})
        if not channel:
            return json.dumps({"ok": False, "error": "channel is required"})
        try:
            limit = int(args.get("limit") or 20)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 100))
        store = _store()
        found = store.resolve_channel(channel)
        if not found:
            return json.dumps({"ok": False, "error": f"No channel or DM named '{channel}'."})
        messages = store.list_messages(found["id"], limit=limit)
        return json.dumps({
            "ok": True, "channel": _brief_channel(found),
            "messages": [_brief_message(m) for m in messages],
        })
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


def _brief_hit(r: dict) -> dict:
    return {"id": r["id"], "channel": r["channel_name"], "channel_id": r["channel_id"],
            "type": "dm" if r["is_dm"] else "channel", "author": r["author_name"], "author_type": r["author_type"],
            "from_machine": r["gateway_name"], "at": r["created_at"], "snippet": r["snippet"],
            "in_thread": bool(r["thread_parent_id"])}


def herd_search(args: dict, **kwargs: Any) -> str:
    """Search message history across channels and DMs this gateway holds. Read-only."""
    try:
        args = args or {}
        query = str(args.get("query") or "").strip()
        if not query:
            return json.dumps({"ok": False, "error": "query is required"})
        channel = str(args.get("channel") or "").strip() or None
        hits = _store().search_messages(query, channel=channel, limit=args.get("limit"))
        return json.dumps({"ok": True, "query": query, "results": [_brief_hit(h) for h in hits]})
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


def herd_set_status(args: dict, **kwargs: Any) -> str:
    try:
        args = args or {}
        entry = _store().set_status(args.get("status"))
        return json.dumps({"ok": True, "status": entry["phrase"]})
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
