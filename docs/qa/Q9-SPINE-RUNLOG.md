# Q-9 — SPINE two-gateway run log (F-3 gate A6 evidence)

**Card:** Q-10 (`t_24c1ee89`) · artifact for Q-1 §8 and F-3 freeze-gate item **A6**
("SPINE demonstrated: message on gateway A appears on gateway B, Q-1 TC-2.1/2.2 signed by Sentry").
**Recorded by:** Sentry (QA gate) — **2026-11-06, 09:10–09:20 MST**.
**Nature of this document:** this is a **recording of someone else's run**, corroborated against
gateway A's persisted state. It is **not** a run Sentry performed or witnessed. See §5.

---

## 0. Verdict summary (read this first)

| Question | Answer |
|---|---|
| Did a real two-Mac message exchange happen? | **YES** — first-hand confirmation by Tyler (desktop, 2026-11-06 08:58 MST) + A-side message artifacts. |
| TC-2.2 B→A (direction Brooklyn posts → Tyler sees) | **PASS** — B-authored rows persisted on A (see §2). |
| TC-2.1 A→B (direction Tyler posts → Brooklyn sees) | **PASS (indirect)** — A's push cursor only advances on a successful peer round-trip (see §2). |
| Three consecutive round-trips (Q-9 requirement) | **NOT COVERED** — never captured (§3). |
| Did the window exercise the **freeze build**? | **NO** — the live gateway ran plugin SHA `5d4b3e4`, **28 commits behind** `origin/main` and **predating PR #26** (§1). |
| **F-3 A6 satisfiable from this log alone?** | **NO.** The exchange is real, but A6 as worded ("on the freeze build", TC-2.1/2.2 signed) must cite the **Q-4 run on the frozen SHA**, not this window. |

**One-line QA statement to @projectmanager:** the two-Mac SPINE exchange is real and confirmed by
Tyler, but the live window ran a pre-#26 build (`5d4b3e4`) and captured no per-direction primary
evidence; A6 should be closed by the Nov 9 Q-4 rehearsal on the frozen SHA, with this log attached
as corroboration, not as the gate evidence.

---

## 1. Run header

### 1.1 Topology
Two machines, the demo topology (Q-1 §2 "two machines"):

