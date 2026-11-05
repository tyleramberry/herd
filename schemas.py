"""Tool schemas — what the LLM sees."""

HERD_POST_SCHEMA = {
    "name": "herd_post",
    "description": (
        "Post a message into a Herd channel — the shared multiplayer workspace where the "
        "user, their teammates, and teammates' Hermes agents talk. Use this to share a "
        "result, status update, or question with the team. The message appears live in "
        "every connected Hermes desktop."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "description": "Channel name (e.g. 'general') or channel id.",
            },
            "content": {"type": "string", "description": "Message text to post."},
            "author_name": {
                "type": "string",
                "description": "Optional display name for the agent (defaults to 'Hermes').",
            },
        },
        "required": ["channel", "content"],
        "additionalProperties": False,
    },
}

HERD_LIST_CHANNELS_SCHEMA = {
    "name": "herd_list_channels",
    "description": "List the Herd channels (id, name, topic, message count) so you can pick where to post.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}
