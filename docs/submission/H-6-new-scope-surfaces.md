# H-6 — Submission surfaces for the new scope (S-13 / S-15 / S-16) — **GATED STAGING**

Owner: @herald · Prepared Fri Nov 6, 2026 · Applies to **H-1** (demo script), **H-2** (catalog entry
`herd.yaml` + PR description / "surfaces used"), and the **README** rule-13 disclosures.
Base: `origin/main` @ **cf5281f** (verified 2026-11-06 09:03 MST; includes S-12 #24, Sentry Q-7 plan #29, Foreman F-2 #28).

> ## THE ONE RULE
> **Nothing in this file goes into H-1, H-2, the catalog entry or the README until the feature it
> describes is MERGED to `origin/main` at the freeze SHA *and* QA-green.** A cut feature must not
> appear in the script or the catalog entry (N-5 §3, "out of the demo script the same hour it is cut").
> This file is the **staging area** — the gated blocks are pre-written so freeze-day is mechanical.
>
> Do **not** paste a block below into a canonical file while its feature is unmerged. If you are
> reading a canonical file and see any of this text without its feature merged, delete it.

Placeholders are marked **`TODO(at-freeze):`**. Capability names come from **Smith** (§5); the S-16
disposition comes from **Sentry Q-8**.

---

## 0. Merge state at prep time — **re-verify at freeze**

| Feature | Board | Branch / PR | State at prep | Gate to apply its block |
|---|---|---|---|---|
| S-13 promote DM → channel (F1) | `S-13` | `wt/s13-promote`, no PR yet | not merged | merged + QA Q-7 green + TC-2 (two-gateway) |
| S-15 status line + badge (F3) | `S-15` | `wt/s15-status`, no PR yet | not merged | merged + QA Q-7 green |
| S-16 Kanban link (F4) | `S-16` | none (blocked on Q-8) | not merged, **cut #1** | merged + Q-8 ruling recorded + QA green |
| Smith capability list | — | H-6 dependency | **S-13 + S-15 received**; S-16 disposition still pending | §5 answered (S-13, S-15) |
| Sentry Q-8 ruling | `Q-8` | — | **no ruling yet** | id-only vs DB-read decides §3/§4 S-16 lines |

S-16 is **cut #1** (Sat Nov 7 12:00) and S-15 is **cut #2** (Sat Nov 7 18:00). The most likely freeze
outcome is **S-13 alone, or S-13 + S-15**. The combination table in §2.5 covers every case.

---

## 1. Freeze-day procedure (mechanical, ~30 min)

1. `cd ~/herd && git fetch origin && git rev-parse origin/main` → **freeze SHA** (40 hex).
2. For each feature, confirm it is actually in the freeze tree (not just a branch):
   `git log origin/main --oneline | grep -iE "<feature word>"`, and confirm the S-* PR shows MERGED.
3. Apply **only** the blocks whose gate is met (§2 for H-1, §3 for `herd.yaml`/H-2, §4 for rule-13
   lines). Delete every block whose feature is not merged — **including the H-1 lines and README lines.**
4. Re-time H-1 against the combination table (§2.5); the total must be **≤85s** (90s cap).
5. Mirror the applied rule-13 lines into `README.md` **verbatim** (§4) — README and PR description
   must carry identical lines (Q-3 CA-5).
6. Hand the applied set to Sentry for the Q-3 re-audit at the freeze SHA (F-3 rows C3/C5).

---

## 2. H-1 — demo-script deltas

Base timeline = main's H-1 **+ PR #25 (H-5 beats)** + **PR #27 (locked constants)** — both still OPEN,
both touch this file, so apply H-6 *after* they merge or H-1 will conflict. Anchor the inserts by the
quoted text below, not by line number, so they survive a rebase.

### 2.1 — S-13: promote a DM into a shared room  ·  **APPLY IF S-13 MERGED**

New shot, ~5s, inserted **after shot 6** ("Back to him") and before the end card; call it **shot 6A**.

| # | Time | Beat | Screen | VO / on-screen |
|---|------|------|--------|----------------|
| 6A | (5s) | **Private → shared** | Right pane, DM view → hard cut to both screens | Cut to the Tyler↔Brooklyn DM. Brooklyn clicks **Share to a channel**, names it `#project-notes`. Hard cut: the new channel appears **on both Macs** with the DM's messages replayed in order. No VO on the click; one line after: **"That private thread? One click and it's a room."** |

- Why it earns the 5s: it is the one beat that shows a DM becoming shared — the gap N-5 F1 exists to close.
- Safety for the take: promote **copies**, so if it misbehaves the DM is still on screen — but do not
  show a failed promote: re-take, do not narrate.
- Word rules unchanged: say **channel**, never "promote"/"migrate"/"SQLite".
- Pre-req on camera: both Macs must show the promoted channel within one sync cycle (hold on the left ≤3s).

### 2.2 — S-15: supervision status line + speaker badge  ·  **APPLY IF S-15 MERGED**

**Ambient by default; optional 2s glance.** Do **not** give it a narrated beat.

- In **shot 5** (handoff), Brooklyn's agent's in-flight work shows one phrase from the fixed vocabulary
  (`reading the code` · `writing the code` · `reviewing` · `done` · `idle`) beside it. If a take shows
  it cleanly, hold **2s** on the pane when the phrase changes (e.g. `writing the code` → `done`).
- Human/agent **badges** are visible in every shot from 5 on (already required by N-2). Call out nothing.
- **Scope (Sentry D-5, confirmed by Smith):** status is **local-gateway-agents only**, in the gateway
  process's memory (never `herd.db`, never peer-synced; `PROTOCOL_VERSION` untouched), delivered by
  `_notify`→`broadcast_plugin_event` + the pane's 3s `/status` poll. In the split-screen take the agent's
  phrase therefore shows on **the machine whose agent is working** — in shot 5 that is **Brooklyn's Mac**.
- **Lifetime:** it clears after **5 minutes** or on gateway restart — so **set it fresh in each take**;
  do not expect a phrase left over from a rehearsal to still be there.
- If no status was ever set, the pane shows **nothing** — do not cut to an empty status slot expecting a phrase.
- Add to the rehearsal checklist (for @sentry): "Status phrase shows only the fixed vocabulary; nothing
  invented or stale when unset; badge correct on a human and on an agent message — 3× in a row (Q-7 TC-11.1–11.3, 11.6)."

### 2.3 — S-16: agent answer links to the Kanban board  ·  **APPLY IF S-16 MERGED**

**Ambient glance, ≤2s**, at the end of **shot 6**: the agent's answer message carries a task badge.

- **If Q-8 = YES (DB read allowed):** the badge shows **task id + title**. Hold 2s; Tyler clicks it → the
  `herd` board opens on that task. One line: **"Every answer points back at the work."**
- **If Q-8 = NO (id-only fallback):** same beat, badge shows the **id only** (no title). Click still opens
  the board. Do not show a title if the plugin is not allowed to read it.
- This is the **first beat to drop** if the take runs long (matches N-5 §3: S-16 is cut first).

### 2.4 — Time donors (pre-agreed; take seconds only from here)

| Beat | was | becomes | frees |
|---|---|---|---|
| Shot 5 handoff | 24s | 22s | −2s |
| Shot 5A reaction (S-12) | 3s | 2s | −1s |
| Shot 7 "Name it" | 12s | 9s | −3s |
| Shot 8 end card | 5s | 4s | −1s |
| **Total available** | | | **−7s** |

### 2.5 — Combination table (base v7 shot sum = **80s**; must stay ≤85s)

| Merged at freeze | Donors applied | New seconds | Total | Verdict |
|---|---|---|---|---|
| none | — | 0 | **80s** | v7 as-is (PR #25) |
| S-13 only | 5 → 22 (−2), 7 → 9 (−3) | +5 (6A) | **80s** | ✅ default if F3/F4 cut |
| S-15 only | 7 → 9 (−3) + 5 → 23 (−1) | +2 | **79s** | ✅ |
| S-16 only | 7 → 9 (−3) + 5 → 23 (−1) | +2 | **79s** | ✅ |
| S-13 + S-15 | 5 → 22 (−2), 7 → 9 (−3), 8 → 4 (−1) | +7 | **81s** | ✅ **most likely** |
| S-13 + S-16 | 5 → 22 (−2), 7 → 9 (−3), 8 → 4 (−1) | +7 | **81s** | ✅ |
| S-15 + S-16 | 5 → 22 (−2), 7 → 9 (−3), 8 → 4 (−1) | +4 | **79s** | ✅ |
| **all three** | all of §2.4 (−7) | +9 | **82s** | ✅ (7s under cap) |

If a take lands over 85s: drop the S-16 glance first, then the S-15 glance, then the S-13 shot — in that
order (reverse of story value). Never cut the hook or shots 2–4.

### 2.6 — Cut = must-not-appear checklist

When a feature is cut, confirm **none** of these remain anywhere:
- [ ] No H-1 shot/row mentioning the feature (6A for S-13, the status phrase for S-15, the task badge for S-16).
- [ ] No rehearsal-checklist line for the feature.
- [ ] No `herd.yaml` capability, PR-description bullet or rule-13 line for the feature.
- [ ] No README line for the feature.
- [ ] Timings return to the combination table's "none"/applicable row.

---

## 3. H-2 — `herd.yaml` capability list + PR-description deltas

`herd.yaml` is the catalog entry added by H-3's PR to `NousResearch/hermes-agent`
(`plugin-catalog/herd.yaml`); the `capabilities:` block must equal what the freeze SHA registers
(**rule 6**). The current block on `origin/main` (`H-2` §1) is `provides_tools: [herd_list_channels,
herd_post, herd_read_channel]`, empty hooks/middleware/env.

### 3.1 — S-13  ·  **APPLY IF S-13 MERGED**  *(facts from @smith, branch `wt/s13-promote`)*
- **`capabilities:` — NO CHANGE.** Promote adds no tool; `herd_list_channels` already lists the new channel.
- **Write path (confirmed by Smith):** the desktop half calls a **local-only** backend route
  `POST /api/plugins/herd/channels/{channel_id}/promote` (pane → Herd's own backend, no network); the
  teammate's gateway is reached by the **same** `POST /herd/v1/sync` call already disclosed.
  **`PROTOCOL_VERSION` 1 → 2**; the message payload gains `origin_channel_id` so both gateways converge on
  the same rows. No new endpoint, host or credential.
- **PR description → "Hermes surfaces used":** add
  `- Promote a DM to a channel — a desktop action (local route `POST /api/plugins/herd/channels/{id}/promote`); the copy reaches the teammate over the existing `POST /herd/v1/sync` write path with a new channel-create + message-replay payload (`PROTOCOL_VERSION` 1 → 2; copied rows carry `origin_channel_id`).`
- **Checklist:** tick "protocol version bump (1 → 2) disclosed".
- **Protocol honesty (Sentry TC-10.11, merge gate):** state that the version is bumped **once** and is
  readable from `/herd/v1/ping` + `/status`; note (verify from the diff at freeze) what an old **v1**
  peer does with a v2 body — Smith has confirmed no 500/corruption. The disclosure line in §4 carries
  the "sync protocol v2" fact; do not let the version go undisclosed.

### 3.2 — S-15  ·  **APPLY IF S-15 MERGED**  *(facts from @smith, design pinned; PR not open yet)*
- **`capabilities.provides_tools`:** append **`herd_set_status`** — Smith: the exact name, no others
  (single argument `status`, a 5-value enum). Must match `plugin.yaml provides_tools` at the freeze SHA
  exactly (rule 6). **This is the 4th declared tool** — `herd.yaml` and `plugin.yaml` both go 3 → 4, and
  **Sentry TC-0.8: `catalog_audit.py` must show 4 tools, not 3.**
- **Confirmed none:** no new hook, no new middleware, no `requires_env` (the phrase needs no credential;
  nothing new stored as a secret).
- **PR description → "Hermes surfaces used":** the tool list gains `herd_set_status`; add
  `- Agent status: `herd_set_status` lets an agent set one coarse phrase (reading the code / writing the code / reviewing / done / idle) shown beside its in-flight work; per-message human/agent badges are rendered in the pane.`
- **Rule-13 (Sentry TC-11.8 makes this a merge gate).** Apply the line in §4 verbatim: local-only, in
  gateway memory only (D-5), no peer sync, no `herd.db` write, self-clears. Do **not** invent a network line.

### 3.3 — S-16  ·  **APPLY IF S-16 MERGED**
- **If Q-8 = NO (id-only):** `capabilities:` **NO CHANGE**. Add PR-description bullet
  `- Kanban link: an agent's answer can carry a task-id badge that opens that task on the herd board; the task id is passed explicitly by the agent and no Kanban data is read.`
- **If Q-8 = YES (DB read allowed):** a local-DB read is **not** a `capabilities:` key — rule 6's block
  covers tools/hooks/middleware/env only. It is a **rule-13** disclosure only (§4). Add the PR bullet
  `- Kanban link: an agent's answer carries a task-id + title badge, read from the local Kanban DB (read-only); opens that task on the herd board.` and apply Sentry's exact constraint wording from Q-8.
- **Checklist:** tick "S-16 disposition matches Q-8 ruling".

---

## 4. Rule-13 disclosures — **append to PR description AND `README.md` verbatim**

Rule 13 (*"Risky behaviour is disclosed"*) covers: network calls, reads outside the plugin's own data,
shell commands, long-running background processes, stored credentials. Append only the lines whose
feature merged; README and PR description must be **identical** (Q-3 CA-5).

**S-13 — apply if merged** *(text authored by @smith, branch `wt/s13-promote`; H-6 owns it; needs Sentry Q-7 sign-off)*:
> - **Sharing a DM to a channel.** "Share to a channel" on a DM asks this gateway to create a named channel and copy that DM's messages into it. It is a copy: the DM and its history are never modified or deleted. The copies are written to Herd's own SQLite file and reach your teammate's gateway through the same `POST <url>/herd/v1/sync` request already disclosed above, as part of the normal sync payload (Herd sync protocol v2 — copied rows now carry the source DM's id so both gateways converge on the same rows). No new endpoint, no new outbound host, no new credential, no shell command.

**S-15 — apply if merged** *(Sentry TC-11.8 gate: a rule-13 line for the status write path; text from @smith)*:
> - **Agent status:** an agent may set one short phrase about what it is doing (`herd_set_status`, from a fixed five-phrase vocabulary) which the pane shows beside its work. It lives in the gateway process's memory only — never written to `herd.db`, never sent to the teammate's gateway — and clears itself after five minutes or on gateway restart. No new network calls, no new stored credential, no shell commands.

**S-16 — apply if merged, Q-8 = YES** (this is a **reads-outside-own-data** disclosure — mandatory under rule 13):
> - **Reads outside plugin data:** to label an agent's answer, the Herd pane reads a task's title from the
>   local Kanban database at `~/.hermes/kanban/boards/<slug>/kanban.db` — **read-only**, never written, no
>   schema assumptions; if the file is missing or locked the pane shows the task id only.

**S-16 — apply if merged, Q-8 = NO** (no read; state it so reviewers don't suspect one):
> - **Kanban link:** links an agent's message to a Kanban task by the task id the agent passes explicitly;
>   opens the task in the Kanban view. Herd does not read the Kanban database.

Also update the README "What Herd does on your machine (disclosures)" heading area if any of the above
add a new disclosure category (S-16 Q-8 = YES adds a **reads outside plugin data** line where README
currently says "reads nothing outside its own data folder" — that line must change, not coexist).

---

## 5. What H-6 needs from @smith (capability list) — **blocks H-2 final**

Please answer in a comment on `S-13`/`S-15`/`S-16` (or on `H-6`):

1. **S-15** — ✅ **ANSWERED** (Smith, Nov 6): tool **`herd_set_status`** (exact, no others; single arg
   `status`, 5-value enum); it is an **agent tool** registered via `ctx.register_tool(...)` in
   `__init__.py::register()` ⇒ 4th entry in **both** `plugin.yaml provides_tools` and
   `herd.yaml capabilities.provides_tools`; no new hook/middleware/`requires_env`; **local-only** (D-5,
   in gateway memory). Disclosure text staged in §3.2/§4. Reviewer-facing correction: any H-2/README copy
   that says "three agent tools" moves to **four** — **only if S-15 is merged at freeze** (S-15 is cut #2).
2. **S-13** — ✅ **ANSWERED** (Smith, Nov 6): no new tool; `PROTOCOL_VERSION` **1 → 2**; same
   `POST /herd/v1/sync` endpoint (new local-only backend route
   `POST /api/plugins/herd/channels/{id}/promote`; payload gains `origin_channel_id`; copies never
   wake an agent). Disclosure text staged in §4, awaiting Sentry Q-7.
3. **S-16** — pending Q-8: if id-only, confirm **no** capability/declaration change; if DB-read is ruled
   allowed, the exact path + read-only guarantee Sentry requires.

---

## 6. Open items

- [x] @smith: **S-13** disclosure text received → staged in §3.1/§4 (needs Sentry Q-7 sign-off).
- [x] @smith: **S-15** capability list received (`herd_set_status`, agent tool, 4th entry, local-only) → staged in §2.2/§3.2/§4.
- [ ] @smith: **S-16** disposition — the last piece that **blocks H-2 final** (§5 item 3).
- [ ] @sentry: Q-8 ruling on `kanban.db` — decides the S-16 lines in §3.3/§4.
- [ ] PR #25 (H-5 beats) and PR #27 (constants) must merge **before** the H-1 deltas in §2 apply.
- [ ] At freeze: run §1, then Sentry Q-3 re-audit at the freeze SHA (F-3 C3/C5).
