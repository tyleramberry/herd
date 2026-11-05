# Q-3 — Catalog-Rules Audit

Owner: @sentry · Round 1: Nov 5, 2026 · Re-run at freeze (Nov 8) on the pinned commit.

Source of truth: the 18 admission rules in
[`plugin-catalog/README.md`](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/README.md)
(read at hermes-agent `bd312c9`, Nov 5), plus the Desktop Plugin SDK and plugin
developer guide. Current Hermes release at audit time: **v0.22.7**.

## How to run

```bash
python scripts/qa/catalog_audit.py .                         # plugin tree
python scripts/qa/catalog_audit.py . --entry herd.yaml       # + cross-check the catalog entry
python -m pytest tests/qa -q                                  # audit self-tests
```

The script checks statically what it can (rules 2, 6, 7-partial, 8, 9, 10, 11,
13-partial, 14, 17 and Q-1 TC-0.4–0.9). It is a pre-flight, not a substitute:
`hermes plugins validate . --install-deps` (what catalog CI runs) is still the
gate, and rule 8 prototype patching and rule 12/13 behaviour need a human read.
Exit 1 on any FAIL; every WARN gets read before sign-off.

## Ruling: `use_hermes_peers` (Herald's H-2 Q1)

**Strip it from the catalog build.** Not default-off: strip.

- Rule 11 blesses `get_secret` only for a plugin's *declared* `requires_env` /
  `config_schema` secrets. `HERMES_PEER_<NAME>_KEY` is core's credential with a
  dynamic name that cannot be declared, so a reviewer reads it as Herd reaching
  into another component's credentials.
- Rule 6 then bites too: the entry's `requires_env` cannot match what the code
  reads.
- Default-off does not help. Reviewers read the code at the pinned SHA, not the
  default setting, and a request-for-changes costs us the review window.
- Reading `bot_peers` out of core config is also a "read outside the plugin's
  own data" that rule 13 would make us disclose.

Keep the clean path only: Herd's own `config_schema` secret `peer_key`
(`HERD_PEER_KEY`) read via `agent.secret_scope.get_secret`. If we want the
peer-registry reuse later, ask Hermes for a seam (rule 9 "asking for a hook").

Demo consequence (for Herald/Northstar): shot 2 shows **Settings → Plugins →
Herd** (peer URL + key), not `hermes peer add`. That is better for judging
anyway, because `hermes peer add` is a core Hermes command
(`hermes_cli/subcommands/peer.py`), so showing it as the hook demos core, not Herd.

## Findings, round 1 (Nov 5)

Severity per Q-1 §7. Each row stays open until re-verified on the fix.

| ID | Sev | Rule | Where | Finding | Owner |
|---|---|---|---|---|---|
| CA-1 | S1 | 14 | `plugin.yaml` (PR #4) | `requires_hermes` missing. Must be a SemVer floor, in **both** plugin.yaml and herd.yaml, identical. | Smith |
| CA-2 | S2 | 14 | H-2 v2 `requires_hermes: ">=0.19.0"` | Floor must be truthful. It's justified as "current release", but current is **0.22.7**. We use `plugin_events.broadcast_plugin_event`, `plugin_storage`, `config_schema` secrets and the unified desktop half; unless someone actually runs on 0.19, set **`">=0.22.7"`** (the version we test on). | Smith + Herald |
| CA-3 | S1 | 6 / TC-0.8 | `plugin.yaml` + `tools.py` (PR #4) | Registers 2 tools (`herd_post`, `herd_list_channels`); locked scope (N-1, PR #5) is 3: add `herd_read_channel`, and declare it in `provides_tools`. | Smith |
| CA-4 | S1 | 11 / 6 | `use_hermes_peers` design | See ruling above: strip from catalog build. | Smith |
| CA-5 | S2 | 13 | `README.md` (PR #4) | No disclosure section. Needs the same rule-13 lines as the PR description: network calls (peer gateways only), stored credential (`peer_key` via Hermes), any poll/sync loop + interval, local SQLite. | Smith / Herald copy |
| CA-6 | S3 | 11 | `dashboard/plugin_api.py:49` | Reads `os.environ["HERMES_GATEWAY_ID"]`. Not a secret, so not a rule-11 violation, but `os.environ` ignores the active profile under multiplexing; prefer a plugin config value or `get_secret`-style profile-aware read. | Smith |
| CA-7 | S2 | 13 | H-2 v2 | "Reads outside plugin data: none beyond Hermes's own peer registry". Once CA-4 is stripped, that becomes plain **none**; update. | Herald |
| CA-8 | info | product | — | Hermes core already ships **cross-machine Group Chat rooms** (`website/docs/user-guide/bot-mode.md`: "Rooms can span machines", gateway-owned rooms, `on_room_member_activity` hook) and `hermes peer dm`. H-2 Q2 only names `peer dm`. Reviewers/judges will compare Herd to Group Chat; the "what Herd adds" line has to answer that (humans on both machines in one shared channel + agent tools), not just peer DMs. Rule 15 (no skins of bundled plugins) does not apply since Group Chat is core, not a plugin, but the overlap is the obvious review question. | Northstar |
| CA-9 | info | 12 | design | If a post on gateway A makes an agent on gateway B take a turn, B's agent runs under B's approval settings; Herd must not auto-approve or spawn non-interactive children (rule 12). Will verify in Q-2 TC-2.3. | Sentry |

### What passed on PR #4 (`988585f`)

- `node --check desktop/plugin.js` OK; imports only allowed specifiers; no eval,
  no markup selectors, no bare timers, no hex colors (rule 8, TC-0.4–0.7).
- No binaries / `.pyc` (rule 17); no secret literals; no core overrides (rule 9).
- Core imports are documented ones: `hermes_cli.plugin_events`, `plugins.plugin_storage`.
- Tool handlers accept `**kwargs` and return JSON strings (TC-0.9).
- Backend tests: 15/15 green (`python -m pytest tests -q`).
- Backend lives in `dashboard/manifest.json` + `dashboard/plugin_api.py` (correct
  per the "One package, both SDKs" layout).
- H-2 v2 already fixed the v1 capability keys (`provides_*`), quoted `version`
  and moved category to `desktop`.

## Freeze-day checklist (Nov 8, on the pinned SHA)

- [ ] `python scripts/qa/catalog_audit.py . --entry herd.yaml` → 0 FAIL, every WARN explained
- [ ] `hermes plugins validate . --install-deps` → green; paste output into H-2
- [ ] `hermes plugins doctor . --ci` → clean
- [ ] Hand-read `desktop/plugin.js` for prototype patching (lint does not catch it)
- [ ] Hand-read for self-update paths (rule 3): no code fetches/replaces plugin files
- [ ] `grep -rn "http" --include=*.py --include=*.js .` → only peer-gateway / `ctx.rest` paths (rule 13)
- [ ] README and PR description carry identical rule-13 lines
- [ ] `version` + `requires_hermes` identical in plugin.yaml and herd.yaml; image/screenshot URLs pinned to the same SHA
