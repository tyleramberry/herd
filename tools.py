"""Agent tool handlers.

Agent-side code runs inside the same gateway process as the dashboard backend, so the
handlers call the backend logic in ``dashboard/plugin_api.py`` directly (no HTTP).
Every handler accepts ``(args, **kwargs)`` and always returns a JSON string.
"""
from __future__ import annotations

import json
from typing import Any


def _api():
    # Imported lazily so plugin registration stays cheap and never touches the db.
    from .dashboard import plugin_api

    return plugin_api


def _error(exc: Exception) -> str:
    detail = getattr(exc, "detail", None) or str(exc) or exc.__class__.__name__
    return json.dumps({"ok": False, "error": detail})


def herd_post(args: dict, **kwargs: Any) -> str:
    try:
        args = args or {}
        channel = str(args.get("channel") or "").strip()
        content = str(args.get("content") or "")
        if not channel or not content.strip():
            return json.dumps({"ok": False, "error": "channel and content are required"})
        message = _api().post_agent_message(
            channel=channel,
            content=content,
            author_name=args.get("author_name"),
            gateway_id=kwargs.get("gateway_id"),
        )
        return json.dumps({"ok": True, "message": message})
    except Exception as exc:  # noqa: BLE001 — tools must never raise into the agent loop
        return _error(exc)


def herd_list_channels(args: dict, **kwargs: Any) -> str:
    try:
        return json.dumps({"ok": True, "channels": _api().list_channels()})
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
