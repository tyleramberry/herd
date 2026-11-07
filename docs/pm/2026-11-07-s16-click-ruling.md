# PM ruling — S-16 task badge: board-level navigation, accepted (Nov 7, 2026)

Owner: **Foreman** (PM) · Raised by: **Sentry** in the S-16 QA review (`t_e7741438`, approve verdict)
· Card: `t_f0d1f45a` · Build of record: `origin/main` @ `f430152`

## Decision

**ACCEPT board-level navigation for the freeze build and the demo. S-16 ships unchanged.** No code
change to PR #46 for the click target. The per-task deep link is **filed post-hackathon** (N-1 OUT
list) — it is out-of-repo work in core / the Kanban plugin, and it is not worth a hackathon-day
workaround.

**DONE MEANS (F4), as amended by this ruling:** when an agent posts an answer tied to a Kanban task,
the message carries a task-id (+ title) badge; acting on it **opens the `herd` board that holds the
task**. The individual card is **not** focused — see the platform evidence below. The N-5 F4
id-only branch already anticipated view-level opening ("opened through the Kanban view"); this ruling
makes the same allowance for the DB-read branch and states it explicitly instead of leaving it
implied.

### Why accept (not fight it)

1. **It is the core contract, not an S-16 shortcut.** A contributed route is one segment with no
   params; no per-task route exists for a plugin to call.
2. **Core parity.** The Kanban plugin's own completion notification ships the identical call
   (`host.navigate('/kanban')`). A judge comparing our badge to core's toast sees the same behaviour,
   so nothing reads as broken or half-built.
3. **The demo beat stays real.** One click lands the user on the board that contains the work. The
   line "Every answer points back at the work." is still true.
4. **The only workaround is forbidden and would cost more than it buys.** DOM-poking the card open is
   blocked by desktop lint and reads as a hack under the *polish* / *reliability* criteria.
5. **The clock.** N-5 §cut order makes F4 cut #1 if not merged by **Sat Nov 7 12:00**; the alternative
   to accepting is losing an approved Tyler directive for a cosmetic difference.

## Independent verification (Foreman — not taken from the QA note)

Core `~/.hermes/hermes-agent` @ `efbc7f7dba5` (clean tree, parent commit
`fix(update): an unavailable config backend fails one launch file…`, 2026-11-07), re-checked myself:

| File | Line | What it says |
|---|---|---|
| `apps/desktop/src/app/routes.ts` | 92 | `/** Absolute path, e.g. `/kanban`. One segment; no params. */` |
| `apps/desktop/src/app/routes.ts` | 119–121 | `isContributedPath(pathname)` → `some(route => route.path === pathname)` (exact match) |
| `apps/desktop/src/app/routes.ts` | 194–198 | `routePathname()` cuts at the first `?`/`#` — a query never reaches a contributed page |
| `apps/desktop/src/app/chat/route-tile.tsx` | 57–64 | `RouteTilePane({ path })`; the page is resolved with `r.path === path`; only `path` is passed in |
| `apps/desktop/src/plugins/kanban/board.tsx` | 1120 | the pane's `search` is React state; grep for `location.search` / `location.hash` / `URLSearchParams` across `plugins/kanban/` finds only REST param building (`api.ts:141`, `api.ts:400`) |
| `apps/desktop/src/plugins/kanban/completion-notify.ts` | 171 | core's own completion toast: `onClick: () => host.navigate('/kanban')` |

⇒ **No supported per-task deep link exists for a contributed route.** Confirmed independently of
Sentry's write-up.

## Review copy that must change (Herald, H-6 freeze pass)

The shipped artifacts are already accurate — PR #46's README rule-13 line and PR body both say
"clicking the badge **opens the Kanban board**", and PR #46's own QA note states the limitation. Two
**staged** lines in `docs/submission/H-6-new-scope-surfaces.md` over-claim the card focus and must be
downgraded when Herald applies them at freeze (H-6 "THE ONE RULE" still governs):

- **H-6 §2.3** (line 101) — `Tyler clicks it → the `herd` board opens on that task.`
  → `Tyler clicks it → the `herd` board opens (board-level: the badge carries the task id; the card itself is not focused).`
- **H-6 §3.3** (line 189) — PR bullet `…opens that task on the herd board.`
  → `…opens the herd board.`

Also due at freeze, unchanged by this ruling: **H-2** `docs/submission/H-2-catalog-pr-package.md`
line 105 still reads `Reads outside plugin data: none.` with the in-file placeholder — Herald replaces
it with the §4 read line once S-16 is merged; Sentry re-audits. No `herd.yaml` capability change is
due (a DB read is not a capability key — rule 6 covers tools/hooks/middleware/env only); `doctor --ci`
still reports 4 tools.

## Landing action and clock

N-5 §cut order: **F4 (S-16) is cut first if it is not merged by Sat Nov 7 12:00.** At this ruling PR
#46 @ `35debd89` is QA-approved (round 1, no S1/S2/S3 defects) and GitHub reports
`mergeable: MERGEABLE`, `mergeStateStatus: CLEAN` (checked at `origin/main` @ `f430152`). Landing is
routed to Smith as a child of `t_f0d1f45a`, with the rule-7 post-merge check spelled out: after the
squash merge, `task_link` must be present in `dashboard/kanban_tasks.py` and `TaskBadge` in
`desktop/plugin.js` **on `origin/main`**, and `hermes plugins doctor --ci` must still show 4 tools.

If the merge does not land by 12:00, S-16 is cut from the demo script per H-6 §2.3/§2.5 and N-5 —
that is the pre-agreed consequence, not a new decision.

## Post-hackathon backlog (filed, out of repo)

**Per-task Kanban deep link** — a supported route or param so a plugin can focus one card from a
message badge (e.g. core honouring something like `/kanban?task=<id>` in `RouteTilePane`/`board.tsx`
and relaxing the "one segment; no params" contract, or the Kanban plugin exposing a task-focus API).
Recorded in `docs/product/N-1-CUT-LIST.md` → **OUT (post-hackathon backlog, do not build before
Nov 11)**. No board card was created on purpose: this is out-of-repo work that cannot be executed in
this repo before the deadline, and an unassigned card would only be re-triaged.

## Nothing here needs Tyler's approval

F4 is an already-approved Tyler directive (Nov 5, N-5 §1) and this ruling stays inside its scope: it
accepts a platform limitation and corrects copy, and it defers rather than adds. Reported to Tyler as
one line in the daily update.
