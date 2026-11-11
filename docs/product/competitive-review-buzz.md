# Hurd ↔ Buzz: gap review (handoff)

**Purpose:** what Hurd must build to compete with Buzz, ranked. Written as a work
brief — each item names the gap, their version, ours today, and the minimum bar.
**Reviewed:** Buzz `block/buzz` @ `44b3c48` and `block/buzz-app` (1.0), against
Hurd `~/src/herd` @ `49adff0`. Clones are disposable, in `~/.hermes/cache/scratch/`.
**Read this with:** `README.md` (our own "doesn't do yet" list) and
`docs/TASKBOARD.md` (the ceilings we already admit).

---

## 0. Scale — the frame for everything below

| | Hurd | Buzz |
|---|---|---|
| Shape | Hermes plugin: Python backend + ESM desktop half | Rust monorepo (~34 crates) + Tauri/React desktop + Flutter mobile + CLI/MCP |
| Size | 3,721 LOC core (store 1,784 · desktop 1,135 · rest ~700) | Desktop alone: 725 `.tsx` / ~347k LOC; 139 event `KIND_` constants in `buzz-core/src/kind.rs` |
| Substrate | Local SQLite per gateway, HTTP peer polling every 3s, per-peer shared secret | Postgres+Redis relay, signed Nostr events, WebSocket, 139 kinds, hash-chained audit log |
| Desktop surface | 3 contribution areas: page, sidebar nav, right pane (340px) | 7 product surfaces; ~16 plugin capability services |

Parity is off the table at ~1% of the code. The question is which gaps are
**load-bearing for the core promise**: humans and agents sharing one room, with
no relay to host.

### Where we're already ahead (don't regress these)

- **Zero infrastructure.** `hermes plugins install` vs their docker-compose.
- **Agent/human badge already ships.** Buzz's `VISION.md` still says *"Bot role
  on agent channel membership. Visual badges are next."*
- **Documented threat model.** Peer-secret scoping, refusing cleartext
  non-loopback `http://`, never following redirects, `HERD_SECRET` ≠
  `API_SERVER_KEY`. Their docs are thinner here.
- **DM → channel promote** (`share_dm`, protocol v2) — a real move Buzz lacks.

---

## 1. The four critical features

### 1. Search — the whole agent story

- **Their version:** ⌘K full-text search over messages, patches, workflow runs.
  The headline demo is "have we seen this error before?" → agent pulls six months
  of history and answers with receipts.
- **Ours today:** `herd_read_channel` only, capped at 100 messages, one channel,
  no query parameter. No search surface anywhere in the UI.
- **Minimum to compete:** SQLite FTS5 virtual table over message bodies + a
  `herd_search` agent tool + `GET /api/plugins/hermes-multiplayer/search?q=` + a ⌘K surface.
  FTS5 is already available in the store; this is the highest-leverage item here.
- **Why it matters:** without search the agent is a parrot in the current
  channel. With it, it becomes the thing Buzz is actually selling.

### 2. Presence, unread and notifications — nothing tells you something happened

- **Their version:** read-state/unread ownership, an Activity page, per-category
  OS notification prefs, sounds, silent-banner rules, and agent avatars that
  morph into a three-dot "working" pill.
- **Ours today:** no unread state, no read receipts, no OS notification, no
  badge; the pane just polls every 3s. `herd_set_status` holds one of 5 phrases
  for a 5-minute TTL **in gateway process memory and never syncs to peers** — so
  Brooklyn cannot see that Tyler's agent is working.
- **Minimum to compete:** sync the status phrase to peers as a real row (or
  ephemeral sync field), add per-channel unread counts, and fire
  `ctx.os.notify` on an incoming message while the pane is not visible.
- **Why it matters:** it's the difference between a live room and a polling table.

### 3. Pairing — joining is a cliff

- **Their version:** pairing CLI + pair-relay, community picker, onboarding
  steps, channel templates.
- **Ours today:** type the teammate's tailnet URL, paste their secret into a
  masked Settings field, restart the gateway, and read a cleartext warning.
  Our README needs a 6-step numbered procedure plus a "linked before this
  change?" caveat.
- **Minimum to compete:** a one-time pairing code — our backend mints a
  short-lived token, the peer exchanges it for a key and stores it. Removes the
  worst adoption cliff in the product.

### 4. Signed events — the mesh can't grow, and can't prove anything

- **Their version:** every action is a signed event in one append-only log with
  a hash-chained audit trail; identity is a keypair, ordering and history are
  the log's job.
