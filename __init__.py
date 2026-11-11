"""Hermes Multiplayer — multiplayer Hermes. Agent-side registration.

* Four agent tools (``multiplayer_list_channels``, ``multiplayer_post``, ``multiplayer_read_channel``, ``multiplayer_set_status``).
* The peer endpoints ``POST /hermes-multiplayer/v1/sync`` and ``GET /hermes-multiplayer/v1/ping`` on this gateway's
  ``api_server``, authenticated with Hermes Multiplayer's OWN credential: this gateway's Hermes Multiplayer secret
  (``HERMES_MULTIPLAYER_SECRET``), never the gateway-wide ``API_SERVER_KEY``. Plus a background sync loop that
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
    from .dashboard import multiplayer_store

    return multiplayer_store


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
        logger.debug("hermes-multiplayer: profile secret scope unavailable for the sync loop", exc_info=True)
    try:
        store.sync_all()
    finally:
        if token is not None and reset is not None:
            reset(token)


def _wire_api_server(app, adapter) -> None:
    """Add Hermes Multiplayer's peer route to the api_server aiohttp app (called at connect, before freeze).

    ``adapter`` is intentionally unused: the platform handler factory passes it, but Hermes Multiplayer no
    longer borrows the adapter's gateway-wide API_SERVER_KEY check — it checks its own secret.
    """
    from aiohttp import web

    def _denied(request: "web.Request"):
        """Hermes Multiplayer's own Bearer check: the request must carry THIS gateway's Hermes Multiplayer secret."""
        store = _store()
        if store.inbound_authorized(request.headers.get("Authorization")):
            return None
        message = "Invalid Hermes Multiplayer secret (HERMES_MULTIPLAYER_SECRET)" if store.multiplayer_secret_set() else store.NO_LOCAL_SECRET
        # Same shape as the api_server adapter's 401: the desktop pane keys off error.code.
        return web.json_response(
            {"error": {"message": message, "type": "gateway_auth_error",
                       "code": "gateway_auth_failed"}}, status=401)

    async def multiplayer_sync(request: "web.Request") -> "web.Response":
        # Only a gateway holding this gateway's Hermes Multiplayer secret (the linked peer) can read or write
        # Hermes Multiplayer data here. The gateway API_SERVER_KEY is not accepted.
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
        except store.MultiplayerError as exc:
            return web.json_response({"error": exc.message}, status=exc.status)
        except Exception:  # noqa: BLE001 — never leak a stack trace to the network
            logger.exception("hermes-multiplayer: peer sync failed")
            return web.json_response({"error": "Hermes Multiplayer sync failed on this gateway."}, status=500)
        return web.json_response(result)

    async def multiplayer_pair(request: "web.Request") -> "web.Response":
        # No Hermes Multiplayer secret here: the one-time pairing code is the credential for this exchange. Wrong, used and expired
        # codes all get one reply, and five wrong tries pause pairing (see multiplayer_store.handle_pair_request).
        try:
            body = await request.json()
        except (ValueError, json.JSONDecodeError):
            return web.json_response({"error": "Body must be JSON."}, status=400)
        store = _store()
        try:
            result = await asyncio.to_thread(store.handle_pair_request, body)
        except store.MultiplayerError as exc:
            return web.json_response({"error": exc.message}, status=exc.status)
        except Exception:  # noqa: BLE001 — never leak a stack trace to the network
            logger.exception("hermes-multiplayer: pairing failed")
            return web.json_response({"error": "Hermes Multiplayer pairing failed on this gateway."}, status=500)
        return web.json_response(result)

    async def multiplayer_ping(request: "web.Request") -> "web.Response":
        denied = _denied(request)
        if denied is not None:
            return denied
        store = _store()
        me = await asyncio.to_thread(store.identity)
        return web.json_response({"ok": True, "from": me, "v": store.PROTOCOL_VERSION})

    # Served under the pre-rename /herd/v1/* too, so a teammate still on that build keeps syncing with us.
    for prefix in (_store().PEER_PATH_PREFIX, _store().LEGACY_PEER_PATH_PREFIX):
        app.router.add_post(prefix + "sync", multiplayer_sync)
        app.router.add_post(prefix + "pair", multiplayer_pair)
        app.router.add_get(prefix + "ping", multiplayer_ping)

    async def _start_sync_loop(_app) -> None:
        async def loop() -> None:
            store = _store()
            while True:
                try:
                    await asyncio.to_thread(_sync_pass, store)
                except Exception:  # noqa: BLE001 — keep syncing through transient failures
                    logger.debug("hermes-multiplayer: sync pass failed", exc_info=True)
                await asyncio.sleep(SYNC_INTERVAL_S)

        task = asyncio.get_running_loop().create_task(loop(), name="multiplayer-sync")
        _app["multiplayer_sync_task"] = task

    async def _stop_sync_loop(_app) -> None:
        task = _app.get("multiplayer_sync_task")
        if task is not None:
            task.cancel()

    app.on_startup.append(_start_sync_loop)
    app.on_cleanup.append(_stop_sync_loop)


def _listen_command(raw_args: str, session_key: str = "", **_kw) -> str:
    """``/multiplayer-listen`` (here) / ``/multiplayer-listen off``: pick the chat that receives @mentions."""
    store = _store()
    if raw_args.strip().lower() in {"off", "stop", "none"}:
        store.set_mention_target("")
        return "Hermes Multiplayer will no longer pass @mentions to an agent."
    if not session_key:
        return "Run /multiplayer-listen inside the chat you want your agent to answer Hermes Multiplayer mentions in."
    store.set_mention_target(session_key, "this chat")
    on = "on" if store.wake_enabled() else "OFF (turn on \"Let my agent answer @mentions\" in Settings > Plugins > Hermes Multiplayer)"
    return ("Done. @mentions of you in Hermes Multiplayer will be handed to this chat. "
            f"Mention wake is {on}. It also needs allow_gateway_injection: true for hermes-multiplayer in config.yaml.")


def _gateway_route_key(session_key: str) -> str:
    """The desktop pane stores the chat's bare id (``local-<hash>``), but the gateway files sessions under their
    route key (``agent:main:local:dm:local-<hash>``). A bare id is admitted and then silently dropped at dispatch
    ("injection was not routed"), so build the real key with the gateway's own function. Anything already a
    route key, or anything we cannot resolve, passes through unchanged."""
    key = (session_key or "").strip()
    if not key or key.startswith("agent:"):
        return key
    try:
        from gateway.config import Platform
        from gateway.session import SessionSource, build_session_key

        return build_session_key(SessionSource(platform=Platform.LOCAL, chat_id=key, chat_type="dm"))
    except Exception:  # noqa: BLE001 — older/newer hosts: hand over the key as stored
        logger.debug("hermes-multiplayer: could not build a route key for %r", key, exc_info=True)
        return key


def register(ctx):
    """Wire schemas to handlers and the peer endpoint. Never touches the network or the db."""
    ctx.register_tool(name="multiplayer_list_channels", toolset="hermes-multiplayer",
                      schema=schemas.MULTIPLAYER_LIST_CHANNELS, handler=tools.multiplayer_list_channels)
    ctx.register_tool(name="multiplayer_post", toolset="hermes-multiplayer",
                      schema=schemas.MULTIPLAYER_POST, handler=tools.multiplayer_post)
    ctx.register_tool(name="multiplayer_read_channel", toolset="hermes-multiplayer",
                      schema=schemas.MULTIPLAYER_READ_CHANNEL, handler=tools.multiplayer_read_channel)
    ctx.register_tool(name="multiplayer_set_status", toolset="hermes-multiplayer",
                      schema=schemas.MULTIPLAYER_SET_STATUS, handler=tools.multiplayer_set_status)
    # multiplayer_search is built (tools.multiplayer_search) but not registered: the catalog's locked tool scope (TC-0.8) is
    # four tools. Registering it means re-approving that scope first.
    ctx.register_platform_handler("api_server", _wire_api_server)
    ctx.register_command("multiplayer-listen", _listen_command,
                         description="Let your agent in this chat answer Hermes Multiplayer @mentions (or: off)",
                         args_hint="[off]")

    def _wake(session_key: str, text: str) -> bool:
        return bool(ctx.inject_message(text, role="user", session_key=_gateway_route_key(session_key)))

    _store().WAKE_HANDLER = _wake
