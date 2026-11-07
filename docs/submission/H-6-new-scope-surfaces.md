# H-6 — Submission surfaces for the new scope (S-13 / S-15 / S-16) — **APPLIED (F-3 REVISED)**

Owner: @herald · Prepared Fri Nov 6, 2026 · **Applied Sat Nov 7, 2026** (Nov 8 freeze cancelled — F-3 REVISED)
Applies to **H-1** (demo script), **H-2** (catalog entry `herd.yaml` + PR description / "surfaces used"),
and the **README** rule-13 disclosures.
Base: `origin/main` @ **`cd6d46c`** (verified 2026-11-07).

> ## THE RULE (post-freeze — `docs/pm/F-3-gate-REVISED.md`)
> The Nov 8 freeze is **cancelled**. There is no freeze SHA to gate on any more; the gate is now
> **merged to `origin/main` *and* QA-green at the head being pinned**, re-checked at every pin bump.
> A **cut** feature must not appear in the script or the catalog entry (N-5 §3) — but a feature's
> **behaviour is disclosed whenever its code ships**, even when its demo beat is held back. This file is
> now the record of what was applied, to which file, and why; the one block **not** applied (S-13's demo
> beat) is retained below with its own apply gate.

---

## 0. State at apply time (Nov 7, re-verified against `origin/main` @ `cd6d46c`)

| Feature | Board | Merge / QA verdict | Gate | Applied? |
|---|---|---|---|---|
| **S-13** promote DM → channel (F1) | `S-13` | **merged #37 @ `9d9c6e7`** (protocol v2); Sentry Q-7 verdict **PASS** on `941e975` — TC-10.4 two-gateway **harness** pass | **F-3 gate B1 still open** — TC-10.4 on **two real Macs** not yet evidenced; re-verified under **Q-11** (`t_16d10f75` harness, `t_a23e959b` pin gate) | **Disclosure: APPLIED** (code ships). **Demo beat 6A: RETAINED** (§2.1) until Q-11 closes. |
| **S-15** status line + badge (F3) | `S-15` | **merged #41 @ `5ab0a0b`**; Sentry QA **PASSED** on `6688b8b` | merged + QA-green ✅ | **APPLIED** — H-1 shot 5 (ambient); H-2 4 tools + rule-13; README. |
| **S-16** Kanban link (F4) | `S-16` | **merged #46 @ `a20f742`**; Sentry QA **APPROVE** on `35debd8` | merged + QA-green ✅ (Q-8 = YES; board-level nav per PM ruling #47) | **APPLIED** — H-1 shot 6 (ambient); H-2 PR bullet + read line; README. |
| Smith capability list | — | answered Nov 6 (S-13/S-15) + Nov 7 (S-16) | §5 closed ✅ | — |
| Sentry Q-8 ruling | `Q-8` | **YES — read-only `kanban.db` under rule 13**, 7 constraints | recorded ✅ | §3.3 **DB-read** branch applied. |

**Where each block landed:** H-1 v10 (`docs/submission/H-1-demo-script.md`), H-2 v7
(`docs/submission/H-2-catalog-pr-package.md` + `docs/submission/plugin-catalog-herd.yaml`), README
disclosures. **The only unapplied block is S-13's shot 6A beat** — see §2.1.

---

## 1. Apply procedure used (mechanical)

1. `git fetch origin && git rev-parse origin/main` → base `cd6d46c`.
2. Confirm each feature is in the tree (not just on a branch): `git log origin/main --oneline` → **S-13 #37, S-15 #41, S-16 #46** all present; QA verdicts read from the cards (**S-13 PASS, S-15 PASS, S-16 APPROVE**).
3. Apply the blocks whose gate is met; for S-13 apply the **disclosure** but hold its **beat** (F-3 B1 open).
4. Re-time H-1 (§2.5); the total must stay **≤85s** (90s cap).
5. Mirror the applied rule-13 lines into `README.md` **verbatim** (§4) — README and PR description must be identical for the new-scope lines (Q-3 CA-5).
6. Hand the applied set to Sentry for the Q-3 re-audit at the pin, and re-run the two gates at every bump.

---

## 2. H-1 — demo-script deltas (status)

