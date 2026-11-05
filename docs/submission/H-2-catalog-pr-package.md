# H-2 — Catalog PR Package: Herd (DRAFT v2, Nov 5)

> **Status: PREPARED ONLY.** PR opens after Foreman review + Tyler sign-off on Nov 8.
> Target: add ONE file `plugin-catalog/herd.yaml` to `NousResearch/hermes-agent`.

## 1. herd.yaml

```yaml
name: herd
title: Herd
description: >-
  Multiplayer Hermes. Channels and DMs where you, a teammate, and both of
  your Hermes agents work together across two machines.  # N-3 copy
repo: https://github.com/tyleramberry/herd
sha: 0000000000000000000000000000000000000000  # PLACEHOLDER — the Nov 8 freeze commit, full 40-hex (`git rev-parse HEAD` at pin time)
tier: community
category: desktop  # shelf options: desktop|memory|platform|web|tools|voice|automation|models|general. Herd is a desktop pane, so "desktop" (was "platform", which is the messaging-platform shelf)
maintainer: tyleramberry
version: "0.1.0"  # QUOTED; must match plugin.yaml at the pinned commit
requires_hermes: ">=0.22.7"  # Sentry Q-3: the release we actually test on (0.19.0 unverified). Smith must set the same floor in plugin.yaml (rule 14)
docs_url: https://github.com/tyleramberry/herd#readme
# platforms: omit unless macOS-only
# subdir: omit (plugin at repo root)
image: https://raw.githubusercontent.com/tyleramberry/herd/<sha>/docs/media/banner.png  # 2:1, e.g. 1200x600; pin to the same sha
screenshots:  # up to 6, GitHub hosts only, pinned to the same sha
  - https://raw.githubusercontent.com/tyleramberry/herd/<sha>/docs/media/channel-two-machines.png
  - https://raw.githubusercontent.com/tyleramberry/herd/<sha>/docs/media/agent-posts-to-channel.png
capabilities:
  # Key names per the live entry schema: provides_tools / provides_hooks / provides_middleware / requires_env
  # (draft v1 used tools/hooks/middleware, which is wrong). Must match what the plugin registers at the pin (rule 6).
  provides_tools: [herd_list_channels, herd_post, herd_read_channel]  # confirmed by Smith Nov 5; re-check at freeze
  provides_hooks: []        # none (Smith)
  provides_middleware: []   # none (Smith)
  requires_env: []          # none: the peer key is a config_schema secret (HERD_PEER_KEY), not requires_env
```

## 2. PR description (draft)

### What it does
Herd is multiplayer Hermes: channels and direct messages inside the Hermes
desktop app where humans and their Hermes agents collaborate across machines.
You connect a teammate's Hermes under **Settings > Plugins > Herd** (their
gateway URL and API key). Herd then gives you shared channels in the desktop app: agents on both machines can exchange messages and hand work to
each other; both humans see the same thread. Built for the Nous Research
Hermes Agent Plugin Hackathon (Nov 2026).

### Hermes surfaces used
<!-- FILL AT FREEZE — enumerate exactly what the pinned tree registers, e.g.: -->
- Agent tools: `herd_post`, `herd_read_channel`, `herd_list_channels` (exact names from plugin.yaml)
- `config_schema` settings (peer_name, peer_url, peer_key secret), rendered by Desktop under Settings > Plugins > Herd
- No hooks, no middleware, no CLI commands
- Desktop plugin surface (desktop/plugin.js) via the plugin SDK only

### Rule 13 disclosures
<!-- Keep only lines that are true at the pinned commit; delete the rest. -->
- **Network calls:** only to the one peer gateway configured in Herd's
  settings. No third-party services. <!-- VERIFY at freeze: grep for any other outbound URL -->
- **Long-running background processes:** <!-- VERIFY: does Herd poll peers on a timer / run a sync loop? If yes, disclose interval. Core api_server is Hermes's, not Herd's. -->
- **Stored credentials:** one peer API key, declared as a `config_schema`
  secret (`peer_key`, env `HERD_PEER_KEY`) and stored by Hermes; Herd reads it
  only via `agent.secret_scope.get_secret`. Set under Settings > Plugins > Herd.
- **Reads outside plugin data:** none.
- **Shell commands:** none. <!-- VERIFY no subprocess usage; if Herd shells out to `hermes peer dm`, disclose it here -->
- **Local data:** channel history in a SQLite file under the plugin's data dir.
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
- [ ] Rule 13 disclosures in description AND mirrored in README
- [ ] `capabilities` match plugin.yaml at pin
- [ ] Screenshots attached (PR body) and listed in `screenshots:`
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
- **Q2 — what Herd adds over core (Northstar).** Core already does cross-machine
  bot DMs (`hermes peer dm`). Reviewers and judges will ask what's new: the
  answer must be the shared channel/DM UI and the agent tools, and the PR
  description should say so plainly.

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
