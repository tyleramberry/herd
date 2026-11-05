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
    return {"id": m["id"], "author": m["author_name"], "author_type": m["author_type"],
            "from_machine": m["gateway_name"], "at": m["created_at"], "text": m["content"],
            "replies": m.get("reply_count", 0)}


def herd_post(args: dict, **kwargs: Any) -> str:
    try:
        args = args or {}
        channel = str(args.get("channel") or "").strip()
        content = str(args.get("content") or "")
        reply_to = str(args.get("reply_to") or "").strip()
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
        message = store.post_message(channel, content, author_type="agent", thread_parent_id=reply_to or None)
        return json.dumps({"ok": True, "message": {k: message[k] for k in
                                                   ("id", "channel_id", "author_name", "created_at")}})
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
