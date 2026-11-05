# Herd — Task Board

Project: multiplayer Hermes desktop plugin · Deadline: **Nov 11, 2026 5:00 PM EST** · Code freeze: **Nov 8**
Board owner: Foreman (PM). Update your own rows by editing this file in your PR. Mark 🔵 In progress / ✅ Done / ⛔ Blocked (state why).

---

## Milestones

| Date | Milestone |
|---|---|
| Thu Nov 5 | **SPINE:** two gateways exchange one real message through the plugin |
| Sat Nov 7 | Validate + doctor clean; demo script final; polish pass done |
| Sun Nov 8 | **CODE FREEZE** · catalog PR opened · demo video recorded |
| Mon Nov 9 | Clean-install rehearsal (fresh HERMES_HOME, 2-gateway smoke test) |
| Tue Nov 10 | Video posted to X (@NousResearch) · entry form submitted |
| Wed Nov 11 | All three gates verified before noon EST |

---

## @smith — Engineering

- [ ] 🔵 **S-1 (due Nov 4 EOD): Scaffold unified package** — **Status (Nov 5): built in the fan-out PR.** plugin.yaml (3 tools, config_schema join form, requires_hermes ">=0.22.0"), `dashboard/herd_store.py` (SQLite: channels, messages, participants, peer_state), `dashboard/plugin_api.py`, `desktop/plugin.js` (route `/herd`, sidebar nav, right pane, empty states). Supersedes PR #4. Awaiting Sentry TC-0 + live `hermes plugins validate`/`doctor`.
- [ ] 🔵 **S-2 (due Nov 5): Two-gateway fan-out** — **Status: implemented, needs live 2-gateway run.** Linked side runs one `POST <peer>/herd/v1/sync` every 3 s (push its new messages, pull the peer's) on the peer's api_server, auth = peer's API_SERVER_KEY. One-sided link carries both directions. Simulated 2-gateway + real-HTTP tests green (ordering, dup convergence, offline catch-up, DMs). THE milestone: Sentry TC-2.1/2.2 on two real gateways is the gate.
- [ ] 🔵 **S-3 (due Nov 5): Agent-side tools** — **Status: done pending QA.** `herd_list_channels`, `herd_post`, `herd_read_channel` (N-1/N-3 copy), registered in plugin.yaml `provides_tools`; agent posts carry `author_type=agent`.
- [ ] 🔵 **S-4 (due Nov 6): Join/onboarding flow** — **Status: done pending QA.** Join = Settings → Plugins → Herd form (peer name, URL, masked key via config_schema secret; Sentry CA-4 / rule 11), "Connect a teammate" button in the pane, New channel, New message (DM = dm-flagged 2-member channel).
- [ ] ⬜ **S-5 (due Nov 7): Fix Sentry's QA round-1 bugs**; `hermes plugins validate` + `doctor` clean; screenshots for catalog PR.
- [ ] ⬜ **S-6 (Nov 8): Freeze** — bug fixes only.
- [ ] 🔵 **S-7 (stretch, gated): @mention wake** — **Tyler approved the build (Nov 5): "Yes, build it."** Smith is starting. Gate stands: **Foreman go/no-go Fri Nov 6 noon** (board previously said "Fri Nov 7"; Nov 7 is Saturday). Go only if TC-2 (two real gateways) has passed on real hardware; otherwise cut it, no freeze slip. Default off (ctx.inject_message + allow_gateway_injection). Rule-13 disclosure and H-2 capabilities must be updated if it ships.

## @sentry — QA

- [x] ✅ **Q-1 (due Nov 4 EOD): QA checklist for Thursday milestone** — DONE: `docs/qa/Q1-SPINE-CHECKLIST.md` (SPINE gate = TC-2.1/2.2, static pre-flight, local round-trip, fan-out incl. polling-fallback + convergence, edge cases, bug template, sign-off rules).
- [ ] 🔵 **Q-2 (Nov 6–7): QA round 1** — test Smith's PRs against checklist; bugs back to Smith with repro steps; loop until clean, then route to Foreman. **Nov 5: #9 static pass (TC-0.3–0.9) green, 49 tests. Live TC-0.1/0.2 (validate/doctor) and TC-2 need Tyler's two Macs.**
- [ ] 🔵 **Q-3 (due Nov 7): Catalog-rules audit** — security scan findings, capability declarations match reality, no core-UI touching, secrets policy. **Round 1 done Nov 5: `docs/qa/Q3-CATALOG-AUDIT.md` + `scripts/qa/catalog_audit.py`. All 3 S1s fixed in #9 (merged); audit on main = 0 FAIL. Re-run at freeze.**
- [ ] ⬜ **Q-4 (due Nov 9): Clean-install rehearsal** — fresh HERMES_HOME, install by repo, enable, two-gateway smoke test, report pass/fail to Foreman. Script ready: `docs/qa/Q4-CLEAN-INSTALL.md`.
- [ ] ⬜ **Q-5 (Nov 10): Regression pass on any post-freeze fixes.**

## @northstar — Product

- [x] ✅ **N-1 (due Nov 4 EOD): Locked cut-list written down** — DONE Nov 5: `docs/product/N-1-CUT-LIST.md`. IN = channels, 2-gateway fan-out, peer join, agents post **and read** (`herd_list_channels`, `herd_post`, `herd_read_channel`), DMs (= 2-person channel). OUT incl. auto-wake/@mention triggers. Join = Herd's own Add-teammate form (core peer registry off-limits per Q-3 CA-4). Positioning vs. core Group Chat added (CA-8): Herd connects people, not just bots.
- [x] ✅ **N-2 (due Nov 6): Demo narrative** — DONE Nov 5: `docs/product/N-2-DEMO-NARRATIVE.md`. 6 beats for Herald; adds a 5s human-to-human beat before the jaw-drop; shot 4 = Riley *hands* the task to her agent (no auto-wake in v1).
- [x] ✅ **N-3 (due Nov 7): Naming/copy pass** — DONE v1 Nov 5: `docs/product/N-3-NAMING-COPY.md` (catalog title/description for H-2, tool descriptions + UI strings + README suggestions for Smith). Will re-check against real UI Nov 7.

## @herald — Submission

- [ ] 🔵 **H-1 (due Nov 7): Demo script draft** — <90s, hook = join flow, demo = Tyler + wife's two instances. Nov 8 recording date is real. **Status: draft v6 (docs/submission/H-1-demo-script.md) — ~80s. People-first hook ("Hermes is single-player. We made it multiplayer."), shot 2 = Add-teammate form, Brooklyn approves her agent on camera. Shot 5 recorded both ways (5A baseline, 5B @mention); Foreman go/no-go Fri noon. Final pass Nov 7.**
- [ ] ⬜ **H-2 (due Nov 7): Catalog PR package ready** — plugin-catalog/herd.yaml draft (entry schema, 40-char SHA, quoted version), PR description w/ surfaces + rule-13 disclosures. **Opens only after Foreman review + Tyler sign-off Nov 8.** **Status: draft v2 (docs/submission/H-2-catalog-pr-package.md) — checked against live catalog README: fixed capability keys (`provides_*`), category → desktop, added image/screenshots. Capabilities from Smith; requires_hermes ">=0.22.0" per Sentry (oldest verified, Tyler's Mac); rule-11 Q1 resolved (strip use_hermes_peers).**
- [ ] ⬜ **H-3 (due Nov 8): Catalog PR opened** (post-approval) · demo video recorded.
- [ ] ⬜ **H-4 (due Nov 10): Video posted to X tagged @NousResearch · entry form submitted with both links** · report form confirmation to Foreman.

## @foreman — Project management

- [x] ✅ **F-1: Repo created** — github.com/tyleramberry/herd (public, verified).
- [ ] 🔵 **F-2 (daily): Verify each deliverable artifact personally** before marking Done; daily risk report. Reports in `docs/pm/` (latest: `docs/pm/2026-11-05-status.md`).
- [ ] 🔵 **F-3 (due Nov 8): Review catalog PR against judging criteria → Tyler approval gate.** Gate checklist drafted: `docs/pm/F-3-freeze-gate.md`.

---

## Post-hackathon backlog (do NOT build before Nov 11)

Threads · reactions · file sharing · presence indicators · voice · channel permissions · message search · Herd for >2 gateways · MySI plugin.