Base timeline = H-1 **v10** (`origin/main` @ `cd6d46c`). v9's mention take (S-7/S-9/S-14), shot 5A
reaction (S-12) and locked constants are unchanged.

### 2.1 — S-13: promote a DM into a shared room  ·  **RETAINED — NOT applied** *(merged #37; F-3 B1 two-real-Mac gate open)*

> **Why held:** S-13 is merged (protocol v2) and Sentry's Q-7 verdict is **PASS** (incl. a TC-10.4
> two-gateway **harness** run). But the **F-3 gate B1** ("TC-10.4 on **two real gateways**") is still open
> and is being re-verified under **Q-11**. Per the gate the demo beat stays out until that closes. Its
> **rule-13 disclosure already ships** (§4) — a merged behaviour is disclosed even when its beat is held.

New shot, ~5s, inserted **after shot 6** and before shot 7; call it **shot 6A**. **Apply only if Q-11
closes before recording, then re-time to ≤85s** (v10 = 79s, so 6A at +5s lands cleanly at ~84s).

| # | Time | Beat | Screen | VO / on-screen |
|---|------|------|--------|----------------|
| 6A | (+5s) | **Private → shared** | Right pane, DM view → hard cut to both screens | Cut to the Tyler↔Brooklyn DM. Brooklyn clicks **Share to a channel**, names it `#project-notes`. Hard cut: the new channel appears **on both Macs** with the DM's messages replayed in order. No VO on the click; one line after: **"That private thread? One click and it's a room."** |

- Why it earns the 5s: the one beat that shows a DM becoming shared — the gap N-5 F1 exists to close.
- Promote **copies**, so a misbehaving take still leaves the DM on screen — but do not show a failed promote: re-take, do not narrate.
- Word rules unchanged: say **channel**, never "promote"/"migrate"/"SQLite".
- Pre-req on camera: both Macs show the promoted channel within one sync cycle (hold on the left ≤3s).
- **Cut checklist (§2.6) applies if Q-11 fails** — the beat, its rehearsal line and any H-1 mention come out.

### 2.2 — S-15: supervision status line + speaker badge  ·  **APPLIED in shot 5 (ambient, no narrated beat)**

- In **shot 5** (handoff), Brooklyn's agent's in-flight work shows one phrase from the fixed vocabulary
  (`reading the code` · `writing the code` · `reviewing` · `done` · `idle`) beside it. If a take shows it
  cleanly, hold **2s** when the phrase flips (e.g. `writing the code` → `done`). No VO — ambient.
