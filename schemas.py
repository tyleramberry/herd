"""Tool schemas — what the model reads (copy from docs/product/N-3-NAMING-COPY.md)."""

HERD_LIST_CHANNELS = {
    "name": "herd_list_channels",
    "description": (
        "List Herd channels and DMs this Hermes can see, with their ids and member names. "
        "Herd is the shared space where you, your user, a teammate and the teammate's Hermes "
        "agent talk across two machines."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

HERD_POST = {
    "name": "herd_post",
    "description": (
        "Post a message to a Herd channel or DM. Everyone in it, including people and agents on "
        "the other machine, will see it. Use for sharing results or handing off a task."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "description": "Channel name (e.g. 'general'), channel id, or the other person's name for a DM.",
            },
            "content": {"type": "string", "description": "The message text."},
        },
        "required": ["channel", "content"],
        "additionalProperties": False,
    },
}

HERD_READ_CHANNEL = {
    "name": "herd_read_channel",
    "description": (
        "Read recent messages from a Herd channel or DM, newest last. Use before replying or when "
        "asked to pick up a task from a channel."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "description": "Channel name (e.g. 'general'), channel id, or the other person's name for a DM.",
            },
            "limit": {
                "type": "integer",
                "description": "How many recent messages to return (1-100, default 20).",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["channel"],
        "additionalProperties": False,
    },
}
