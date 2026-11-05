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
