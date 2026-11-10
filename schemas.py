"""Tool schemas — what the model reads (copy from docs/product/N-3-NAMING-COPY.md)."""

HERD_LIST_CHANNELS = {
    "name": "herd_list_channels",
    "description": (
        "List Herd channels and DMs this Hermes can see, with their ids and member names. "
        "Herd is the shared space where you, your user, your teammates and their Hermes "
        "agents talk across up to five machines."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

HERD_POST = {
    "name": "herd_post",
    "description": (
        "Post a message to a Herd channel or DM. Everyone in it, including people and agents on "
        "the other machine, will see it. Use for sharing results or handing off a task. "
        "To answer a specific message, pass its id as reply_to."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "description": "Channel name (e.g. 'general'), channel id, or the other person's name for a DM.",
            },
            "content": {"type": "string", "description": "The message text."},
            "task_id": {
                "type": "string",
                "description": (
                    "Optional: the Kanban task id this answer is about (e.g. 't_e7741438'), when you are "
                    "deliberately answering that task. Herd never guesses it from the message text — pass it "
                    "only when you mean it. The pane then shows the task id and title with the message."
                ),
            },
            "reply_to": {
                "type": "string",
                "description": (
                    "Message id to reply to — puts your message in that message's thread. "
                    "With reply_to, channel is optional (the message's own channel is used)."
                ),
            },
        },
        "required": ["content"],
        "additionalProperties": False,
    },
}

HERD_SEARCH = {
    "name": "herd_search",
    "description": (
        "Search the message history of every Herd channel and DM this Hermes holds, for example to check whether "
        "an error was seen before. Every word in the query must appear; the last word also matches a prefix. "
        "Returns the best matches with channel, author, time and a snippet. Pass a result's channel_id to "
        "herd_read_channel to read around it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Words to look for. Plain text, not search syntax."},
            "channel": {
                "type": "string",
                "description": "Optional: limit to one channel or DM (name, id, or the other person's name).",
            },
            "limit": {"type": "integer", "description": "How many results (1 to 25). Default 10."},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

HERD_READ_CHANNEL = {
    "name": "herd_read_channel",
    "description": (
        "Read recent messages from a Herd channel or DM, newest last. Use before replying or when "
        "asked to pick up a task from a channel. Each message has an id and a replies count; "
        "pass a message id as thread to read that message's replies."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "description": (
                    "Channel name (e.g. 'general'), channel id, or the other person's name for a DM. "
                    "Required unless thread is given."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "How many recent messages to return (1-100, default 20).",
                "minimum": 1,
                "maximum": 100,
            },
            "thread": {
                "type": "string",
                "description": "Message id to read the thread of: returns that message and its replies, oldest first.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}

HERD_SET_STATUS = {
    "name": "herd_set_status",
    "description": (
        "Tell your user, in one short phrase, what you are doing right now. They see it beside your "
        "work in the Herd pane. Use exactly one of: 'reading the code', 'writing the code', "
        "'reviewing', 'done', 'idle'. Set it when you start a piece of work and again when you finish. "
        "It clears itself after five minutes, so set it again during long work."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["reading the code", "writing the code", "reviewing", "done", "idle"],
                "description": "One of the five phrases.",
            }
        },
        "required": ["status"],
        "additionalProperties": False,
    },
}
