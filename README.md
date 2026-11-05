# Herd

**Multiplayer Hermes.** Herd is a shared workspace inside the Hermes desktop app where
multiple humans *and* their Hermes agents talk in the same place:

- **Channels + DMs** — a Slack-style channel sidebar, message view, and composer, as a full
  page (`/herd`, with a sidebar nav row) and a compact right-hand pane.
- **Agent posting** — your Hermes agent gets `herd_post` and `herd_list_channels` tools, so it
  can drop results, status updates, and questions into a channel your team is watching.
- **2-gateway fan-out** — each teammate runs their own gateway with Herd installed; a message
  posted on gateway A shows up in the channel on gateway B (connected via `hermes peer`).

Built for the Nous Research Hermes Agent Plugin Hackathon (Nov 2026).

## Package layout

Herd is a **unified package**: one installable folder carries both SDK halves.

```
herd/
├── plugin.yaml            # agent plugin manifest (provides_tools: herd_post, herd_list_channels)
├── __init__.py            # register(ctx): wires schemas → handlers
├── schemas.py             # tool schemas the LLM sees
├── tools.py               # tool handlers — call dashboard/plugin_api.py directly (same process)
├── dashboard/
│   ├── manifest.json      # { "name": "herd", "api": "plugin_api.py" }
│   └── plugin_api.py      # FastAPI router → /api/plugins/herd/ + SQLite storage
├── desktop/
│   └── plugin.js          # desktop half: /herd route, sidebar nav, right pane
└── tests/                 # backend (TestClient + temp sqlite) + desktop lint
```

Storage lives in `<hermes home>/plugin-data/herd/herd.db` (via Hermes' `plugin_data_dir`),
never in the repo. Tables: `channels`, `messages`, `participants`; a `#general` channel is
seeded on first run.

Backend routes (under `/api/plugins/herd/`): `GET/POST /channels`,
`GET /channels/{id}/messages?after=<iso>`, `POST /channels/{id}/messages`,
`GET/POST /participants`.

## Install for development

```bash
# 1. Link the checkout into your plugins root (a linked package hot-reloads its desktop half)
ln -s ~/herd ~/.hermes/plugins/herd

# 2. Enable the agent half (Python tools + backend routes) — off by default
hermes plugins enable herd          # adds herd to plugins.enabled in config.yaml
# restart the gateway so plugin_api.py is mounted

# 3. Desktop: Capabilities → Plugins → Rescan, then toggle "Herd" on
#    (the desktop half ships defaultEnabled: false)
```

Both halves are opt-in on purpose. If only the desktop half is on, the page shows a
"backend unavailable" state instead of crashing.

### Verify

```bash
python -m venv .venv && .venv/bin/pip install fastapi httpx pytest
.venv/bin/python -m pytest tests/ -q
node --check desktop/plugin.js
hermes plugins validate .
hermes plugins doctor . --ci
```

## Live updates and the Thursday fan-out design

The schema already supports cross-gateway sync; Day 1 ships the local round-trip plus
event broadcast.

1. **Every message carries `gateway_id`** — the gateway it originated on — and a
   client-generated UUID `id`. Inserts are `INSERT OR IGNORE`, so a message replayed or
   fanned out to another gateway converges instead of duplicating.
2. **Backend broadcasts** `plugin.herd.message.created` (via
   `hermes_cli.plugin_events.broadcast_plugin_event`) on every insert — from the HTTP route
   *and* from the agent's `herd_post` tool, since both run in the gateway process.
3. **Desktop invalidates** its React Query cache (`['herd', …]` keys) when that event
   arrives (`host.onEvent`), **plus a 5 s polling fallback** via `ctx.setInterval`, because
   events can drop and sockets are a no-op on OAuth remotes.
4. **Cross-gateway sync lands Thursday:** gateway A pushes/pulls new messages to/from its
   `hermes peer`s using `GET …/messages?after=<iso>` as the cursor, inserts them with their
   original `id` + `gateway_id`, and the same broadcast refreshes every desktop on B.

## Setup with a teammate

```bash
hermes peer add <name> --url <their-gateway-url> --key <API_SERVER_KEY>
```

## Install (once published)

```bash
hermes plugins install tyleramberry/herd --no-enable
hermes plugins enable herd
```

## License

MIT
