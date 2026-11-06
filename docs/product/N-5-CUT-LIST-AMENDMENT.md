# N-5 — Cut-List Amendment (Tyler's Nov 6 directive)

Owner: @foreman (recording Tyler's decision) · Date: Fri Nov 6, 2026 · Applies through submission (Nov 11, 5:00 PM EST)
Amends **N-1** (docs/product/N-1-CUT-LIST.md). N-1 says "Changing this list needs Tyler's OK in writing."
Tyler's Nov 6 directive *is* that written OK. This file is the record.

**The Nov 8 code freeze stands.** Nothing here may push it.

---

## 1. New IN (must be merged by Sun Nov 8 freeze)

Priority order below is Tyler's, verbatim from the directive.

### F1 — Promote a private DM into a shared room  ·  board `S-13`  ·  owner Smith  ·  QA `Q-7`
Closes the known gap: today a DM is the *only* private space and there is no way to
deliberately make a thread shared.

**Done means**
- From an open DM, a human has one action — **Share to a channel** — that creates a named
  shared channel and replays that DM's messages into it, in order.
- The new channel appears in **both** gateways' channel lists within one sync cycle, with
  both participants present.
- The DM itself is untouched (promote **copies**; it never deletes history). Demo safety: if
  promote misbehaves, the DM is still there.
- `herd_list_channels` (agent view) shows the promoted channel, so an agent can be pointed at it.

**Catalog impact** new sync payload (channel create + message replay) → `PROTOCOL_VERSION` bump; rule-13
disclosure of the new write path. Owner of that text: Herald (H-6), signed off by Sentry.
**Estimate** 4 h build + 1.5 h QA.

### F2 — Assignment context on @mention wake  ·  board `S-14`  ·  owner Smith  ·  QA `Q-7` (extend TC-4)
Bridges the gap past bare @mention wake: the woken agent currently just receives a dumped chat
message. It must receive an assignment.

**Done means** the injected wake text states, in plain language,
(a) **who** asked (human name + which channel), (b) **what** is expected (the mention text),
(c) **where to report back** (channel ref + the `herd_post` call to use).
**Every existing guard is unchanged**: mentions only · one wake per message · agent-authored
messages never wake · default off · still requires `allow_gateway_injection`.
**Estimate** 3 h build + 1 h QA. *(Smallest and highest story-value item — never cut.)*

### F3 — Live supervision status line + speaker badge  ·  board `S-15`  ·  owner Smith  ·  QA `Q-7`
**Done means**
- The Herd pane shows one **short plain-English phrase** beside an agent's in-flight work, from a
  fixed vocabulary: `reading the code` · `writing the code` · `reviewing` · `done` · `idle`.
- Every message carries a **human/agent badge** in the pane.
- **No tool-by-tool activity stream.** One phrase, that is all.
- Rides the plumbing that already exists: the plugin event broadcast
  (`broadcast_plugin_event`) plus the 3 s sync poll. No new transport.
- No status set ⇒ the pane shows **nothing**, never a guessed or stale phrase.

**Catalog impact** new agent tool (status) → `plugin.yaml provides_tools` + `herd.yaml` capability
+ rule-13. Sentry re-audits.
**Estimate** 6 h build + 2 h QA.

### F4 — Agent response links to the Kanban board  ·  board `S-16`  ·  owner Smith  ·  QA `Q-8` (ruling first)
**Done means** when an agent posts an answer in a Herd channel that is tied to a Kanban task, the
message in the pane shows a link/badge with the **task id + title**, and acting on it opens that
task on the `herd` board. The tie is **explicit** (the agent passes the task id) — never guessed
from message text.

**BLOCKING RULING — do not start until Sentry answers (Q-8):** may a catalog plugin read
`~/.hermes/kanban/boards/<slug>/kanban.db`? If **no**, F4 still ships, but as **id-only** (no
title fetched from the DB), opened through the Kanban view. Sentry's call, in writing, before a
line of code.
**Catalog impact** possibly a new declared capability; rule-13.
**Estimate** 6 h build + 2 h QA. **Riskiest item — first to be cut.** (See §3.)

---

## 2. DO NOT BUILD (Tyler, Nov 6 — "wait", "not yet")

| Directive # | Item | Disposition |
|---|---|---|
| #1 | Identities & permissions | **Not built.** Parked, no design work, no branch. |
| #6 | Concurrency safety hardening | **Not built.** Parked. |

Both are post-hackathon backlog entries as of today. No branches may be opened for them.

---

## 3. Cut order (if the clock runs out before Sun Nov 8)

Tyler's directive is already ordered 1 → 2 → 4 → 5, so the cut falls in reverse, last-first:

1. **F4 (S-16) is cut first** if it is not merged by **Sat Nov 7, 12:00** — it is the biggest
   integration and depends on a catalogue ruling that does not exist yet.
2. **F3 (S-15) is cut second** if it is not merged by **Sat Nov 7, 18:00**.
3. **F1 (S-13)** and **F2 (S-14)** are not cut. If either is at risk on Sun morning, we are in
   trouble and Foreman escalates to Tyler rather than deciding alone.

Anything cut goes to the post-hackathon backlog and out of the demo script the same hour it is cut.

---

## 4. Risks added by this amendment

- **R-4 — F4's Kanban read may be disallowed by catalog rules.** Mitigation: Sentry ruling Q-8
  *before* build; id-only fallback defined above. Owner: Sentry.
- **R-5 — F1 changes the sync payload on the critical path.** A protocol change this late can
  break the two-gateway SPINE. Mitigation: F1 lands **behind** the 3 s poll and must pass TC-2
  (two-gateway) before merge, not just unit tests. Owner: Smith, verified by Sentry.
- **R-6 — Four new features against a 2.5-day clock.** Engineer capacity Fri 09:00 → Sun 17:00 is
  ~20 h of build time, and S-9/S-11/S-12 (PRs #19/#23/#24) still need QA + merge on the same clock.
  Mitigation: the cut order in §3, decided on Saturday at noon, not Sunday night.
- **R-7 — SPINE is not verified and is the real critical path.** (Pre-existing; see the Nov 6
  report.) No new feature may consume the hardware window that SPINE needs.
