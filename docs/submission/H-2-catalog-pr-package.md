# H-2 — Catalog PR Package: Herd (DRAFT v1, Nov 5)

> **Status: PREPARED ONLY.** PR opens after Foreman review + Tyler sign-off on Nov 8.
> Target: add ONE file `plugin-catalog/herd.yaml` to `NousResearch/hermes-agent`.

## 1. herd.yaml

```yaml
name: herd
title: Herd
description: >-
  Multiplayer Hermes — channels and DMs where humans and their agents work
  together across machines, inside the Hermes desktop app.
repo: https://github.com/tyleramberry/herd
sha: 543c1fe2e672862a548d72d5b3fa5ebbd4b1fa44  # PLACEHOLDER — must be the Nov 8 freeze commit (full 40-hex, verify with `git rev-parse HEAD` at pin time)
tier: community
category: platform
maintainer: tyleramberry
version: "0.1.0"  # QUOTED per schema; must match plugin.yaml at pinned commit — verify at freeze
requires_hermes: ">=0.19"  # TODO: set to actual floor once plugin.yaml exists; must match plugin.yaml (rule 14)
# platforms: omit unless plugin is macOS-only
# subdir: omit (plugin at repo root)
capabilities:
  # TODO: must match what the plugin actually registers at the pinned commit (rule 6).
  # Pull the exact tools/hooks/middleware/requires_env list from plugin.yaml at freeze.
  tools: []       # FILL FROM plugin.yaml
  hooks: []       # FILL FROM plugin.yaml
  middleware: []  # FILL FROM plugin.yaml
  requires_env: []  # e.g. API_SERVER_KEY — confirm whether env or config_schema secret (rule 11)
# image / screenshots: pin to the entry's commit (raw.githubusercontent.com/tyleramberry/herd/<sha>/...)
#   — add after the Nov 8 recording session; screenshots also satisfy the PR-description requirement
docs_url: https://github.com/tyleramberry/herd#readme
```

## 2. PR description (draft)

### What it does
Herd is multiplayer Hermes: channels and direct messages inside the Hermes
desktop app where humans and their Hermes agents collaborate across machines.
One command joins a peer:

```
hermes peer add <name> --url <their-gateway-url> --key <API_SERVER_KEY>
```

After joining, agents on both machines can exchange messages and hand work to
each other; both humans see the same thread. Built for the Nous Research
Hermes Agent Plugin Hackathon (Nov 2026).

### Hermes surfaces used
<!-- FILL AT FREEZE — enumerate exactly what the pinned tree registers, e.g.: -->
- Tools: `hermes peer add`, … (exact tool names from plugin.yaml)
- Hooks/middleware: TBD
- Desktop plugin surface (desktop/plugin.js) via the plugin SDK only

### Rule 13 disclosures
<!-- Keep only lines that are true at the pinned commit; delete the rest. -->
- **Network calls:** Herd runs its own gateway/relay server and communicates
  peer-to-peer over the network to the gateways you configure (`--url`). No
  third-party services. <!-- VERIFY: does anything else phone home? -->
- **Long-running background processes:** the gateway/API server runs for the
  lifetime of the Hermes session to receive peer connections. <!-- VERIFY -->
- **Stored credentials:** peer API keys (`API_SERVER_KEY`) are stored by
  Hermes's secret route (`agent.secret_scope.get_secret`) — not read from
  .env or any other credential store. <!-- VERIFY implementation (rule 11) -->
- **Reads outside plugin data:** none. <!-- VERIFY -->
- **Shell commands:** `hermes peer add` is a Hermes CLI command, not a plugin
  shell-out. <!-- VERIFY no subprocess usage -->
- **Telemetry:** none. Opt-in telemetry: n/a.

### Screenshots
<!-- Attach: (1) the peer-add command in the terminal, (2) both desktop apps
     showing the shared channel, (3) cross-machine task handoff. Same shots as
     the demo video session on Nov 8. -->

### Validation
- `hermes plugins validate /path/to/herd --install-deps` run at the pinned commit — green.
  <!-- PASTE ACTUAL OUTPUT AT FREEZE -->

### Checklist
- [x] One file added: `plugin-catalog/herd.yaml`
- [x] Full 40-char SHA pin (placeholder above — swap for freeze commit)
- [x] `version` quoted
- [x] Rule 13 disclosures in description (and mirrored in README)
- [x] Capabilities match plugin.yaml at pin
- [x] Screenshots attached
- [ ] CI green
- [ ] Foreman review + Tyler sign-off (Nov 8) — **gate before opening PR**

## 3. Pre-open verification list (at freeze, Nov 8)
1. `git -C /path/to/herd rev-parse HEAD` → swap into `sha:`
2. Confirm `version` in plugin.yaml matches the yaml above
3. `hermes plugins validate /path/to/herd --install-deps` — zero errors; read warnings
4. Grep the tree for rule 8/9 red flags (prototype patching, `eval`, core module
   overrides, `os.environ` secret reads) — should be clean
5. Confirm README carries the same rule-13 disclosures
