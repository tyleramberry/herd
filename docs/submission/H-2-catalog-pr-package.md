# H-2 — Catalog PR Package: Herd (DRAFT v7, Nov 7 — PIN-READY under F-3 REVISED: open on Tyler's go, bump later)

> **Status: PIN-READY (F-3 REVISED).** No freeze — the PR opens on **Tyler's one-screen go**; re-pin `sha:`
> to the newest head **immediately before opening** and before each later bump (last bump **Nov 10 18:00 MST**).
> **GATE CHANGE (F-3 REVISED, `docs/pm/F-3-gate-REVISED.md`):** the Nov 8 freeze is **cancelled**. The PR
> **opens as soon as this package is pin-ready** — no freeze wait — and later improvements go in as
> **SHA-bump PRs** (catalog rule 4). **Last pin bump: Nov 10, 18:00 MST.** Tyler approves *opening* the PR
> (one screen: what is submitted, the pin, the disclosures); he is informed, not asked, at form submission.
>
> **Pin: `cd6d46cc5f324ade11a814fa50889ce33324c607`** (`origin/main` HEAD at this pass, includes #45 B1, #41 S-15, #46 S-16).
> Verified at that SHA: `hermes plugins validate . --install-deps` → **Validation passed**; draft entry →
> **`catalog_audit: 0 FAIL, 0 WARN`**, 4 tools. Re-pin to the newest head before actually opening (main
> moves daily until Nov 10) — Q-11 owns the pin re-verify.
> Target: add ONE file `plugin-catalog/herd.yaml` to `NousResearch/hermes-agent`.

## 0. Pin-readiness block (added Nov 7 from QA's pre-flight audit)

**H-2 is pin-ready** (F-3 REVISED: no freeze). Three gates:

| # | Gate | State | Owner |
|---|---|---|---|
| 1 | **B1 fix merged** (`herd_store.py` — the `open_credentialed_url` import + `urlopen` fallback are **deleted**; `_NoRedirect` handler + module-level `_OPEN_PEER` opener added; no manifest/tool/env/secret change) | **MERGED** — #45 landed on `main` @ `5686f0b` (QA-confirmed; `_NoRedirect`/`_OPEN_PEER` present, no `urllib_security` import anywhere). Pre-fix `61c9068` stays non-pin-valid. | ✅ closed |
| 2 | **Real 40-char SHA** — `cd6d46cc5f324ade11a814fa50889ce33324c607`, verified to contain #45 B1, #41 S-15 and #46 S-16 | ✅ closed (re-pin at open) | Herald |
| 3 | **Media** — `docs/media/*` is **empty** (`git ls-files docs/media` → nothing); the freeze no longer exists, so "before the freeze commit" now means "before the commit being pinned" | **DECIDED: ship WITHOUT `image:`/`screenshots:`.** Stills may be captured in the Nov 8 session and added via a SHA-bump PR; never link a file absent at the pin | Herald |

**Decision on media (rule-safe default):** the catalog treats `image`/`screenshots` as *cosmetic*, and a
link to a file that does not exist at the pinned SHA renders a broken gallery. So: **ship the entry
WITHOUT `image:` and `screenshots:` unless real files are committed to the pin.** If the Nov 8 recording
session yields usable captures, commit them to `docs/media/` **before** the freeze commit and pin those
URLs to the same SHA. Never reference a file that is not in the pinned tree.

**Disclosure corrections this PR carries** (rule 13 accuracy — both found by the audit):
- `README.md:15` listed **reactions** under "What it doesn't do (yet)". **RESOLVED in PR #45**: verified at the PR head — the line now reads "What it doesn't do (yet): more than two gateways, search, notifications." Keep it that way at the pin.
- `README.md:63` claimed the key "drops" on a cross-host redirect — false on the old fallback. **RESOLVED in PR #45**: the fix refuses redirects outright and the README now says so (exact wording in §2). The earlier candidate wordings (refuse-redirects / helper-only) are retired — **the helper-only wording is now WRONG and must never be used**:
  - *(refuse-redirects fix — audit's recommended one)*: "Outbound sync sets the bearer header only for
    the teammate gateway URL you configured; a redirect from that URL is **refused, never followed**, so
    the key is never re-sent to another host (a redirecting peer shows an HTTP 30x error)."
  - *(helper-only path)* — **RETIRED, do not use.** PR #45 deleted that import, so this sentence would
    describe code that is not in the tree.
  **No "credential is dropped on redirect" claim may remain unless it is true for every path in the
  pinned tree.**
- **WARN 3 (audit):** `scripts/qa/catalog_audit.py:176` shells out to `git` via `subprocess`, while the PR
  description says "Shell commands: none". Either **disclose** it as a dev-only script under `scripts/qa/`
  or leave `scripts/qa/` out of the pinned tree. Runtime files still shell out to nothing.

## 1. herd.yaml

```yaml
name: herd
title: Herd
description: >-
  Multiplayer Hermes. Channels and DMs where you, a teammate, and both of
  your Hermes agents work together across two machines.  # N-3 copy
repo: https://github.com/tyleramberry/herd
sha: cd6d46cc5f324ade11a814fa50889ce33324c607  # PIN CANDIDATE (origin/main HEAD, Nov 7; includes #45 B1, #41 S-15, #46 S-16). Re-pin to the newest head immediately before opening; Q-11 re-verifies the pin gate.
tier: community
category: desktop  # shelf options: desktop|memory|platform|web|tools|voice|automation|models|general. Herd is a desktop pane, so "desktop" (was "platform", which is the messaging-platform shelf)
maintainer: tyleramberry
version: "0.1.0"  # QUOTED; must match plugin.yaml at the pinned commit
requires_hermes: ">=0.22.0"  # Sentry, Nov 5: oldest release verified to have every core API Herd uses (Tyler's Mac runs 0.22.0). VERIFIED Nov 5: plugin.yaml on main carries the same floor (PRs #10/#11, rule 14)
docs_url: https://github.com/tyleramberry/herd#readme
# platforms: omit unless macOS-only
# subdir: omit (plugin at repo root)
# image: https://raw.githubusercontent.com/tyleramberry/herd/<sha>/docs/media/banner.png  # DEFAULT = OMITTED. docs/media is EMPTY on main (audit WARN 5); a link to a file missing at the pin is a broken gallery.
# screenshots:  # add ONLY if real files are committed to docs/media/ before the freeze commit, pinned to the same sha
#   - https://raw.githubusercontent.com/tyleramberry/herd/<sha>/docs/media/channel-two-machines.png
#   - https://raw.githubusercontent.com/tyleramberry/herd/<sha>/docs/media/agent-posts-to-channel.png
capabilities:
  # Key names per the live entry schema: provides_tools / provides_hooks / provides_middleware / requires_env
  # (draft v1 used tools/hooks/middleware, which is wrong). Must match what the plugin registers at the pin (rule 6).
  provides_tools: [herd_list_channels, herd_post, herd_read_channel, herd_set_status]  # 4 tools — VERIFIED vs plugin.yaml on origin/main (Nov 7, after S-15 #41). catalog_audit.py must show 4, not 3 (Sentry TC-0.8)
  provides_hooks: []        # VERIFIED none in plugin.yaml on main
  provides_middleware: []   # VERIFIED none in plugin.yaml on main
  requires_env: []          # VERIFIED none: the peer key is a config_schema secret (HERD_PEER_KEY), not requires_env
```

## 2. PR description (draft)

### What it does
Herd is multiplayer Hermes: channels and direct messages inside the Hermes
desktop app where humans and their Hermes agents collaborate across machines.
You connect a teammate's Hermes under **Settings > Plugins > Herd** (their
gateway URL and API key). Herd then gives you shared channels in the desktop app: agents on both machines can exchange messages and hand work to
each other; both humans see the same thread. Built for the Nous Research
Hermes Agent Plugin Hackathon (Nov 2026).

**What Herd adds over core:** Core Group Chat and `hermes peer dm` connect one
person's bots across their machines. Herd connects two people: each keeps their
own Hermes, credentials and approvals, and both humans and both agents share
one persistent channel.

### Hermes surfaces used
<!-- v3: verified against plugin.yaml + tree on main (PRs #9–#13 merged). Re-check at freeze. -->
- Agent tools: `herd_post`, `herd_read_channel`, `herd_list_channels`, `herd_set_status` (exact names from plugin.yaml — VERIFIED Nov 7; **4 tools**, matching S-15)
- Promote a DM to a channel — a desktop action (local-only route `POST /api/plugins/herd/channels/{id}/share`); the copy reaches the teammate over the existing `POST /herd/v1/sync` write path as a channel-create + message-replay payload (`PROTOCOL_VERSION` 1 → 2; copied rows carry `promoted_from`, the source DM id). **(S-13 #37 merged — no capability change; promote adds no tool. Names verified against the pinned tree: `dashboard/plugin_api.py` exposes `/channels/{channel_id}/share`; `herd_store.py` carries the `promoted_from` column. The *proof beat* stays staged in H-6 pending the two-real-Mac TC-10.4 gate.)**
- Kanban link: an agent's answer carries a task badge (task id + title, read-only) that opens the `herd` board — board-level per the PM ruling (#47); per-task deep links are post-hackathon. **(S-16 #46 merged; `capabilities:` unchanged — no new tool)**
- Agent status: `herd_set_status` lets an agent set one coarse phrase (reading the code / writing the code / reviewing / done / idle) shown beside its in-flight work; per-message human/agent badges are rendered in the pane. (S-15 #41 merged)
- Chat command: `/herd-listen` (and `/herd-listen off`) registered via `ctx.register_command` — picks the chat that receives @mentions (S-7, PR #13)
- Opt-in agent turns for @mention wake: teammate mention → `ctx.inject_message` (needs the user's `allow_gateway_injection` permission; off by default via `mention_wake: false`)
- `config_schema` settings (display_name, peer_name, peer_url, peer_key secret, mention_wake), rendered by Desktop under Settings > Plugins > Herd
- No hooks, no middleware, no CLI commands (`/herd-listen` is a plugin chat command, not CLI)
- Desktop plugin surface (desktop/plugin.js) via the plugin SDK only

### Rule 13 disclosures
<!-- v3: lines below verified against the tree on main (Nov 5); keep only lines true at the pinned commit at freeze. -->
- **Network calls:** only to the one teammate gateway URL entered in settings, at `POST <url>/herd/v1/sync`. No third-party services. <!-- grep verified Nov 5; re-run at freeze -->
- **Long-running background processes:** a sync loop runs inside the gateway process while the API server is up — pushes outgoing messages and polls the teammate's gateway every 3 seconds (does nothing when no teammate is configured). The desktop pane polls its own backend every 3 seconds and asks it to sync every 10 seconds. <!-- intervals VERIFIED vs README/tree Nov 5 -->
- **Agent turns (opt-in only):** if the user enables @mention wake (`mention_wake: true` + `allow_gateway_injection: true`), a teammate's mention is injected into a user-chosen chat via Hermes's `inject_message`. Off by default.
- **Stored credentials:** one peer API key, declared as a `config_schema`
  secret (`peer_key`, env `HERD_PEER_KEY`) and stored by Hermes; Herd reads it
  only via `agent.secret_scope.get_secret`. Set under Settings > Plugins > Herd.
- **Reads outside plugin data:** to label an agent's answer, the Herd pane reads a task's title from the local Kanban database at `~/.hermes/kanban/boards/<slug>/kanban.db` — **read-only**, never written, no schema assumptions; if the file is missing or locked the pane shows the task id only. The id itself is passed explicitly by the agent and travels with the message in the normal sync payload; a peer that predates the field ignores it. <!-- README verbatim (canonical, CA-5). S-16 #46, Q-8 = YES; replaces the old "reads outside plugin data: none" line (never keep both). Verified at the pin: dashboard/kanban_tasks.py opens a mode=ro URI, busy_timeout 250, and issues exactly `SELECT title FROM tasks WHERE id = ?`; board-level click per PM ruling #47. -->
- **Shell commands:** none **in the runtime files** (`tools.py`, `__init__.py`, `schemas.py`, `dashboard/`). <!-- audit WARN 3: scripts/qa/catalog_audit.py:176 shells out to `git` via subprocess; disclose it as a dev-only script or leave scripts/qa/ out of the pin -->
- **Peer key on redirect (B1) — SETTLED (PR #45, verified at its head):** *"Outbound sync never follows a redirect: a 3xx from your teammate's gateway is refused, so the key is never re-sent to another host (a redirected peer shows as \"The peer answered HTTP 30x\" instead of being followed)."* Mirror this sentence into README + PR description **verbatim** at the pin. Do **not** name `hermes_cli.urllib_security.open_credentialed_url` anywhere — that import is deleted from the tree; a disclosure naming it would itself be inaccurate. Same-origin POST still returns 200; a redirecting peer now surfaces as an error rather than being silently followed.",
- **Stored-secret path unchanged:** `peer_key` remains a `config_schema` secret read via `agent.secret_scope.get_secret`; PR #45 adds no env var and removes the only core-helper import on this path.
- **Sync protocol version:** `PROTOCOL_VERSION` is **2** at this tree (S-13 promote, #37): a promoted DM is copied to a new channel and delivered over the existing `POST <url>/herd/v1/sync` write path; copied rows carry `promoted_from` (the source DM id), and a version **1** peer simply ignores the extra field (no 500, no corruption). The version is bumped in exactly **one** place and is readable from `/herd/v1/ping` + `/status`; **peers do not enforce `v`** — `handle_peer_sync` reads no version field, so a newer-protocol body is accepted rather than refused (verified live: a `{"v":3,…}` body to `/herd/v1/sync` returned HTTP **200**, not 422). Disclosed, not a silent pass. <!-- disclosure, not a marketing beat; keep even if S-13 is later reverted — then delete -->
- **Local data:** messages, channels and sync cursors live in `<HERMES_HOME>/plugin-data/herd/herd.db`. Herd reads nothing outside its own data folder except its settings in `config.yaml` and the linked task's title (next bullet). <!-- README:68 verbatim -->
- **Sharing a DM to a channel.** "Share to a channel" on a DM asks this gateway to create a named channel and copy that DM's messages into it. It is a copy: the DM and its history are never modified or deleted. The copies are written to Herd's own SQLite file and reach your teammate's gateway through the same `POST <url>/herd/v1/sync` request already disclosed above, as part of the normal sync payload (Herd sync protocol v2 — copied rows now carry the source DM's id so both gateways converge on the same rows). No new endpoint, no new outbound host, no new credential, no shell command. <!-- README verbatim (canonical, CA-5). S-13 #37; authored by Smith, signed off by Sentry Q-7. Ships because S-13 is merged; the demo beat stays staged. -->
- **Agent status:** an agent may set one short phrase (herd_set_status, e.g. "writing the code") that the pane shows beside its work. It lives in the gateway process's memory only — never written to herd.db, never sent to your teammate's gateway — and it disappears after five minutes or when the gateway restarts. <!-- README verbatim (canonical, CA-5). S-15 #41 merged; 4th tool, local-only, no new transport. -->
- **Telemetry:** none.

### Screenshots
<!-- Attach: (1) the peer-add command in the terminal, (2) both desktop apps
     showing the shared channel, (3) cross-machine task handoff. Same shots as
     the demo video session on Nov 8. -->

### Validation (run by me at the pin `cd6d46c`, Nov 7)
```
$ git rev-parse HEAD
cd6d46cc5f324ade11a814fa50889ce33324c607
$ hermes plugins validate . --install-deps
✓ config schema — shape valid          ✓ declared tools — matches registrations
✓ requires_env — all entries UPPER_SNAKE ✓ declared hooks — matches registrations
✓ oauth — not declared                 ✓ declared middleware — matches registrations
✓ loadable — entry: __init__.py, desktop/plugin.js
✓ python dependencies — none declared  ✓ built-in tool collisions — no collisions
✓ capability probe — register() ran in isolation
✓ security scan — safe                 ✓ no core override — no runtime rebinds of Hermes core
✓ desktop surface — stays inside the plugin SDK surface
Validation passed.

$ python3 scripts/qa/catalog_audit.py <herd-tree> --entry herd.yaml
catalog_audit: 0 FAIL, 0 WARN  (tools registered: ['herd_list_channels','herd_post','herd_read_channel','herd_set_status'])
```
Re-run both at the **exact** SHA being pinned, immediately before opening (and before every bump). <!-- screenshots go in the PR body even though the entry omits the fields -->

### Checklist (tick only when true at the pinned commit)
- [ ] One file added: `plugin-catalog/herd.yaml`
- [ ] Full 40-char SHA pin (freeze commit, not placeholder)
- [x] `version` quoted
- [x] Rule 13 disclosures in description AND mirrored in README <!-- README verified Nov 5: disclosures section incl. @mention-wake/inject_message line -->
- [x] `capabilities` match plugin.yaml at pin <!-- verified Nov 7 vs origin/main: 4 tools incl. herd_set_status -->
- [x] Screenshots/media — **entry ships WITHOUT `image`/`screenshots`** (no files at the pin); stills go in the PR body only (see §0)
- [ ] `hermes plugins validate --install-deps` green locally
- [ ] CI green
- [ ] Tyler approves **opening** the PR (F-3 REVISED: no freeze; one-screen go when pin-ready)

## Open questions (need Smith / Northstar)
- **Q1 — peer auth vs rule 11: RESOLVED.** Herd declares its own
  `config_schema` (peer_name, peer_url, peer_key secret → `HERD_PEER_KEY`),
  read only via `get_secret`. Sentry's Q-3 ruling (PR #8): **strip**
  `use_hermes_peers` from the catalog build, since reviewers read the code at
  the pin whatever the default, and undeclared dynamic secret names fail
  rules 6 and 11.
- ~~**Q2 — what Herd adds over core**~~ resolved: Northstar N-3 line, now in "What it does" above.
- ~~**Q3 — plugin.yaml missing requires_hermes**~~ resolved: plugin.yaml on main
  now carries `requires_hermes: ">=0.22.0"` (PRs #10/#11) and the three tools.
  Verified Nov 5 against `main` @ 8281abb.

## 3. Pre-open verification list (before opening, and before every bump)
1. `git -C /path/to/herd rev-parse HEAD` → swap into `sha:`
2. Confirm `version` in plugin.yaml matches the yaml above
3. `hermes plugins validate /path/to/herd --install-deps` — zero errors; read warnings
4. Grep the tree for rule 8/9 red flags (prototype patching, `eval`, core module
   overrides, `os.environ` secret reads) — should be clean
5. Confirm README carries the same rule-13 disclosures
5b. `python scripts/qa/catalog_audit.py . --entry herd.yaml` (Sentry, PR #8) is clean
5c. No `use_hermes_peers` / `HERMES_PEER_` references anywhere in the pinned tree
6. Swap `<sha>` in `image:` / `screenshots:` URLs for the pinned sha, and confirm
   those files exist at that commit (`docs/media/…`)
7. Confirm `requires_hermes` is identical in plugin.yaml and herd.yaml (rule 14)
8. No `.pyc`, binaries or opaque archives in the tree (rule 17); no self-updater (rule 3)

_Sources checked Nov 5: `plugin-catalog/README.md` (entry schema + rules 1–18) and
`website/docs/developer-guide/plugins/catalog-submission.md` in NousResearch/hermes-agent;
`hermes peer` section of `website/docs/reference/cli-commands.md`._
