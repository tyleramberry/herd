# Q-9 / Q-10 — SPINE run log (two real Macs)

Owner: @sentry · Opened Nov 6, 2026 · Status: **RECORDED, NOT INDEPENDENTLY VERIFIED BY QA**

## Attestation (read this first)

QA did not run this test and did not observe it. The only evidence on record is:

- `docs/TASKBOARD.md` (Q-9, S-2) and `docs/pm/2026-11-06-status.md`: Foreman closed the
  verification card `t_4e0473ee` at 09:07 MST on Nov 6, "signed off on Tyler's first-hand
  confirmation": Tyler's Mac and Brooklyn's Mac exchanged messages in both directions.
- Foreman's cross-check on main `e967130`: pytest 125 passed / 3 skipped, `node --check`
  OK, `hermes plugins validate` pass, `doctor --ci` clean (3 tools, 0 hooks),
  `catalog_audit` 0 FAIL / 1 known WARN. QA re-ran tests + audit on main (`9d9c6e7`):
  135 passed, 0 FAIL, node OK.

So SPINE is **accepted on Tyler's word**, which is a legitimate sign-off for this project,
but this file is not a QA attestation until the rows below carry evidence. Rows marked
`—` are unknown, not passed. Do not cite this file as proof of TC-2 to Nous reviewers
until they are filled.

## Run record

| Field | Value |
|---|---|
| Date / time | Nov 6, 2026, before 09:07 MST (exact time: —) |
| Who ran it | Tyler (first-hand, per Foreman). Brooklyn operated the second Mac (—: confirm) |
| Topology | Two machines: Tyler's Mac, Brooklyn's Mac (same LAN: —) |
| Hermes version, A / B | — / — (`hermes --version`) |
| Plugin SHA, A / B | — / — (`hermes plugins list --json`, recorded sha) |
| Fix in play | #26 (33342b9): sync loop carries the profile secret scope |

| TC | What | Result | Evidence |
|---|---|---|---|
| ENV-1 | same plugin commit both sides | — | SHA per side (above) |
| TC-2.1 | A→B human message, no reload | PASS (reported) | Tyler, via Foreman card t_4e0473ee |
| TC-2.2 | B→A human message, no reload | PASS (reported) | same |
| TC-2.3 | agent on A posts → human on B sees | — | not reported |
| TC-2.4 | 3 quick messages arrive in order | — | not reported |
| TC-2.5 | refresh without sockets (poll fallback) | — | not reported |
| TC-2.6 | restart B desktop → history intact | — | not reported |
| TC-2.7 | duplicate delivery → one row | — | covered by unit tests only |
| TC-0.1/0.2 | `validate` / `doctor --ci` on the device | — | Foreman ran them in a sandbox, not on Tyler's Mac |
| TC-10.4 | S-13 promote on two real gateways | — | not yet run |
| TC-4 live | @mention wake on real Hermes | — | not yet run |

Foreman's note that the #26 symptom (`last_error` back seconds after a success) did not
recur is also unverified by QA until the `peer_state` rows below exist.

## What closes Q-10 (about 5 minutes, per Mac)

Run these on **each** Mac and paste the output into this file or send it to QA:

```bash
hermes --version
hermes plugins list --json | grep -A4 '"herd"'          # recorded sha
hermes plugins doctor herd
sqlite3 "$HERMES_HOME/plugin-data/herd/herd.db" \
  "select url, push_seq, pull_seq, last_ok, last_error from peer_state;"
```

(`HERMES_HOME` defaults to `~/.hermes`. If `sqlite3` is missing, skip that line and
send a screenshot of the Herd pane header showing "Connected to <name>".)

Then, if time allows, one pass of TC-2.3 (agent posts a task, other human sees it) and
TC-2.6 (restart one desktop app, history is still there). Those are the two demo-critical
rows nobody has reported.

## Sign-off rule

QA will change the status line to **PASSED (verified)** only when ENV-1, TC-2.1/2.2 and
the `peer_state` rows are filled in with real output. Until then the status above stands.
