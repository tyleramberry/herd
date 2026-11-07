# H-2 — Catalog PR Package: Herd (DRAFT v4, Nov 7 — pre-flight audit folded in)

> **Status: PREPARED ONLY — NOT PIN-READY.** PR opens after Foreman review + Tyler sign-off on Nov 8.
> **Pin blocked on B1** (QA pre-flight audit, `docs/qa/catalog-preflight-audit-nov7.md`): the pin must be a
> commit that *contains the B1 fix*, never the current HEAD. See §0 Pin-readiness block.
> Target: add ONE file `plugin-catalog/herd.yaml` to `NousResearch/hermes-agent`.

## 0. Pin-readiness block (added Nov 7 from QA's pre-flight audit)

**H-2 is NOT pin-ready.** Three gates, in this order:

| # | Gate | State | Owner |
|---|---|---|---|
| 1 | **B1 fix merged** (`herd_store.py:922-927` — plain-`urllib` fallback forwards the peer key across a cross-host redirect; rule 11 + rule 13 accuracy) | **NOT FIXED** on `origin/main` @ `61c9068` (verified Nov 7). No B1 PR is open. | Smith |
| 2 | **Real 40-char SHA** — `git rev-parse HEAD` on the B1-fixed commit, validate at that commit | blocked by 1 | Herald |
| 3 | **Media** — `docs/media/*` referenced but **empty** (`git ls-files docs/media` → nothing) | open — see decision below | Herald |

**Decision on media (rule-safe default):** the catalog treats `image`/`screenshots` as *cosmetic*, and a
link to a file that does not exist at the pinned SHA renders a broken gallery. So: **ship the entry
WITHOUT `image:` and `screenshots:` unless real files are committed to the pin.** If the Nov 8 recording
session yields usable captures, commit them to `docs/media/` **before** the freeze commit and pin those
URLs to the same SHA. Never reference a file that is not in the pinned tree.

**Disclosure corrections this PR carries** (rule 13 accuracy — both found by the audit):
- `README.md:15` lists **reactions** under "What it doesn't do (yet)". Reactions ship (README:57,
  `plugin_api.py:95-97` `toggle_reaction`). The word "reactions" **must be deleted from that line**.
- `README.md:63` claims the peer key "drops the key if your teammate's gateway redirects to a different
  host". That is **only true on the Hermes-helper path**; the plain-`urllib` fallback forwards it. The
  sentence must match the shipped behaviour once B1 lands. **Two candidate wordings, pick by the fix
  Smith actually ships:**
  - *(refuse-redirects fix — audit's recommended one)*: "Outbound sync sets the bearer header only for
    the teammate gateway URL you configured; a redirect from that URL is **refused, never followed**, so
    the key is never re-sent to another host (a redirecting peer shows an HTTP 30x error)."
  - *(helper-only path)*: "Outbound sync drops the credential if your teammate's gateway redirects to a
    different host (via `hermes_cli.urllib_security.open_credentialed_url`)."
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
sha: 0000000000000000000000000000000000000000  # PLACEHOLDER — NOT A VALID PIN. Fill with `git rev-parse HEAD` of the B1-FIXED freeze commit (audit B2: the current HEAD contains B1 and is not pin-valid)
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
- Promote a DM to a channel — a desktop action (local route `POST /api/plugins/herd/channels/{id}/promote`); the copy reaches the teammate over the existing `POST /herd/v1/sync` write path with a channel-create + message-replay payload (`PROTOCOL_VERSION` 1 → 2; copied rows carry `origin_channel_id`). **(S-13 #37 is merged at this tree — the disclosure line above carries the v2 fact; the *proof beat* for it stays staged in H-6 until QA is green.)**
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
- **Reads outside plugin data:** none. <!-- at freeze: if S-16 ships, this line is REPLACED by the read-only kanban.db read line (Q-8) — never keep both -->
- **Shell commands:** none **in the runtime files** (`tools.py`, `__init__.py`, `schemas.py`, `dashboard/`). <!-- audit WARN 3: scripts/qa/catalog_audit.py:176 shells out to `git` via subprocess; disclose it as a dev-only script or leave scripts/qa/ out of the pin -->
- **Peer key on redirect (B1):** outbound sync must never re-send the teammate key to another host. **Wording follows Smith's landed fix** — see §0; the current README:63 sentence is FALSE on the plain-`urllib` fallback and cannot ship as-is.
- **Sync protocol version:** `PROTOCOL_VERSION` is **2** at this tree (S-13 promote, #37): a promoted DM is copied to a new channel and delivered over the existing `POST <url>/herd/v1/sync` write path; copied rows carry `origin_channel_id`/`promoted_from`, and a version **1** peer simply ignores the extra field (no 500, no corruption). Readable from `/herd/v1/ping` + `/status`. <!-- disclosure, not a marketing beat; keep even if S-13 is later reverted — then delete -->
- **Local data:** channel history in a SQLite file under the plugin's data dir.
- **Agent status (S-15 #41):** the status phrase is **local-gateway-agents only** — it lives in the gateway process's memory, is never written to `herd.db`, is **never sent to the teammate's gateway**, and clears after five minutes or on gateway restart.
- **Telemetry:** none.

### Screenshots
<!-- Attach: (1) the peer-add command in the terminal, (2) both desktop apps
     showing the shared channel, (3) cross-machine task handoff. Same shots as
     the demo video session on Nov 8. -->

### Validation
- `hermes plugins validate /path/to/herd --install-deps` run at the pinned commit — green.
  <!-- PASTE ACTUAL OUTPUT AT FREEZE -->

### Checklist (tick only when true at the pinned commit)
- [ ] One file added: `plugin-catalog/herd.yaml`
- [ ] Full 40-char SHA pin (freeze commit, not placeholder)
- [x] `version` quoted
- [x] Rule 13 disclosures in description AND mirrored in README <!-- README verified Nov 5: disclosures section incl. @mention-wake/inject_message line -->
- [x] `capabilities` match plugin.yaml at pin <!-- verified Nov 7 vs origin/main: 4 tools incl. herd_set_status -->
- [ ] Screenshots attached (PR body) and listed in `screenshots:` — **or `image`/`screenshots` intentionally omitted because no files exist at the pin (see §0)**
- [ ] `hermes plugins validate --install-deps` green locally
- [ ] CI green
- [ ] Foreman review + Tyler sign-off (Nov 8) — **gate before opening PR**

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

## 3. Pre-open verification list (at freeze, Nov 8)
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
