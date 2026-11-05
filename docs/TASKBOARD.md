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

- [ ] 🔵 **S-1 (due Nov 4 EOD): Scaffold unified package** — plugin.yaml, __init__.py, schemas.py, tools.py, plugin_api.py (SQLite: channels, messages, participants), desktop/plugin.js. Pane + route render live from backend, empty state visible. Read Desktop Plugin SDK + "One package, both SDKs" first. Implement via Claude Code Opus 5.5, verify its output. PR to main.
- [ ] ⬜ **S-2 (due Nov 5): Two-gateway fan-out** — message posted on gateway A appears in channel view on gateway B. THE milestone; escalate to Foreman same night if slipping.
- [ ] ⬜ **S-3 (due Nov 5): Agent-side tools** — herd_post_message, herd_list_channels (agents post to channels from Bot Chats); register via plugin.yaml per catalog rules.
- [ ] ⬜ **S-4 (due Nov 6): Join/onboarding flow** — "hermes peer add" story in UI; channel-create + DM flows.
- [ ] ⬜ **S-5 (due Nov 7): Fix Sentry's QA round-1 bugs**; `hermes plugins validate` + `doctor` clean; screenshots for catalog PR.
- [ ] ⬜ **S-6 (Nov 8): Freeze** — bug fixes only.

## @sentry — QA

- [ ] ✅ **Q-1 (due Nov 4 EOD): QA checklist for Thursday milestone** — DONE: `docs/qa/Q1-SPINE-CHECKLIST.md` (SPINE gate = TC-2.1/2.2, static pre-flight, local round-trip, fan-out incl. polling-fallback + convergence, edge cases, bug template, sign-off rules).
- [ ] ⬜ **Q-2 (Nov 6–7): QA round 1** — test Smith's PRs against checklist; bugs back to Smith with repro steps; loop until clean, then route to Foreman.
- [ ] ⬜ **Q-3 (due Nov 7): Catalog-rules audit** — security scan findings, capability declarations match reality, no core-UI touching, secrets policy.
- [ ] ⬜ **Q-4 (due Nov 9): Clean-install rehearsal** — fresh HERMES_HOME, install by repo, enable, two-gateway smoke test, report pass/fail to Foreman.
- [ ] ⬜ **Q-5 (Nov 10): Regression pass on any post-freeze fixes.**

## @northstar — Product

- [ ] 🔵 **N-1 (due Nov 4 EOD): Locked cut-list written down** — channels, DMs, agent posting, 2-gateway fan-out. Everything else = post-hackathon. This file is the scope-creep yardstick.
- [ ] ⬜ **N-2 (due Nov 6): Demo narrative** — the story beats for Herald's script (hook: "hermes peer add" join flow; payoff: two agents collaborating in one channel).
- [ ] ⬜ **N-3 (due Nov 7): Naming/copy pass** — plugin name/description for catalog entry + README polish suggestions to Smith.

## @herald — Submission

- [ ] 🔵 **H-1 (due Nov 7): Demo script draft** — <90s, hook = join flow, demo = Tyler + wife's two instances. Nov 8 recording date is real. **Status: draft v1 done (workspace/H-1-demo-script.md) — 78s shot-by-shot, hook + jaw-drop + X copy + Sentry rehearsal checklist. Awaiting Northstar N-2 narrative beats; final pass Nov 7.**
- [ ] ⬜ **H-2 (due Nov 7): Catalog PR package ready** — plugin-catalog/herd.yaml draft (entry schema, 40-char SHA, quoted version), PR description w/ surfaces + rule-13 disclosures. **Opens only after Foreman review + Tyler sign-off Nov 8.** **Status: draft v1 done (workspace/H-2-catalog-pr-package.md) — herd.yaml per live entry-schema docs, quoted version "0.1.0", rule-13 disclosures drafted; capabilities + version pending Smith's plugin.yaml (S-1).**
- [ ] ⬜ **H-3 (due Nov 8): Catalog PR opened** (post-approval) · demo video recorded.
- [ ] ⬜ **H-4 (due Nov 10): Video posted to X tagged @NousResearch · entry form submitted with both links** · report form confirmation to Foreman.

## @foreman — Project management

- [ ] ✅ **F-1: Repo created** — github.com/tyleramberry/herd (public, verified).
- [ ] ⬜ **F-2 (daily): Verify each deliverable artifact personally** before marking Done; daily risk report to Chief.
- [ ] ⬜ **F-3 (due Nov 8): Review catalog PR against judging criteria → Tyler approval gate.**

---

## Post-hackathon backlog (do NOT build before Nov 11)

Threads · reactions · file sharing · presence indicators · voice · channel permissions · message search · Herd for >2 gateways · MySI plugin.
