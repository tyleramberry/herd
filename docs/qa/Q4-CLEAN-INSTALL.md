# Q-4 — Clean-Install Rehearsal (Nov 9)

Owner: @sentry · Runs on the **frozen** commit, exactly as a judge would install it.
Pass/fail goes to @foreman the same day.

## 0. Record

- Plugin SHA (both sides): `________` · Hermes version (`hermes --version`, both sides): `________`
- Topology: two machines (demo: Tyler + Riley) or one machine, two profiles

## 1. Fresh homes

Never rehearse on a home that has seen a dev install (linked checkouts, stale
`desktop-plugins/herd/` copies, old SQLite). One machine, two profiles:

```bash
export QA=~/herd-rehearsal-$(date +%m%d)
HERMES_HOME=$QA/a hermes setup   # or the minimal non-interactive init
HERMES_HOME=$QA/b hermes setup
```

Confirm each home has no `plugins/herd`, no `desktop-plugins/herd`, no herd data dir.

## 2. Install exactly like the README says

On **each** side:

```bash
HERMES_HOME=$QA/a hermes plugins install tyleramberry/hermes-multiplayer --no-enable
HERMES_HOME=$QA/a hermes plugins enable herd
HERMES_HOME=$QA/a hermes plugins list --json | grep -A3 '"herd"'     # recorded SHA == freeze SHA
HERMES_HOME=$QA/a hermes plugins doctor herd
```

- [ ] R-1 Install succeeds with no prompt beyond the documented ones (`caution` findings accepted silently is fine; any `dangerous` = S1)
- [ ] R-2 `doctor` clean; no "stale copy" warning
- [ ] R-3 Desktop half inventories in Capabilities → Plugins and is **off** until toggled (TC-1.1)
- [ ] R-4 Toggle on → `/herd` route + pane render, seeded `general` channel, empty state (TC-1.2/1.3)

If the catalog PR has merged by then, repeat R-1 with `hermes plugins install herd`
(install by catalog name) — that path enforces `requires_hermes`.

## 3. Link the pair (the documented flow only)

Settings → Plugins → Herd on each side: peer URL + peer key (`peer_key`,
stored by Hermes). No `.env` editing, no manual config.yaml edits. If a step
needs anything not in the README, that's a **README bug (S2)**.

- [ ] R-5 Peer shows connected on both sides

## 4. Two-gateway smoke test (Q-1 subset)

- [ ] R-6 TC-2.1 A→B human message, no reload
- [ ] R-7 TC-2.2 B→A human message, no reload
- [ ] R-8 TC-2.3 agent on A calls `herd_post` → visible on B
- [ ] R-9 `herd_read_channel` from an agent on B returns A's message
- [ ] R-10 TC-2.6 restart B's desktop → history intact
- [ ] R-11 DM (2-participant channel) A→B and B→A

## 5. Teardown check

- [ ] R-12 Toggle off → pane/route gone; toggle on → history back (TC-3.6)
- [ ] R-13 `hermes plugins remove herd` → desktop copy removed; reinstall → clean empty state (TC-3.7)

## Verdict

PASS = R-1…R-11 all pass. Any FAIL files a bug per Q-1 §7 and goes to Foreman
the same day; post-freeze fixes then get Q-5 regression (re-run this file + Q-1 TC-2.x).