- Human/agent **badges** are visible in every shot from 5 on (already required by N-2). Call out nothing.
- **Scope (Sentry D-5, confirmed by Smith):** status is **local-gateway-agents only**, in the gateway
  process's memory (never `herd.db`, never peer-synced; `PROTOCOL_VERSION` untouched), delivered by
  `_notify`→`broadcast_plugin_event` + the pane's 3s `/status` poll — so the phrase shows on **the machine
  whose agent is working** (in shot 5, **Brooklyn's Mac**).
- **Lifetime:** clears after **5 minutes** or on gateway restart → **set it fresh in each take**.
- Unset ⇒ the pane shows **nothing** — never cut to an empty status slot expecting a phrase.
- Rehearsal line added to H-1 (for @sentry): phrase shows only the fixed vocabulary; nothing invented or
  stale when unset; badge correct on a human and on an agent message (Q-7 TC-11.1–11.3, 11.6).

### 2.3 — S-16: agent answer links to the Kanban board  ·  **APPLIED in shot 6 (ambient glance, ≤2s)**

**Ambient glance at the end of shot 6:** the agent's answer carries a task badge.

- **Q-8 = YES (DB read):** the badge shows **task id + title**. Hold 2s; Tyler clicks it → the `herd`
  board opens (**board-level**: the badge carries the task id; the card itself is **not** focused — PM
  ruling #47, `docs/pm/2026-11-07-s16-click-ruling.md`). One line: **"Every answer points back at the work."**
- The id-only fallback (Q-8 = NO) is **not** in play — Q-8 was ruled YES.
- This is the **first beat to drop** if the take runs long (matches N-5 §3 cut order).

### 2.4 — Time donors (as applied to v10)

| Beat | v9 → v10 as cut | frees |
|---|---|---|
| Shot 7 "Name it" | 12s → **9s** | −3s |
| Shot 8 end card | 5s → **4s** | −1s |
| **Total available** | | **−4s** |

Shot 5 (22s) is the @mention take by design and **cannot** donate. The S-16 glance **adds** 2s inside
shot 6 (12s → 14s); the S-15 status phrase is **ambient** inside shot 5 (no added hold). Shot 5A stays 4s.

### 2.5 — Timing ledger

| State | Seconds |
|---|---|
| v9 base (shots 1–4, 5, 5A, 6–8) | 81s |
| **v10 as cut** — S-15 ambient (shot 5) + S-16 +2 (shot 6); donors 7 −3 / 8 −1 | **79s** ✅ (11s under cap; ≤85s target held) |
| *If S-13's beat is applied* (shot 6A +5s, no further donors) | **84s** ✅ (still ≤85s) |

Everything stays under the 90s cap; the ≤85s target holds in both states. If a take lands over 85s: drop
the S-16 glance first, then the S-15 glance, then the S-13 shot — reverse of story value. Never cut the
hook or shots 2–4.

### 2.6 — Cut / not-applied = must-not-appear checklist

For any block **not** applied (currently only S-13's beat), confirm **none** of these appear in H-1:
- [ ] No H-1 shot/row mentioning the feature (no 6A row while S-13's beat is held).
- [ ] No rehearsal-checklist line for the held feature.
- [ ] No `herd.yaml` capability or PR-description **beat** for it — **but its rule-13 disclosure line stays** (behaviour ships).
- [ ] Timings return to the applicable ledger row.

---

## 3. H-2 — `herd.yaml` capability list + PR-description deltas (status)

`herd.yaml` is the catalog entry added by H-3's PR to `NousResearch/hermes-agent`
(`plugin-catalog/herd.yaml`); the `capabilities:` block must equal what the pin registers (**rule 6**).

### 3.1 — S-13  ·  **APPLIED (disclosure only)**  *(names corrected Nov 7 per Sentry Q-7)*
- **`capabilities:` — NO CHANGE.** Promote adds no tool; `herd_list_channels` already lists the new channel.
- **Write path (code of record, verified):** the desktop half calls a **local-only** backend route
  **`POST /api/plugins/herd/channels/{channel_id}/share`** (`dashboard/plugin_api.py`); the teammate's
  gateway is reached by the **same** `POST /herd/v1/sync` call already disclosed. **`PROTOCOL_VERSION`
  1 → 2**; the message row gains **`promoted_from`** (the source DM id) so both gateways converge.
  *(The earlier staged names `…/promote` and `origin_channel_id` were **wrong** — do not use them.)*
- **Protocol honesty (Sentry TC-10.11):** the version is bumped **once**, readable from
  `/herd/v1/ping` + `/status`; **peers do not enforce `v`** (`handle_peer_sync` reads no version field),
  so a newer-protocol body is accepted, not refused (verified live: `{"v":3,…}` → HTTP **200**). Disclosed,
  not a silent pass.
- **Checklist:** "protocol version bump (1 → 2) disclosed" ✅.

### 3.2 — S-15  ·  **APPLIED (merged on main @ `5ab0a0b`, #41)**
- **`capabilities.provides_tools`:** `herd_set_status` appended — the exact name, no others (single arg
  `status`, a 5-value enum). **The 4th declared tool** — `herd.yaml` and `plugin.yaml` both go 3 → 4, and
  **`catalog_audit.py` shows 4 tools, not 3** (Sentry TC-0.8). ✅
- **Confirmed none:** no new hook, no new middleware, no `requires_env`.
- **Rule-13 line** (§4) applied: local-only, gateway-memory only (D-5), no peer sync, no `herd.db` write,
  self-clears.

### 3.3 — S-16  ·  **APPLIED (merged #46; Q-8 = YES, DB read)**
- **`capabilities:` — NO CHANGE.** No new tool/hook/middleware/`requires_env`; `provides_tools` stays **4**,
  so rule 6 is untouched and `catalog_audit.py --expect-tools` needs no edit.
- **PR bullet (as shipped in PR #46):** `- Kanban link: an agent's answer can carry a task-id + title badge; the title is read from the local Kanban database (**read-only**), and clicking the badge opens the herd board. The task id is passed explicitly by the agent.` *(board-level, per PM ruling #47.)*
- **Rule-13 line** (§4, reads-outside-own-data) applied verbatim to README + PR description.
- **CA-7 ("reads outside plugin data: none") was deleted** and replaced by the read line (README + H-2). ✅

---

## 4. Rule-13 disclosures — **applied to PR description AND `README.md` verbatim**

Rule 13 (*"Risky behaviour is disclosed"*): network calls, reads outside own data, shell commands,
long-running background processes, stored credentials. README and PR description carry these **identical**
(Q-3 CA-5).

**S-13 — APPLIED** *(authored by @smith; signed off by Sentry Q-7)*:
> - **Sharing a DM to a channel.** "Share to a channel" on a DM asks this gateway to create a named channel and copy that DM's messages into it. It is a copy: the DM and its history are never modified or deleted. The copies are written to Herd's own SQLite file and reach your teammate's gateway through the same `POST <url>/herd/v1/sync` request already disclosed above, as part of the normal sync payload (Herd sync protocol v2 — copied rows now carry the source DM's id so both gateways converge on the same rows). No new endpoint, no new outbound host, no new credential, no shell command.

**S-15 — APPLIED** *(shipped README wording is canonical — H-2 copies it verbatim; Sentry TC-11.8 gate)*:
> - **Agent status:** an agent may set one short phrase (herd_set_status, e.g. "writing the code") that the pane shows beside its work. It lives in the gateway process's memory only — never written to herd.db, never sent to your teammate's gateway — and it disappears after five minutes or when the gateway restarts.

**S-16 — APPLIED (Q-8 = YES)** *(reads-outside-own-data — mandatory under rule 13)*:
> - **Reads outside plugin data:** to label an agent's answer, the Herd pane reads a task's title from the local Kanban database at `~/.hermes/kanban/boards/<slug>/kanban.db` — **read-only**, never written, no schema assumptions; if the file is missing or locked the pane shows the task id only. The id itself is passed explicitly by the agent and travels with the message in the normal sync payload; a peer that predates the field ignores it.

*(The S-16 "Q-8 = NO" id-only variant is retired — Q-8 was ruled YES.)*

---

## 5. What H-6 needed from @smith (capability list) — **CLOSED**

1. **S-15** — ✅ answered: tool **`herd_set_status`** (exact, no others; single arg `status`, 5-value enum);
   an **agent tool** registered via `ctx.register_tool(...)` in `__init__.py::register()` ⇒ 4th entry in
   **both** `plugin.yaml provides_tools` and `herd.yaml capabilities.provides_tools`; no new
   hook/middleware/`requires_env`; **local-only** (D-5, in gateway memory).
2. **S-13** — ✅ answered: no new tool; `PROTOCOL_VERSION` **1 → 2**; route `…/share`; field `promoted_from`;
   same `POST /herd/v1/sync` endpoint; copies never wake an agent.
3. **S-16** — ✅ answered (Smith, Nov 7, PR #46): **no** capability/declaration change; title read is one
   `SELECT title FROM tasks WHERE id = ?` over a `mode=ro` URI, profile-aware path, soft-degrade to id-only.

---

## 6. Open items

- [x] @smith: **S-13** disclosure text → applied (§3.1/§4).
- [x] @smith: **S-15** capability list → applied (§2.2/§3.2/§4).
- [x] @smith: **S-16** disposition → applied (§3.3/§4).
- [x] @sentry: Q-8 ruling → applied (DB-read branch).
- [x] H-1 v10 re-timed to ≤85s (§2.5); H-2 / `herd.yaml` updated; README mirrored (§4).
- [ ] **S-13 demo beat (shot 6A)** — apply only if the F-3 B1 gate (TC-10.4 on two real Macs) closes under **Q-11**; then re-time and re-hand to Sentry.
- [ ] At open (and every bump): re-run `hermes plugins validate . --install-deps` and
  `catalog_audit.py --entry herd.yaml` at the exact pin; hand the applied set to Sentry for the Q-3 re-audit.
