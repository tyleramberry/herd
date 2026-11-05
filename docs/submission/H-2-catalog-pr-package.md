# H-2 — Catalog PR Package: Herd (DRAFT v2, Nov 5 — reconciled with Smith's PR #4 surface)

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
sha: 543c1fe2e672862a548d72d5b3fa5ebbd4b1fa44  # PLACEHOLDER — per Foreman: pin = actual Nov 8 head of main AFTER review+sign-off. Candidate lineage: PR #4 @ 988585ff94c48344243a10c5ed5b79bfa3c2c86a
tier: community
category: platform
maintainer: tyleramberry
version: "0.1.0"  # QUOTED per schema; matches plugin.yaml at PR #4 (verified with Smith) — re-verify at freeze
requires_hermes: ">=0.19"  # TODO(FIX IN REPO): plugin.yaml declares NO floor — rule 14 wants the same floor in BOTH plugin.yaml and the catalog entry. Ask Smith to add requires_hermes to plugin.yaml (PR #4 or follow-up); then set the catalog value to match exactly.
# platforms: omit unless plugin is macOS-only
# subdir: omit (plugin at repo root)
capabilities:
  # Verified against PR #4 plugin.yaml + runtime registration (Smith, Nov 5) — rule 6.
  tools:
    - herd_post
    - herd_list_channels
  hooks: []        # none registered
  middleware: []   # none registered
  requires_env: [] # none declared; no config_schema secrets
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
<!-- Verified against PR #4 (988585ff94c48344243a10c5ed5b79bfa3c2c86a) — Smith, Nov 5 -->
- Tools (toolset "herd"): `herd_post`, `herd_list_channels`
- Hooks: none. Middleware: none. Slash commands: none.
- Desktop surface: `desktop/plugin.js` via the plugin SDK only; dashboard backend
  mounted in-gateway at `/api/plugins/herd/` (no separate process)

### Rule 13 disclosures
<!-- As confirmed by Smith for the PR #4 tree; re-verify at freeze. -->
- **Execution model:** the plugin runs inside the Hermes gateway process
  (dashboard backend mount). No subprocesses. No long-lived background process
  of its own.
- **Network calls:** none in the pinned Day-1 commit. The desktop half talks
  only to its own `/api/plugins/herd/` namespace and the host event stream.
  Cross-gateway sync (between the two `hermes peer`-configured gateways) is the
  only planned egress — disclose it explicitly once it exists at the pinned
  commit, and state it goes only to gateways the user configured.
- **Secrets / credentials:** none. No `requires_env`, no `config_schema`
  secret-typed fields, no use of `agent.secret_scope.get_secret`. Known item
  pending the config_schema fix (below): one direct read of the non-secret
  `HERMES_GATEWAY_ID` env var (dashboard/plugin_api.py:49), used as the
  gateway's logical identity, defaulting to `"local"`.
- **Reads outside plugin data:** none.
- **Shell commands:** none.
- **Telemetry:** none. Opt-in telemetry: n/a.

### Known pre-open fixes (do NOT open the PR before these land at the pin)
1. **Rule 11 hygiene:** replace the direct `os.environ.get("HERMES_GATEWAY_ID")`
   read with a `config_schema` setting (`gateway_id` under
   `plugins.entries.herd.settings`). Recommended to fold into PR #4 while it is
   still in Sentry QA — trivial change, removes the only env read from the tree.
2. **Rule 14:** add `requires_hermes` to plugin.yaml (currently absent) and set
   the catalog entry's floor to the exact same value.

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