- **Ours today:** identity is `gateway_id`, a message id is `(gateway, seq)`,
  and our README states plainly that the shared secret *"authenticates the link
  to each teammate, not the individual caller"* — a linked peer is trusted to
  relay any origin it names. Ceilings: 5 gateways, 4 hardcoded emoji, 2-person
  DMs, no private channels, no roles/permissions ("NOT BUILT" per TASKBOARD).
- **Minimum to compete:** an Ed25519 keypair per gateway and a message =
  signed event (`{gateway_pubkey, seq, kind, body}` + signature, id = hash).
  One table, one verify function, protocol v3.
- **Why it matters:** it is the *only* path to edit, delete, tombstone
  convergence, read-state, audit, and a mesh where you can't assume every peer
  is honest. Fine for two brothers today; blocks everything above 5 gateways.

### The one architectural bet

**Signed events (gap 4).** It is not a refactor — it is the precondition. Edit,
delete, read-state, audit and multi-hop relay are all downstream of "every
action is a signed event in one log." Build it before the features that need it,
not after.

---

## 2. UI updates

We register 3 of the 16 available Hermes desktop contribution areas. Everything
below is registerable today with no core changes — verified against
`website/docs/developer-guide/desktop-plugin-sdk.md` and
`apps/desktop/src/sdk/areas.ts`.

| What to add | Hermes area | Ours today | Why |
|---|---|---|---|
| Search page + ⌘K command | `PALETTE_AREA` + a route | absent | Biggest demo payoff, near-zero risk. |
| Unread counter | `STATUSBAR_AREAS.right` | absent | Only live signal that the room moved. |
| Nav badge | **not supported** — `SIDEBAR_NAV_AREA` payload is only `{path,label,codicon}` | absent | Buzz's pages carry a `badge`; Hermes' nav doesn't. Use the status bar or an in-page chip, or upstream the slot. |
| Native notification / toast | `ctx.os.notify`, `host.notify` | absent | Nothing can pull you back to the pane. |
| Channel settings: rename, topic, member picker, private toggle | `SETTINGS_PLUGINS_AREA` (`ctx.registerSettingsPage`) or `Dialog*` in-pane | members are route-only; README admits "no picker for it yet" | Buzz's create-channel dialog has search + filters + private. |
| Attachments, emoji picker, markdown, draft persistence | `COMPOSER_AREAS.*` (middleware + attachment providers) | bare textarea; 4 hardcoded reactions | Composer is where a chat app is judged. |
| Dock threads/tasks into the main zone | `host.openWorkspace` + `WORKSPACE_PAGE_HEADER_AREA` | everything in a 340px right pane | A 340px pane cannot be a workspace; Buzz runs channel-list / messages / thread as three columns on the page. Pane = peek, page = product. |
| Message edit / delete / mark unread | data layer — needs signed events (gap 4) | absent | Most visible hole in the message row. |
| Task / link panels | `Contribute` + `TOOL_MEDIA_RENDERER_AREA` | `TaskBadge` only | The read path already exists; a panel beats a badge. |
| Keybinds: open Herd, new message | `KEYBINDS_AREA` | absent | Slack muscle memory. |
| Design-system pass | UI kit (`Badge`, `Dialog*`, `SearchField`, `Kbd`, …) | hand-rolled `text-(--ui-text-tertiary)` + tailwind-ish classes beside SDK components | It reads bolted-on next to core panes. |

### Not on this list, deliberately

More gateways, mobile, push, custom emoji, voice huddles, workflow YAML, git
hosting, canvases, audit log. Right for Buzz, out of scope for a household mesh
— revisit after gap 4 makes them cheap.

---

## 3. If you do four things

1. **Search** (`herd_search` + ⌘K) — unlocks the agent story.
2. **Sync agent status + unread + OS notifications** — makes it feel live.
3. **Pairing code** — kills the adoption cliff.
4. **Signed events (protocol v3)** — the only path past 5 gateways, edit/delete,
   and audit.

---

## 4. Rival context worth knowing

`block/buzz-app/docs/hermes-agent-research.md` shows Buzz already ships a
**Hermes Agent preset** (`hermes-acp`, Tier 2, with
`HERMES_ACP_SKIP_CONFIGURED_MCP=1`). Buzz treats Hermes as one harness among
Goose / Codex / Claude Code. So the frame is not "be Buzz" — it is "be the room
Hermes agents and their humans share, without a relay to host." Search, presence
and pairing serve that; a Nostr relay rewrite does not.
