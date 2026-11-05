"""Herd agent-side plugin registration."""

from . import schemas, tools


def register(ctx):
    """Register Herd tools with the Hermes gateway."""
    ctx.register_tool(
        name="herd_post",
        toolset="herd",
        schema=schemas.HERD_POST_SCHEMA,
        handler=tools.herd_post,
    )
    ctx.register_tool(
        name="herd_list_channels",
        toolset="herd",
        schema=schemas.HERD_LIST_CHANNELS_SCHEMA,
        handler=tools.herd_list_channels,
    )
    # Gateway identity comes from plugin settings (plugins.entries.herd.settings.gateway_id).
    # Imported lazily to keep registration cheap; a missing settings tree never breaks it.
    try:
        from .dashboard import plugin_api

        plugin_api.set_gateway_id(ctx.get_config("gateway_id") or None)
    except Exception:  # noqa: BLE001
        pass
