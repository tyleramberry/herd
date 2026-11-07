# Q-4 / Q-11 — Clean-install rehearsal run log

**Runner:** Sentry (QA gate) · **Ran:** 2026-11-07, ~13:53–14:06 MST (dry run) and ~14:01–14:07 (certification run)
**Verdict:** **PASS on every leg except F-3 A2** (blocked by an undeclared dev dependency, not by product code).
**Certified SHA:** `b69a9d03e99441c165d797ee60fa067fca00e1f9` (`origin/main` at run time) — installed and verified by `git rev-parse` in both installed checkouts.

> Per Tyler's revised F-3 (no freeze), this run certifies the SHA that was current when it ran.
> It must be **re-run after any later merge that touches sync** (the no-freeze rule).

## 0. What was rehearsed

Exactly the judge path, on one machine, two isolated homes, outside the live Hermes root:

- Root: `~/herd-rehearsal-1107b/{a,b}` (deliberately **not** under `~/.hermes` — a "fresh" home nested
  inside the live root inherits the live `.env` and `desktop-plugins/`).
- Install: `HERMES_HOME=<home> hermes plugins install tyleramberry/herd --ref <40-hex> --no-enable`,
  then `hermes plugins enable herd`.
- Topology: two live gateways on distinct ports (`127.0.0.1:8742` = A/Tyler, `127.0.0.1:8743` = B/Riley),
  each with its own `API_SERVER_KEY`, each configured with the other's URL and key
  (`plugins.entries.herd.settings.{display_name,peer_name,peer_url}` + `.env HERD_PEER_KEY`).

## 1. Clean install + registration

| Check | A | B |
|---|---|---|
| Installed HEAD == pinned SHA | ✅ `b69a9d0…` | ✅ `b69a9d0…` |
| Installer output | `✓ Installed`, `Warning: custom (unreviewed) source` | same |
| `plugins doctor herd --ci` | ✅ OK, **4 tools / 0 hooks** | ✅ OK, **4 tools / 0 hooks** |
| `plugins validate .` (installed copy) | ✅ Validation passed | — |
| `catalog_audit.py` | ✅ **0 FAIL / 0 WARN** | — |

The "custom (unreviewed) source" warning is expected until the catalog PR (H-3) opens; a judge
installing from the submitted catalog entry would not see it. Disclosed, not a defect.

## 2. Two-gateway SPINE (the product)

| Leg | Result |
|---|---|
| Both peer routes mounted + auth enforced (`/herd/v1/ping`) | ✅ `200` with the key, `401` without, on both |
| Bidirectional sync established | ✅ each side's `peer_state.last_ok` advancing, `last_error` **empty**, other side's `remote_gateway_id` populated |
| **Three consecutive round-trips A→B** | ✅ all 3 rows on B, same ids |
| **Three consecutive round-trips B→A** | ✅ all 3 rows on A, same ids |
| Convergence after all six | ✅ **6/6 messages on both sides**, `push=6 pull=6`, `err=<none>` |
| **Restart keeps history** (TC-2.6 substance) | ✅ stopped and restarted both gateways (no reinstall): 6 messages kept, `gateway_id` stable (`4b031c32…` / `f09f7f09…`), cursors preserved |
| Sync resumes after restart | ✅ new post after restart crossed A→B |
| Security: redirect probe on the installed artifact | ✅ `tests/test_peer_redirect_security.py` **3/3 passed** (302 never re-sent with the bearer key) |

No `"No key set for this peer."` error appeared in any run — the #26 scope fix holds in a clean install.

## 3. F-3 A2 — **BLOCKED** (undeclared dev dependency)

`python -m pytest tests/ -q` (the README's own verify block) in a venv built from a bare install line
(`pytest fastapi httpx`):

```
2 failed, 185 passed, 35 subtests passed
FAILED tests/test_package.py::ManifestTest::test_manifest_fields      - ModuleNotFoundError: No module named 'yaml'
FAILED tests/test_package.py::ManifestTest::test_provides_tools_matches_register
```

With `pyyaml` present the same suite is **187 passed / 35 subtests**. So A2 ("pytest green at the
certified SHA") cannot be ticked as a judge would run it: the README lists no dependency step and
`tests/test_package.py` imports `yaml` unconditionally. **Fix:** declare PyYAML (or make the manifest
test skip-guarded). Owner: @smith.

Counts move between runs for a benign reason: `skipUnless(find_spec("fastapi"))` guards skip whole
files when FastAPI is absent (measured at an earlier head: 134 passed + 3 skipped without it, 137 with).

## 4. One scoped observation (S3, harness-triggered — not a demo blocker)

Re-installing with `--force` **over an existing rehearsal home** re-provisions that data root: it removed
`config.yaml` and sibling files I had written, and replaced the root's SQLite generations while old
handles were live. Hermes' own state layer detects this and logs it
(`hermes_state: … WAL/SHM generation was deleted or replaced`) and captures a retired WAL.

Herd's store caches schema initialisation **per DB path per process** (`_initialized`, `herd_store.py:190`),
so once a process has initialised a path it never re-checks it: a DB replaced under a live process leaves
`identity()` at `sqlite3.OperationalError: no such table: meta` and the peer route answering **500** until
the gateway restarts. Two clean restarts (no reinstall) produced **no** such warning and no 500s, so this
is reinstall-induced, not a restart defect.

**Recommendation (non-blocking):** validate the schema on `connect()` (or key `_initialized` on file
identity/mtime) so a replaced/corrupt DB self-heals instead of 500-ing on the peer route.

**Harness lesson (mine, recorded):** configure a home *after* installing into it — never install over a
configured root.

## 5. F-3 status after this run

- **A1** freeze SHA → **n/a** (no freeze; certified SHA above is the current head)
- **A2** pytest green → ❌ blocked on the PyYAML declaration
- **A3** `node --check` → ✅ · **A4** validate → ✅ · **A5** doctor → ✅
- **A6** SPINE demonstrated → ⏳ **this run supplies it for `b69a9d0`**: three consecutive two-gateway
  round-trips both directions, against the installed pinned artifact. TC-2.3 (agent post seen by the
  other human) and TC-2.6 (restart keeps history — now measured above) still want a real-agent and
  real-UI capture on the two Macs; the store-level legs are proven here.
