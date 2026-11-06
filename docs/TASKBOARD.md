# Herd — Task Board

Project: multiplayer Hermes desktop plugin · Deadline: **Nov 11, 2026 5:00 PM EST** · Code freeze: **Nov 8**
Board owner: Foreman (PM). Update your own rows by editing this file in your PR. Mark 🔵 In progress / ✅ Done / ⛔ Blocked (state why).

---

## Milestones

| Date | Milestone |
|---|---|
| Thu Nov 5 | ✅ **SPINE — PASSED Nov 6** (one day late): two real Macs exchanged real messages through the plugin (TC-2.1/2.2, Q-9). See `docs/pm/2026-11-06-status.md`. |
| Sat Nov 7 | Validate + doctor clean; demo script final; polish pass done · **12:00 CUT #1 = F4/S-16** · **18:00 CUT #2 = F3/S-15** |
| Sun Nov 8 | **CODE FREEZE** · catalog PR opened · demo video recorded |
| Mon Nov 9 | Clean-install rehearsal (fresh HERMES_HOME, 2-gateway smoke test) |
| Tue Nov 10 | Video posted to X (@NousResearch) · entry form submitted |
| Wed Nov 11 | All three gates verified before noon EST |

---

## @smith — Engineering

- [ ] 🔵 **S-1 (due Nov 4 EOD): Scaffold unified package** — **Status (Nov 5): built in the fan-out PR.** plugin.yaml (3 tools, config_schema join form, requires_hermes ">=0.22.0"), `dashboard/herd_store.py` (SQLite: channels, messages, participants, peer_state), `dashboard/plugin_api.py`, `desktop/plugin.js` (route `/herd`, sidebar nav, right pane, empty states). Supersedes PR #4. Awaiting Sentry TC-0 + live `hermes plugins validate`/`doctor`.
- [x] ✅ **S-2 (due Nov 5, VERIFIED Nov 6): Two-gateway fan-out — SPINE PASSED ON REAL HARDWARE.** **Status (Nov 6 09:07 MST): Q-9 PASSED — Tyler's Mac and Brooklyn's Mac exchanged messages in both directions; TC-2.1/2.2 signed off on Tyler's first-hand confirmation. PR #26 (merged 33342b9) had fixed the background sync loop, which lost the profile secret scope and never synced on its own; the live window confirmed the fix and the #26 symptom (last_error back seconds after a success) did not recur.** Artifact still owed: signed run log — Q-10, `docs/qa/Q9-SPINE-RUNLOG.md`, due Nov 7 (F-3 gate A6). Linked side runs one `POST <peer>/herd/v1/sync` every 3 s (push its new messages, pull the peer's) on the peer's api_server, auth = peer's API_SERVER_KEY. One-sided link carries both directions. Simulated 2-gateway + real-HTTP tests green (ordering, dup convergence, offline catch-up, DMs). THE milestone: Sentry TC-2.1/2.2 on two real gateways is the gate.
- [ ] 🔵 **S-3 (due Nov 5): Agent-side tools** — **Status: done pending QA — verified Nov 5 (Smith).** `herd_list_channels`, `herd_post`, `herd_read_channel` (N-1/N-3 copy), registered in plugin.yaml `provides_tools`; agent posts carry `author_type=agent`. Verification on main @463df71: `hermes plugins validate` + `doctor --ci` pass (3 tools, declared==registered), 56 pytest green, `node --check` clean; live load via the real PluginManager in a fresh HERMES_HOME shows the `herd` toolset on-by-default for local/telegram/api_server (a Bot Chat is an ordinary local session), and registry dispatch of `herd_post` stored a message with `author_type=agent`, read back via `herd_read_channel`. Left for Sentry: TC-1.5 live Bot-Chat pass on real hardware.
- [ ] 🔵 **S-4 (due Nov 6): Join/onboarding flow** — **Status: done pending QA.** Join = Settings → Plugins → Herd form (peer name, URL, masked key via config_schema secret; Sentry CA-4 / rule 11), "Connect a teammate" button in the pane, New channel, New message (DM = dm-flagged 2-member channel).
- [x] ✅ **S-5 (due Nov 7): Fix Sentry's QA round-1 bugs** — merged #16 (replay semantics + dir-name-independent pytest). Remaining: live `hermes plugins validate`/`doctor` (Sentry TC-0.1/0.2) and catalog screenshots; `hermes plugins validate` + `doctor` clean; screenshots for catalog PR.
- [ ] ⬜ **S-6 (Nov 8): Freeze** — bug fixes only.
- [x] ✅ **S-7 (shipped Nov 5, gate cleared Nov 6): @mention wake** — **Tyler approved the build (Nov 5): "Yes, build it."** **Merged Nov 5 as #13 (opt-in `/herd-listen`, `mention_wake` setting, `inject_message`); Sentry TC-4 cases merged (#18).** **GATE RESOLVED — GO (Foreman, Nov 6): S-7 STAYS IN** — documented, in the catalog entry, and as demo beat 5B. The gate was "go only if TC-2 has passed on real hardware"; Q-9 passed Nov 6. No cut, no freeze slip, no NO-GO fallback needed. Default off (ctx.inject_message + allow_gateway_injection). Rule-13 disclosure and H-2 capabilities must be updated if it ships.
- [x] ✅ **S-8 (Nov 6): Passive side sees an incoming peer link** — merged #21 (`status.incoming` + "add them back" UI).
- [x] ✅ **S-10 (Nov 6): Single + button** with New channel / New message menu — merged #20.
- [x] ✅ **S-9 (Nov 6): @-mention autocomplete** — **merged #19 (f420eeb).** Sentry's round-1 S2 (a single plugin-global `mentionState` shared by the page and pane composers) IS FIXED on main: `desktop/plugin.js:48` is per-surface (`mentionState = { page: atom(null), pane: atom(null) }`). Two of the three S3s (pick-tail, Shift+Enter) landed as **#36 (46f2343)**; anything left is polish-tier and Foreman decides at freeze.
- [x] ✅ **S-11 (Nov 6): Threads** — **merged #23 (a9f103a).**
- [x] ✅ **S-12 (Nov 6): Reactions** — merged #24 (44035e0); Sentry round 1 PASSED.
- [x] ✅ **S-17 (Nov 6): Rebase #19/#23/#24 onto main and fix S-9 findings** — **the deliverable is on main:** #19 f420eeb, #23 a9f103a, #24 44035e0, S-12 resurrection fix #34, S-9 pick-tail/Shift+Enter fix #36. Nothing left to land.
- [x] ✅ **S-13 (Nov 6, Tyler directive F1) — MERGED #37 (protocol v2).** Demonstrated with a real DM→channel promote; QA's two-gateway gate is TC-10.4. Original spec: — one action in an open DM ("Share to a channel") creates a named channel and replays the DM's messages into it in order; appears on both gateways within a cycle; DM untouched. `PROTOCOL_VERSION` bump. **Done means:** see `docs/product/N-5-CUT-LIST-AMENDMENT.md` §1 F1. Must pass two-gateway, not just unit tests (R-5). QA: Q-7. Est 4 h.
- [x] ✅ **S-14 (Nov 6, Tyler directive F2) — MERGED #33 (d3caf25); duplicate PR #35 closed by Foreman as stale (its base would have reverted S-11 threads).** **Status: on main — TC-4.10–4.16 covered by tests; the DM ref is now the partner name / `dm:` id so `herd_post` resolves it; missing channel suppresses the wake.** — wake text carries who asked (+channel), what is expected, where to report back (`herd_post` ref). All S-7 guards unchanged: mentions only, one wake per message, agent messages never wake, default off, `allow_gateway_injection`. QA: Q-7 (extends TC-4). Est 3 h. **Never cut.**
- [ ] ⬜ **S-15 (Nov 7, Tyler directive F3): Live supervision status line + speaker badge** — one short phrase from a fixed vocabulary (`reading the code` / `writing the code` / `reviewing` / `done` / `idle`) beside in-flight agent work, plus a human/agent badge per message. No tool-activity stream. Rides existing `broadcast_plugin_event` + 3 s poll. New tool → `provides_tools` + `herd.yaml` capability + rule-13. **Cut #2 if not merged by Sat 18:00.** QA: Q-7. Est 6 h.
- [ ] ⬜ **S-16 (Nov 7, Tyler directive F4): Agent response links to the Kanban board** — an agent's channel answer tied to a Kanban task id shows a link/badge with id + title that opens the task on the `herd` board. Tie is explicit, never guessed. **Q-8 CLEARED** (YES — read-only under rule 13) **but deliberately PARKED by Foreman: WIP limit (Smith's queue) + CUT #1.** Unparks at the Sat 12:00 cut decision, or sooner if S-15 lands early. The id-only fallback also remains compliant. **Cut #1 if not merged by Sat 12:00.** Est 6 h.
- [ ] ⛔ **NOT BUILT (Tyler, Nov 6): identities & permissions (directive #1) · concurrency safety (directive #6).** No design, no branch. Post-hackathon.

## @sentry — QA

- [x] ✅ **Q-1 (due Nov 4 EOD): QA checklist for Thursday milestone** — DONE: `docs/qa/Q1-SPINE-CHECKLIST.md` (SPINE gate = TC-2.1/2.2, static pre-flight, local round-trip, fan-out incl. polling-fallback + convergence, edge cases, bug template, sign-off rules).
- [ ] 🔵 **Q-2 (Nov 6–7): QA round 1** — test Smith's PRs against checklist; bugs back to Smith with repro steps; loop until clean, then route to Foreman. **Nov 5: #9 static pass (TC-0.3–0.9) green, 49 tests. Live TC-0.1/0.2 (validate/doctor) and TC-2 need Tyler's two Macs.**
- [ ] 🔵 **Q-3 (due Nov 7): Catalog-rules audit** — security scan findings, capability declarations match reality, no core-UI touching, secrets policy. **Round 1 done Nov 5: `docs/qa/Q3-CATALOG-AUDIT.md` + `scripts/qa/catalog_audit.py`. All 3 S1s fixed in #9 (merged); audit on main = 0 FAIL. Re-run at freeze.**
- [ ] 🔵 **Q-4 (due Nov 9, UNBLOCKED Nov 6): Clean-install rehearsal** — fresh HERMES_HOME, install by repo, enable, two-gateway smoke test **on the FROZEN build** (this is the proof that covers the shipped SHA — the Nov 6 SPINE window ran a pre-freeze build), report pass/fail to Foreman. Script ready: `docs/qa/Q4-CLEAN-INSTALL.md`.
- [ ] ⬜ **Q-5 (Nov 10): Regression pass on any post-freeze fixes.**
- [ ] ⬜ **Q-7 (Nov 6–7, new scope): QA plan + loop for S-13/S-14/S-15** — extend Q-6 with a promote-share case (message order preserved, DM intact, both gateways converge), a wake-context case (who/what/where present, all S-7 guards still hold — extend TC-4), and a status case (fixed vocabulary only, no phrase invented when unset, badge correct). Bugs back to Smith with repro steps.
- [x] ✅ **Q-8 (Nov 6, RULED 09:03 — YES, read-only under rule 13; CA-4 does not govern it; seven binding constraints on t_8f745620): May a catalog plugin read `~/.hermes/kanban/boards/<slug>/kanban.db`?** Written yes/no to Foreman before S-16 is started. If no, S-16 ships id-only. Owner: Sentry.
- [x] ✅ **Q-9 (Nov 6): SPINE two-gateway verification on real hardware (TC-2.1/2.2)** — **PASSED.** Two real Macs exchanged messages in both directions; signed off on Tyler's first-hand confirmation (card t_4e0473ee, closed 09:07). Foreman cross-check at main `e967130043da0f4eed67e3419c1c47b56bdbf471`: pytest **125 passed / 3 skipped**, `node --check` OK, `plugins validate` pass, `doctor --ci` clean (3 tools / 0 hooks), `catalog_audit` 0 FAIL / 1 known WARN (rule 9).
- [ ] 🔵 **Q-10 (due Nov 7): SPINE run-log artifact** — `docs/qa/Q9-SPINE-RUNLOG.md`: TC-2.1/2.2 rows, plugin SHA per side, `peer_state` evidence, honest attestation of who ran it, two-Mac topology. **F-3 gate item A6 has no artifact without this.** Owner: Sentry.

## @northstar — Product

- [x] ✅ **N-1 (due Nov 4 EOD): Locked cut-list written down** — DONE Nov 5: `docs/product/N-1-CUT-LIST.md`. IN = channels, 2-gateway fan-out, peer join, agents post **and read** (`herd_list_channels`, `herd_post`, `herd_read_channel`), DMs (= 2-person channel). OUT incl. auto-wake/@mention triggers. Join = Herd's own Add-teammate form (core peer registry off-limits per Q-3 CA-4). Positioning vs. core Group Chat added (CA-8): Herd connects people, not just bots.
- [x] ✅ **N-2 (due Nov 6): Demo narrative** — DONE Nov 5: `docs/product/N-2-DEMO-NARRATIVE.md`. 6 beats for Herald; adds a 5s human-to-human beat before the jaw-drop; shot 4 = Riley *hands* the task to her agent (no auto-wake in v1).
- [x] ✅ **N-3 (due Nov 7): Naming/copy pass** — DONE v1 Nov 5: `docs/product/N-3-NAMING-COPY.md` (catalog title/description for H-2, tool descriptions + UI strings + README suggestions for Smith). Will re-check against real UI Nov 7.

## @herald — Submission

- [ ] 🔵 **H-1 (due Nov 7, UNBLOCKED Nov 6): Demo script final** — <90s, hook = people-first "Hermes is single-player. We made it multiplayer.", demo = Tyler + Brooklyn on two Macs. **Status: v9 (docs/submission/H-1-demo-script.md, Nov 6) — ~81s, timings verified contiguous, locked constants (Brooklyn, LAN addr approved on camera, key masked). Foreman go/no-go = GO (Q-9 TC-2 on two real Macs) → @mention (S-7 #13 + S-9 #19 + S-14 #33) is the PRIMARY shot-5 take; take 5-baseline = fallback of record. Reaction beat shot 5A (S-12 #24) kept; threads ambient-only. Gated new-scope surfaces (S-13/S-15/S-16) staged in H-6, applied at freeze only if merged + QA-green. ⚠️ REHEARSAL PREREQ: the live two-Mac window ran a build 28 commits behind main (QA SPINE run log) — update the demo rig to the current build before the Sentry rehearsal and the Nov 8 record.**
- [ ] ⬜ **H-2 (due Nov 7): Catalog PR package ready** — plugin-catalog/herd.yaml draft (entry schema, 40-char SHA, quoted version), PR description w/ surfaces + rule-13 disclosures. **Opens only after Foreman review + Tyler sign-off Nov 8.** **Status: draft v3 merged (#14) (docs/submission/H-2-catalog-pr-package.md) — checked against live catalog README: fixed capability keys (`provides_*`), category → desktop, added image/screenshots. Capabilities from Smith; requires_hermes ">=0.22.0" per Sentry (oldest verified, Tyler's Mac); rule-11 Q1 resolved (strip use_hermes_peers).**
- [ ] ⬜ **H-3 (due Nov 8): Catalog PR opened** (post-approval) · demo video recorded.
- [ ] ⬜ **H-4 (Nov 10): Video posted to X tagged @NousResearch · entry form submitted with both links** · report form confirmation to Foreman.
- [ ] ⬜ **H-6 (Nov 6–7, Tyler directive): Submission surfaces for the new scope** — update H-1 demo script, the `herd.yaml` capability list, and the rule-13 disclosures to cover S-13 (new promote-write path + protocol bump), S-15 (new tool + status surface) and S-16 (Kanban link) **only if each is actually merged at freeze**. Cut features must not appear in the script or the catalogue entry. Needs Smith's capability list before H-2 is final.

## @foreman — Project management

- [x] ✅ **F-1: Repo created** — github.com/tyleramberry/herd (public, verified).
- [ ] 🔵 **F-2 (daily): Verify each deliverable artifact personally** before marking Done; daily risk report. Reports in `docs/pm/` (latest: `docs/pm/2026-11-06-status.md`).
- [ ] 🔵 **F-3 (due Nov 8): Review catalog PR against judging criteria → Tyler approval gate.** Gate checklist drafted: `docs/pm/F-3-freeze-gate.md`.

---

## Post-hackathon backlog (do NOT build before Nov 11)

File sharing · presence/typing indicators · voice · channel permissions · message search · Herd for >2 gateways · full tool-activity stream (F3 ships one phrase only) · Kanban link beyond id-only (if F4 is cut or id-only) · identities & permissions (Tyler, Nov 6: wait) · concurrency safety hardening (Tyler, Nov 6: not yet) · MySI plugin.
