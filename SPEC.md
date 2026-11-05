# Herd — Day 1 scaffold spec

Multiplayer workspace plugin for Hermes: multiple humans and their Hermes agents
(across machines, via `hermes peer`) share channels and DMs. Each gateway runs
this plugin; a message posted on gateway A must appear in the channel view on
gateway B (2-gateway fan-out, Thursday milestone).

Unified package layout (both SDKs, one installable folder):

```
herd/
├── plugin.yaml            # agent plugin manifest
├── __init__.py            # register(ctx): agent-side tools
├── schemas.py             # tool schemas the LLM sees
├── tools.py               # tool handlers
├── dashboard/
│   ├── manifest.json      # { "name": "herd", "api": "plugin_api.py" }
│   └── plugin_api.py      # FastAPI APIRouter -> /api/plugins/herd/
└── desktop/
    └── plugin.js          # desktop half: route + pane, ctx.rest/ctx.socket
```

## Hard constraints (catalog admission — violations decline the PR)

- `desktop/plugin.js` imports ONLY `@hermes/plugin-sdk`, `react`,
  `react/jsx-runtime`. No other specifier, static or dynamic. No eval, no
  prototype patching, no touching app markup (`data-slot` etc.), no core-UI
  restyling. Our UI lives in OUR pane/route only.
- No JSX syntax in `desktop/plugin.js` (loaded uncompiled). Use `jsx()` /
  `jsxs()` from `react/jsx-runtime`.
- Never hardcode colors. Use theme variables (`var(--ui-text-secondary)` etc.).
- No secrets in code. The plugin talks only to the gateway and its own
  `/api/plugins/herd/` backend namespace.
- No core overrides: never assign to Hermes modules, `sys.modules`, or core
  dicts/functions at runtime (`hermes plugins validate` no-core-override check).
- Tools return JSON strings, accept `**kwargs`. Every tool registered by
  `register()` must be listed in `provides_tools` in `plugin.yaml`.
- `hermes plugins validate .` and `hermes plugins doctor . --ci` must pass.

## Backend (dashboard/plugin_api.py)

SQLite storage (prefer the installed Hermes helpers `plugin_data_dir()` /
`plugin_db()` if importable from the gateway process — check
~/.hermes/hermes-agent; otherwise fall back to a `herd.db` under the plugin
data dir, never the repo). Tables:

- `channels(id TEXT PK, name TEXT UNIQUE, topic TEXT, created_at TEXT)`
- `messages(id TEXT PK, channel_id TEXT, author_type TEXT, author_name TEXT,
  gateway_id TEXT, content TEXT, created_at TEXT)` — message ids are
  client-generated UUIDs, globally unique, so 2-gateway fan-out can converge
  without collisions (INSERT OR IGNORE).
- `participants(id TEXT PK, display_name TEXT, gateway_id TEXT, kind TEXT,
  last_seen TEXT)`

Routes (all under /api/plugins/herd/):

- GET  /channels            -> list channels (with message counts)
- POST /channels            -> create channel {name, topic}
- GET  /channels/{id}/messages?after=<iso> -> messages
- POST /channels/{id}/messages {content, author_name, author_type,
  gateway_id} -> insert; then broadcast_plugin_event("herd",
  "message.created", {...}) so every connected desktop refreshes.
- GET  /participants        -> list participants
- POST /participants        -> register/heartbeat a participant

Thursday fan-out design (document in README; schema supports it now):
- every message row carries the originating `gateway_id`
- desktop half subscribes via `host.onEvent('plugin.herd.message.created')`
  and invalidates the React Query cache; polling fallback required (sockets
  no-op on OAuth remotes)
- cross-gateway sync itself (gateway A <-> B push/pull) is a later step;
  Day 1 only needs local round-trip + event broadcast

## Desktop half (desktop/plugin.js)

- `defaultEnabled: false` (unified-package desktop half ships opt-in).
- A full route at `/herd` (ROUTES_AREA) + sidebar nav row (SIDEBAR_NAV_AREA,
  codicon e.g. 'comment-discussion') + a right pane (PANES_AREA).
- Page: channel sidebar (list from ctx.rest('/channels')), message view for
  the selected channel, composer (Textarea + Button from the SDK UI kit).
- Empty state visible: no channels yet -> EmptyState component with a
  "create channel" affordance.
- Data via useQuery/useMutation + queryClient.invalidateQueries; subscribe to
  the backend event inside register() and invalidate; poll fallback every few
  seconds is fine.
- All timers/listeners via ctx.setTimeout / ctx.setInterval /
  ctx.addEventListener — never bare window globals.

## Verification (must actually run before commit)

```
hermes plugins validate .
hermes plugins doctor . --ci
python -m pytest tests/ -q        # backend tests (FastAPI TestClient + temp sqlite)
node --check desktop/plugin.js   # syntax check (plain ESM)
```
