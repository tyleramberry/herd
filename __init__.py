"""Herd — multiplayer Hermes. Agent-side registration.

* Four agent tools (``herd_list_channels``, ``herd_post``, ``herd_read_channel``, ``herd_set_status``).
* The peer endpoints ``POST /herd/v1/sync`` and ``GET /herd/v1/ping`` on this gateway's
  ``api_server``, authenticated with Herd's OWN credential: this gateway's Herd secret
  (``HERD_SECRET``), never the gateway-wide ``API_SERVER_KEY``. Plus a background sync loop that
  keeps this gateway and its configured teammates (up to four) converged.
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


def _sync_pass(store) -> None:
    """One background sync pass, run with this profile's secret scope bound.

    Under Hermes's multiplex gateway ``agent.secret_scope.get_secret`` fails closed
    for any task that does not carry a profile scope. A request handler inherits one
    from its caller (which is why ``request_sync`` works); a task created at app
    startup does not, so without this binding every pass resolved the peer key as
    empty, wrote ``last_error`` and never synced. Best-effort: when the scope
    machinery is unavailable (standalone runs, tests) the pass still runs.
    """
    token = None
    reset = None
    try:
        from agent.secret_scope import build_profile_secret_scope, reset_secret_scope, set_secret_scope
        from hermes_constants import get_hermes_home

        home = get_hermes_home()
        token = set_secret_scope(build_profile_secret_scope(home), profile_home=str(home))
        reset = reset_secret_scope
    except Exception:  # noqa: BLE001 — scope is an enhancement, never a hard requirement
        logger.debug("herd: profile secret scope unavailable for the sync loop", exc_info=True)
    try:
        store.sync_all()
    finally:
        if token is not None and reset is not None:
            reset(token)


def _wire_api_server(app, adapter) -> None:
    """Add Herd's peer route to the api_server aiohttp app (called at connect, before freeze).

    ``adapter`` is intentionally unused: the platform handler factory passes it, but Herd no
    longer borrows the adapter's gateway-wide API_SERVER_KEY check — it checks its own secret.
    """
    from aiohttp import web

    def _denied(request: "web.Request"):
        """Herd's own Bearer check: the request must carry THIS gateway's Herd secret."""
        store = _store()
        if store.inbound_authorized(request.headers.get("Authorization")):
            return None
        message = "Invalid Herd secret (HERD_SECRET)" if store.herd_secret_set() else store.NO_LOCAL_SECRET
        # Same shape as the api_server adapter's 401: the desktop pane keys off error.code.
        return web.json_response(
            {"error": {"message": message, "type": "gateway_auth_error",
                       "code": "gateway_auth_failed"}}, status=401)

    async def herd_sync(request: "web.Request") -> "web.Response":
        # Only a gateway holding this gateway's Herd secret (the linked peer) can read or write
        # Herd data here. The gateway API_SERVER_KEY is not accepted.
        denied = _denied(request)
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
        denied = _denied(request)
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
                    await asyncio.to_thread(_sync_pass, store)
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


def _listen_command(raw_args: str, session_key: str = "", **_kw) -> str:
    """``/herd-listen`` (here) / ``/herd-listen off``: pick the chat that receives @mentions."""
    store = _store()
    if raw_args.strip().lower() in {"off", "stop", "none"}:
        store.set_mention_target("")
        return "Herd will no longer pass @mentions to an agent."
    if not session_key:
        return "Run /herd-listen inside the chat you want your agent to answer Herd mentions in."
    store.set_mention_target(session_key, "this chat")
    on = "on" if store.wake_enabled() else "OFF (turn on \"Let my agent answer @mentions\" in Settings > Plugins > Herd)"
    return ("Done. @mentions of you in Herd will be handed to this chat. "
            f"Mention wake is {on}. It also needs allow_gateway_injection: true for herd in config.yaml.")


def register(ctx):
    """Wire schemas to handlers and the peer endpoint. Never touches the network or the db."""
    ctx.register_tool(name="herd_list_channels", toolset="herd",
                      schema=schemas.HERD_LIST_CHANNELS, handler=tools.herd_list_channels)
    ctx.register_tool(name="herd_post", toolset="herd",
                      schema=schemas.HERD_POST, handler=tools.herd_post)
    ctx.register_tool(name="herd_read_channel", toolset="herd",
                      schema=schemas.HERD_READ_CHANNEL, handler=tools.herd_read_channel)
    ctx.register_tool(name="herd_set_status", toolset="herd",
                      schema=schemas.HERD_SET_STATUS, handler=tools.herd_set_status)
    ctx.register_platform_handler("api_server", _wire_api_server)
    ctx.register_command("herd-listen", _listen_command,
                         description="Let your agent in this chat answer Herd @mentions (or: off)",
                         args_hint="[off]")

    def _wake(session_key: str, text: str) -> bool:
        return bool(ctx.inject_message(text, role="user", session_key=session_key))

    _store().WAKE_HANDLER = _wake