| Role | Machine | gateway_id | Hermes API server | Reachable from A at record time |
|---|---|---|---|---|
| **A** | `Tylers-MacBook-Air-104` (Tyler's Mac) | `fa0d66ffb0524d6aae4e8e2125eb8cce` | `0.0.0.0:8642` | n/a (local) — `/herd/v1/ping` → **401** (route mounted, auth enforced) |
| **B** | `Brooklyns-MacBook-Pro-3.local` (192.168.4.40) | `d05d074d7161400daeb8697def1fe735` | `:8642` | **NO** — ICMP ping OK, TCP `:8642` connect **timed out** (IPv4 + IPv6) |

Evidence for the identity/gateway_id pair: A's `herd.db` `meta` row (`gateway_id=fa0d66ff…`),
A's `participants` table (`fa0d66ff…` → "Tyler"; `d05d074d…` → "Brooklyn"), and A's `peer_state`
row `remote_gateway_id=d05d074d…` recorded from B's `/herd/v1/sync` response. Both sides run the
same `herd` plugin.

### 1.2 Plugin SHA per side

| Side | SHA | How read | Note |
|---|---|---|---|
| **A** | **`5d4b3e4`** | `git -C ~/.hermes/plugins/herd rev-parse HEAD` (first-hand, 2026-11-06 09:12 MST) | `Herald: set catalog entry requires_hermes to >=0.22.0 (#11)`, 2026-11-05 10:22 MST. Working tree **clean**. |
| **B** | **NOT EVIDENCED** | — | Brooklyn's machine could not be read (gateway unreachable; no remote access). |

Install method (A side, first-hand):
- Plugin is a **linked local checkout**: `~/.hermes/plugins/herd → /Users/tyleramberry/src/herd`
  (`hermes plugins install` on the local path; desktop half `~/.hermes/desktop-plugins/herd`
  sources `…/plugins/herd/desktop`, `"linked": true`, `repo: https://github.com/tyleramberry/herd.git`).
- Data: `<HERMES_HOME>/plugin-data/herd/herd.db` (SQLite/WAL), gateway A.

### 1.3 Hermes version (A side)
`Hermes Agent v0.23.0+120.g57cc40f (2026.9.24) · stable · local 57cc40f4699f`, install method **git**
(`hermes --version`). B-side version: **NOT EVIDENCED**.

### 1.4 Live window (UTC in the DB → MST)

| Local (MST) | Event |
|---|---|
| 2026-11-05 10:34 | gateway restarted; seeded `general` (agent hello, seq 1) |
| 2026-11-05 16:45:37 | A: Tyler posts "Hi brooklyn" (seq 4) |
| 2026-11-05 16:45:45 | B: Brooklyn posts "Hi Tyler," (seq 5) — **+8.4 s after A's post** |
| 2026-11-05 16:46:45 / 16:47:00 | A long message (seq 6) → B "Your name: Brooklyn / Gateway: …" (seq 7) — **+15.5 s** |
| 2026-11-05 16:58:42 | agent (smith) posts "SPINE TC-2.1 verification by agent smith" (seq 9) |
| 2026-11-05 17:07:33 / 17:07:43 | A "yo" (seq 18) → B "yo" (seq 19) — **+10.6 s** |
| 2026-11-06 08:31:41 | A: Tyler posts "@Brooklyn'shermes" (seq 21) |
| 2026-11-06 08:58:06 | **Tyler confirms the exchange on Q-9** (desktop comment) |
| 2026-11-06 09:00:44 | last **successful** peer sync on A (`peer_state.last_ok`) |

---

## 2. TC-2.1 / TC-2.2 rows

Evidence source for both rows: gateway A's SQLite snapshot, copied WAL-safe to
`~/.hermes/profiles/sentry/cache/scratch/…/evid/herd.db` on 2026-11-06 09:09 MST
(`sqlite3 -readonly` on a live WAL db fails; the copy is the standard snapshot method).

**TC-2.2 — B→A. `PASS`.**
- *Action:* Brooklyn posts on gateway B; the message must appear on gateway A without a reload.
- *Observed:* rows **authored on B are persisted in A's database**, attributed to B's gateway:
  - seq 5 · `author_name=Brooklyns-MacBook-Pro-3` · `Hi Tyler,` · 2026-11-05 16:45:45 MST
  - seq 7 · `author_name=Brooklyns-MacBook-Pro-3` · `Your name: Brooklyn / Gateway: http://Broo…` · 16:47:00 MST
  - seq 19 · `author_name=Brooklyn` · `yo` · 17:07:43 MST
- *Evidence pointer:* `evid/herd.db` → `SELECT … FROM messages WHERE gateway_name LIKE 'Brooklyn%'`.
  A only ever learns these rows by ingesting B's `/herd/v1/sync` export, so their presence on A is
  direct proof that B→A relay delivered. **First-hand, from A's own store.**

**TC-2.1 — A→B. `PASS (indirect; no B-side primary evidence)`.**
- *Action:* Tyler posts on gateway A; the message must appear on gateway B.
- *Observed (A-side artifacts):*
  1. **Push cursor only advances on a successful peer round-trip.** In `herd_store.sync_peer`,
     `peer_state.push_seq` (and `last_ok`) is written **only after** the `transport(peer, …)` HTTP call
     returns. A's row shows `push_seq = 21`, i.e. A completed a round-trip in which it exported its
     messages through **seq 21** (the 2026-11-06 "@Brooklyn'shermes" post) at `last_ok = 09:00:44 MST`.
  2. **Stimulus/response cadence:** B answered each A post from 8.4–15.5 s later (seq 4→5, 6→7, 18→19),
     which requires B to have received the A posts.
- *Evidence pointer:* `evid/herd.db` → `peer_state` row (`push_seq`, `last_ok`) + the seq pairs above.
- *Gap:* there is **no capture on B** (no B-side DB row dump, screenshot, or terminal output) showing
  A's message rendered on B. A6's wording ("appears on gateway B") is therefore satisfied by A-side
  cursors + timing, not by direct B-side observation.

**TC-2.3 (agent→other gateway)** was partially touched (seq 9, "SPINE TC-2.1 verification by agent
smith", 2026-11-05 16:58:42 MST) but **NOT EVIDENCED** as a delivered cross-gateway agent post.

---

## 3. Three-consecutive-times evidence (Q-9 explicit requirement)

**NOT COVERED.**

Q-9 asked for the exchange "three consecutive times, not once". The window contains at most **two clean
bidirectional round trips** on 2026-11-05 evening (`Hi brooklyn`/`Hi Tyler,` and `yo`/`yo`) plus one
long-message exchange; there is **no capture of three consecutive A→B-and-back pairs**, and no
timestamps were recorded at the time by an observer.

*Reachable re-run attempted (2026-11-06 09:10–09:12 MST):* the live two-machine re-run **could not be
performed** — Brooklyn's gateway (`Brooklyns-MacBook-Pro-3.local:8642`) accepted **no TCP connection**
from A (curl timed out on every resolved IPv4/IPv6 address, ~12 s). Brooklyn's Mac itself is on the LAN
(ICMP ping OK, ARP entry present), so this is the peer's Hermes API server being down/closed, not a
missing machine.

**Required follow-up:** the three-consecutive live run belongs in **Q-4 (clean-install rehearsal,
Nov 9)** against the **frozen SHA**, on both machines. See §8.

---

## 4. `peer_state` evidence (last_ok / last_error, and the #26 symptom)

Raw row (A side, snapshot 2026-11-06 09:09:51 MST):

| url | name | push_seq | pull_seq | remote_gateway_id | remote_name | last_attempt | last_ok | last_error |
|---|---|---|---|---|---|---|---|---|
| `http://Brooklyns-MacBook-Pro-3.local:8642` | Brooklyn | 21 | 18 | `d05d074d7161400daeb8697def1fe735` | Brooklyn | `2026-11-06T16:09:51.178+00:00` (09:09:51 MST) | `2026-11-06T16:00:44.882+00:00` (09:00:44 MST) | `No key set for this peer.` |

**PR #26 symptom check — REPRODUCED on the live build.**
- `last_attempt` advances right up to "now" (the 3 s background loop is alive), but `last_ok` is
  **~9 minutes stale** and `last_error` is **non-empty**. That is the exact pre-#26 signature
  (PR #26's own message: an `UnscopedSecretError` written to `last_error` **every 3 s**, with all real
  syncing riding only the request kicker / desktop backstop).
- `status()` reads `connected = bool(last_ok) and not last_error` → the desktop header would show
  "Can't reach" for this peer despite the historical successes.
- Causally: the live build's `__init__.py::_start_sync_loop` calls `store.sync_all` **without** a
  bound profile secret scope (the `_sync_pass` wrapper that PR #26 added is absent); the loop's
  `peer.get("key")` is empty → `PermissionError` → `"No key set for this peer."`.
- **Consequence:** the Nov 6 window did **not** validate PR #26 — it ran *before* it, and exhibits the
  very bug #26 fixes. This is the reason A6 needs the Q-4 run.

Minor anomaly for Q-4 to confirm (not asserted as a defect): `pull_seq = 18` while the newest
B-authored row on A is **seq 19** — worth checking whether the pull cursor regressed (e.g. B-side DB
reset / `next_seq` semantics) once the peer is reachable.

---

### 4b. Corroborating record carried on `main` (merged via #39)

These facts were recorded on `main`'s attestation and are folded in here so the merged
document is the single run-log of record (the two versions differed only in detail, not in
conclusion):

- Card `t_4e0473ee` (Q-9 / S-2) was closed **2026-11-06 09:07 MST** on **Tyler's first-hand
  confirmation** that his Mac and Brooklyn's Mac exchanged messages in both directions
  (per `docs/TASKBOARD.md` Q-9/S-2 and `docs/pm/2026-11-06-status.md`).
- Cross-check on `main` `e967130`: `pytest` **125 passed / 3 skipped**, `node --check` OK,
  `hermes plugins validate` pass, `doctor --ci` clean (**3 tools, 0 hooks**),
  `catalog_audit` **0 FAIL / 1 known WARN** (the pre-existing `herd_store.py`
  `hermes_cli.urllib_security` import).
- QA re-run on `main` `9d9c6e7`: **135 passed, 0 FAIL**, `node --check` OK (QA lead, own run).
  Additional QA run at `main` `46f2343` (after #36): **137 passed, 0 FAIL**.
- Note on the "3 skipped": those are the `skipUnless(find_spec("fastapi"))` guards on the HTTP-surface
  tests. Measured by QA at `46f2343`: venv with pytest+PyYAML only → **134 passed / 3 skipped**;
  same venv + FastAPI → **137 passed / 0 skipped**. So the count differences between runs track
  the presence of FastAPI, not test loss.

---

## 5. Attestation (first-hand, explicit)

- **Observed first-hand by: Tyler** — via the Hermes desktop app — who posted on Q-9 (`t_4e0473ee`)
  at **2026-11-06 08:58:06 MST**: *"This is done. Tyler confirms that it worked."* (platform: desktop).
- **Recorded by: Sentry (QA).** Sentry **did not perform and did not witness** the two-Mac run. What
  Sentry did first-hand, on 2026-11-06 09:10–09:20 MST, is: read gateway A's live plugin SHA, snapshot
  A's `herd.db`, and verify the B-authored rows, `peer_state`, and the reachability of B.
- Therefore every "PASS" above rests on **(a)** Tyler's first-hand confirmation, and **(b)** A-side
  artifacts that Sentry read directly. **There is no Sentry-observed live run behind this log.**

---

## 6. Reachable re-run Sentry did perform (code-level, not live HTTP)

At `origin/main` **`941e975`** ("Foreman: SPINE PASSED (Q-9) … (#39)"), fresh clones in Sentry's
scratch, both directory-name variants (the mandatory pytest dirname trap):

| Gate | Hyphenated clone `qa-q10` | Identifier clone `qa_q10` |
|---|---|---|
| `python -m pytest tests/ -q` | **137 passed**, 1 warning | **137 passed**, 1 warning |
| `node --check desktop/plugin.js` | OK | — |

These exercise the two-gateway sync **in-process** (`TRANSPORT` shim + JSON round-trip); they are
**not** a live two-machine exchange and do not substitute for §3.

Foreman's code-level cross-check at `f420eeb` (pytest 84 passed, `node --check` OK, `plugins validate`
pass with 1 known rule-9 warning `herd_store.py urllib_security`, `doctor --ci` clean, 3 tools / 0 hooks)
is **reported by Foreman, not re-run by Sentry** here; the counts differ only because more PRs merged
between `f420eeb` and `941e975`.

---

## 7. Gaps — NOT EVIDENCED

1. **B-side plugin SHA / Hermes version / install method** — cannot read Brooklyn's machine; peer
   gateway unreachable.
2. **Per-direction primary evidence** — no screenshot or terminal capture of B's channel view exists
   in `docs/qa/` or on gateway A for either direction; TC-2.1 rests on A-side cursors + timing.
3. **Three consecutive round-trips** — NOT COVERED (§3).
4. **Wrong build exercised** — the live window ran `5d4b3e4` (pre-#26); it did not exercise #26.
5. **TC-2.3 agent→other-gateway delivery** — not evidenced.

---

## 8. Sign-off

- **TC-2.1 (A→B): PASS (indirect / A-side artifact)** — Sentry, 2026-11-06 09:20 MST.
- **TC-2.2 (B→A): PASS (A-side artifact)** — Sentry, 2026-11-06 09:20 MST.
- **Three consecutive: NOT COVERED** — Sentry, 2026-11-06 09:20 MST.
- **F-3 A6:** **NOT to be closed from this log.** The exchange is real, but A6 requires the frozen
  build; and the live build is 28 commits behind with the #26 fix absent. A6 is to be closed by the
  **Q-4 clean-install rehearsal (Nov 9)** running the two-gateway smoke test on the frozen SHA,
  which must include the **three consecutive** round-trips and a per-side SHA capture.

**Sentry — QA gate — 2026-11-06 09:20 MST**
