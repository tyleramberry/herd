"""Herd — multiplayer Hermes. Agent-side registration.

* Three agent tools (``herd_list_channels``, ``herd_post``, ``herd_read_channel``).
* The peer endpoint ``POST /herd/v1/sync`` on this gateway's ``api_server`` (the same server and
  ``API_SERVER_KEY`` a teammate's Hermes already uses to reach this one), plus a background
  sync loop that keeps this gateway and its configured peer converged.
"""

from __future__ import annotations

import asyncio
import json
import logging

from . import schemas, tools

logger = logging.getLogger(__name__)

SYNC_INTERVAL_S = 3.0


def _store():
    from .dashboard import herd_store

    return herd_store


def _wire_api_server(app, adapter) -> None:
    """Add Herd's peer route to the api_server aiohttp app (called at connect, before freeze)."""
    from aiohttp import web

    async def herd_sync(request: "web.Request") -> "web.Response":
        # The api_server's own Bearer API_SERVER_KEY check: only a gateway that holds this
        # gateway's key (the linked peer) can read or write Herd data here.
        denied = adapter._check_auth(request)
        if denied is not None:
            return denied
        try:
            body = await request.json()
        except (ValueError, json.JSONDecodeError):
            return web.json_response({"error": "Body must be JSON."}, status=400)
        store = _store()
        try:
            result = await asyncio.to_thread(store.handle_peer_sync, body)
        except store.HerdError as exc:
            return web.json_response({"error": exc.message}, status=exc.status)
        except Exception:  # noqa: BLE001 — never leak a stack trace to the network
            logger.exception("herd: peer sync failed")
            return web.json_response({"error": "Herd sync failed on this gateway."}, status=500)
        return web.json_response(result)

    async def herd_ping(request: "web.Request") -> "web.Response":
        denied = adapter._check_auth(request)
        if denied is not None:
            return denied
        store = _store()
        me = await asyncio.to_thread(store.identity)
        return web.json_response({"ok": True, "from": me, "v": store.PROTOCOL_VERSION})

    app.router.add_post(_store().PEER_SYNC_PATH, herd_sync)
    app.router.add_get("/herd/v1/ping", herd_ping)

    async def _start_sync_loop(_app) -> None:
        async def loop() -> None:
            store = _store()
            while True:
                try:
                    await asyncio.to_thread(store.sync_all)
                except Exception:  # noqa: BLE001 — keep syncing through transient failures
                    logger.debug("herd: sync pass failed", exc_info=True)
                await asyncio.sleep(SYNC_INTERVAL_S)

        task = asyncio.get_running_loop().create_task(loop(), name="herd-sync")
        _app["herd_sync_task"] = task

    async def _stop_sync_loop(_app) -> None:
        task = _app.get("herd_sync_task")
        if task is not None:
            task.cancel()

    app.on_startup.append(_start_sync_loop)
    app.on_cleanup.append(_stop_sync_loop)


def register(ctx):
    """Wire schemas to handlers and the peer endpoint. Never touches the network or the db."""
    ctx.register_tool(name="herd_list_channels", toolset="herd",
                      schema=schemas.HERD_LIST_CHANNELS, handler=tools.herd_list_channels)
    ctx.register_tool(name="herd_post", toolset="herd",
                      schema=schemas.HERD_POST, handler=tools.herd_post)
    ctx.register_tool(name="herd_read_channel", toolset="herd",
                      schema=schemas.HERD_READ_CHANNEL, handler=tools.herd_read_channel)
    ctx.register_platform_handler("api_server", _wire_api_server)
