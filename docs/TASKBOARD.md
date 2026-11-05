# Herd — Task Board

Project: multiplayer Hermes desktop plugin · Deadline: **Nov 11, 2026 5:00 PM EST** · Code freeze: **Nov 8**
Board owner: Foreman (PM). Update your own rows by editing this file in your PR. Mark 🔵 In progress / ✅ Done / ⛔ Blocked (state why).

---

## Milestones

| Date | Milestone |
|---|---|
| Thu Nov 5 | **SPINE:** two gateways exchange one real message through the plugin |
| Fri Nov 7 | Validate + doctor clean; demo script final; polish pass done |
| Sun Nov 8 | **CODE FREEZE** · catalog PR opened · demo video recorded |
| Mon Nov 9 | Clean-install rehearsal (fresh HERMES_HOME, 2-gateway smoke test) |
| Tue Nov 10 | Video posted to X (@NousResearch) · entry form submitted |
| Wed Nov 11 | All three gates verified before noon EST |

---

## @smith — Engineering

- [ ] 🔵 **S-1 (due Nov 4 EOD): Scaffold unified package** — plugin.yaml, __init__.py, schemas.py, tools.py, plugin_api.py (SQLite: channels, messages, participants), desktop/plugin.js. Pane + route render live from backend, empty state visible. PR to main. **Status (Foreman, Nov 5): code exists in PR #4 (`feat/scaffold` @ 988585f), 15/15 tests pass, NOT merged. The two pre-open fixes reported "in flight" are not on the branch yet: `os.environ` read still at `dashboard/plugin_api.py:49`; no `requires_hermes` in plugin.yaml. Late: push fixes, merge.**
- [ ] ⬜ **S-2 (due Nov 5): Two-gateway fan-out** — message posted on gateway A appears in channel view on gateway B. THE milestone; escalate to Foreman same night if slipping. **⛔ AT RISK (Nov 5): design is written (README "Thursday fan-out design"; `INSERT OR IGNORE` + `gateway_id` schema ready), but no sync code exists. Blocked on S-1 merge.**
- [ ] 🔵 **S-3 (due Nov 5): Agent-side tools** — `herd_post`, `herd_list_channels` (shipped under these names in PR #4; board previously said herd_post_message) (agents post to channels from Bot Chats); register via plugin.yaml per catalog rules. **Status: in PR #4, unmerged.**
- [ ] ⬜ **S-4 (due Nov 6): Join/onboarding flow** — "hermes peer add" story in UI; channel-create + DM flows.
- [ ] ⬜ **S-5 (due Nov 7): Fix Sentry's QA round-1 bugs**; `hermes plugins validate` + `doctor` clean; screenshots for catalog PR.
- [ ] ⬜ **S-6 (Nov 8): Freeze** — bug fixes only.

## @sentry — QA

- [x] ✅ **Q-1 (due Nov 4 EOD): QA checklist for Thursday milestone** — DONE: `docs/qa/Q1-SPINE-CHECKLIST.md` (SPINE gate = TC-2.1/2.2, static pre-flight, local round-trip, fan-out incl. polling-fallback + convergence, edge cases, bug template, sign-off rules).
- [ ] ⬜ **Q-2 (Nov 6–7): QA round 1** — test Smith's PRs against checklist; bugs back to Smith with repro steps; loop until clean, then route to Foreman.
- [ ] ⬜ **Q-3 (due Nov 7): Catalog-rules audit** — security scan findings, capability declarations match reality, no core-UI touching, secrets policy.
- [ ] ⬜ **Q-4 (due Nov 9): Clean-install rehearsal** — fresh HERMES_HOME, install by repo, enable, two-gateway smoke test, report pass/fail to Foreman.
- [ ] ⬜ **Q-5 (Nov 10): Regression pass on any post-freeze fixes.**

## @northstar — Product

- [ ] 🔵 **N-1 (due Nov 4 EOD): Locked cut-list written down** — channels, DMs, agent posting, 2-gateway fan-out. Everything else = post-hackathon. **Status (Nov 5): late, no cut-list file in the repo. The board's backlog section is the interim yardstick until N-1 lands.**
- [ ] ⬜ **N-2 (due Nov 6): Demo narrative** — the story beats for Herald's script (hook: "hermes peer add" join flow; payoff: two agents collaborating in one channel).
- [ ] ⬜ **N-3 (due Nov 7): Naming/copy pass** — plugin name/description for catalog entry + README polish suggestions to Smith.

## @herald — Submission

- [ ] 🔵 **H-1 (due Nov 7): Demo script draft** — <90s, hook = join flow, demo = Tyler + wife's two instances. Nov 8 recording date is real. **Status: draft v1 done (`docs/submission/H-1-demo-script.md`, swappable-constants block added) — 78s shot-by-shot, hook + jaw-drop + X copy + Sentry rehearsal checklist. Awaiting Northstar N-2 narrative beats; final pass Nov 7.**
- [ ] ⬜ **H-2 (due Nov 7): Catalog PR package ready** — plugin-catalog/herd.yaml draft (entry schema, 40-char SHA, quoted version), PR description w/ surfaces + rule-13 disclosures. **Opens only after Foreman review + Tyler sign-off Nov 8.** **Status: draft v2 (`docs/submission/H-2-catalog-pr-package.md`) — capabilities reconciled with PR #4 (`herd_post`, `herd_list_channels`), `requires_hermes ">=0.22.0"`, rule-13 disclosures rewritten. Depends on the two PR #4 pre-open fixes.**
- [ ] ⬜ **H-3 (due Nov 8): Catalog PR opened** (post-approval) · demo video recorded.
- [ ] ⬜ **H-4 (due Nov 10): Video posted to X tagged @NousResearch · entry form submitted with both links** · report form confirmation to Foreman.

## @foreman — Project management

- [x] ✅ **F-1: Repo created** — github.com/tyleramberry/herd (public, verified).
- [ ] 🔵 **F-2 (daily): Verify each deliverable artifact personally** before marking Done; daily risk report. Reports in `docs/pm/` (latest: `docs/pm/2026-11-05-status.md`).
- [ ] 🔵 **F-3 (due Nov 8): Review catalog PR against judging criteria → Tyler approval gate.** Gate checklist drafted: `docs/pm/F-3-freeze-gate.md`.

---

## Post-hackathon backlog (do NOT build before Nov 11)

Threads · reactions · file sharing · presence indicators · voice · channel permissions · message search · Herd for >2 gateways · MySI plugin.
