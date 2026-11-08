# Herd: catalog submission pre-flight audit

**Scope.** `herd/` at HEAD `10cc2b982c72be4f5d23876e2d719f918bd811d1`, clean tree. The brief said `/workspace/herd`, which does not exist on this machine. The repo is at `./herd` in this job workspace, so I audited it there and wrote this file at the workspace root. The repo was not modified.

**Sources.** Rules: the canonical `plugin-catalog/README.md` from `NousResearch/hermes-agent` `main` (fetched raw, verbatim) and the catalog-submission docs page. Symbols and validator behaviour: the Hermes checkout at `/Users/openclaw/.hermes/hermes-agent` (release 2026.9.24), read only.

**Verdict.** One code blocker (B1, conditional but real) and one submission gate (B2). Everything else is WARN. The Hermes validator passes the tree (exit 0, `ok: true`), and the repo's own `scripts/qa/catalog_audit.py` reports 0 FAIL.

---

## STATUS — post-SEC-1 (added Nov 7; findings below are not edited)

The SEC-1 hardening branch (`54b3284`…`8840f78`, PR #56) and S-20 (`e2a6411`) landed after this
audit was written. What they closed, re-derived at the pin `8840f78`:

- **B1 — CLOSED.** S-19 (`54b3284`) refuses the peer key in cleartext off loopback and stops steering
  users to `http://`; S-24 (`8840f78`) closes the proxy key leak. At the pin the peer client is
  `build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open` (`dashboard/herd_store.py:1312`) —
  an explicit empty proxy map suppresses urllib's ambient `http_proxy`, and `_NoRedirect` surfaces a 3xx
  as an error instead of following it, so the key is never re-sent. `README.md:75` (the inbound-endpoint
  disclosure; was `:63` at this audit's HEAD) now reads "Outbound sync never follows a redirect … the key
  is never re-sent to another host". Command: `git grep -n 'build_opener' 8840f78 -- 'dashboard/*.py'`.
- **B2 — procedural; still open by design.** No code defect: the catalog entry's `sha:` is an intentional
  placeholder until the pin is taken on `origin/main`. At the H-7 branch head it reads
  `REPIN_AT_OPEN_ORIGIN_MAIN` (`docs/submission/plugin-catalog-herd.yaml:12`, `H-2:60`), which the catalog
  audit FAILs on until it is swapped — intended. H-7/H-2 own the repin.
- **W1 — CLOSED by S-20 (`e2a6411`).** The plugin no longer calls `adapter._check_auth`. Proof at the pin,
  `git grep -n _check_auth 8840f78 -- '*.py'`:

  ```
  8840f78:scripts/qa/two_gateway_run.py:168:        def _check_auth(self, request):
  8840f78:scripts/qa/two_gateway_run.py:180:        denied = adapter._check_auth(request)
  8840f78:tests/test_peer_secret_scope.py:39:    def _check_auth(self, request):
  8840f78:tests/test_peer_secret_scope.py:180:        self.assertEqual(self.adapter.calls, 0, "the plugin must not consult adapter._check_auth")
  ```

  Only the QA harness's own stub (`scripts/qa/two_gateway_run.py`) and `tests/` match — nothing in the
  plugin (`git grep -c _check_auth 8840f78 -- __init__.py dashboard/herd_store.py dashboard/plugin_api.py
  desktop/plugin.js` = 0 in all four). At `origin/main` the call was still present
  (`e23a319:__init__.py:63`, `:81`), which is exactly what S-20 removed. The W1 text's "disclosed at
  `README.md:63`" note is obsolete: at the pin `README.md:75` discloses the Herd-scoped credential and
  makes no private-core claim.

This file is a point-in-time snapshot (Nov 7, HEAD `10cc2b98`). The status block above records what later
commits closed; findings are not edited.

---

## BLOCKERS

### B1. The peer API key is sent through plain `urllib`, which forwards it across origins on redirect

- **Where:** `dashboard/herd_store.py:922-927`. The bearer header is set at `:920`. Line `:924` imports `hermes_cli.urllib_security.open_credentialed_url`. `except Exception` at `:925` falls back to `urllib.request.urlopen` at `:926`, and the request is sent at `:927`.
- **Rules:** 11 (credentials only through Hermes routes). Also 13: `README.md:63` tells users the key is dropped on a cross-host redirect, which the fallback does not do. Undisclosed behaviour found in review is a request for changes.
- **Evidence:**
  - Hermes's helper strips the credential on a cross-origin redirect: `hermes_cli/urllib_security.py:128-170` (`SafeCredentialRedirectHandler`, `_CrossOriginRequestSanitizer`).
  - Probe (`/tmp/herd-redirect-probe/probe.py`, Python 3.9.6, localhost, fake key): a 302 from origin A to origin B with the plain urllib path delivered `Authorization: Bearer FAKE-TEST-KEY-123` to B.
  - Trigger: the import at `:924` raises (for example, a Hermes build without that helper) and the peer redirects cross-origin. I could not confirm whether the `requires_hermes` floor (`plugin.yaml:7`, `>=0.22.0`) includes the helper. See the last section.
- **Minimal fix** (tested in `/tmp/herd-redirect-probe/fix_probe.py`). Delete lines `:922-926`, use an opener that refuses redirects, and drop the core import. That also clears the validator's only WARN.

  ```python
  class _NoRedirect(urllib.request.HTTPRedirectHandler):
      def redirect_request(self, req, fp, code, msg, headers, newurl):
          return None  # the 3xx surfaces as HTTPError; the key is never re-sent

  _OPEN_PEER = urllib.request.build_opener(_NoRedirect()).open
  # ...
  with _OPEN_PEER(req, timeout=SYNC_TIMEOUT_S) as resp:
  ```

  Test result: the redirect is refused with HTTP 302, the target receives no `Authorization`, and a same-origin POST returns 200. Tradeoff: a peer that answers with a redirect (for example, http to https) now shows "The peer answered HTTP 30x" instead of following it. Say so in the README if you accept that.

### B2. Submission gate: no pinned entry exists yet

- `docs/submission/H-2-catalog-pr-package.md:15` has the all-zero `sha:` placeholder. `plugin-catalog/herd.yaml` is not in this tree. Checklist items `:85` (full SHA) and `:89` (screenshots) are unticked.
- **Rule:** 2 (a full 40-hex pin is mandatory). This is not a code defect, but the PR cannot pass until the entry exists at a real commit.
- **Ordering matters.** The current HEAD `10cc2b982c72be4f5d23876e2d719f918bd811d1` still contains B1, so it is not a valid pin.
- **Fix:** commit the B1 change, run `git rev-parse HEAD`, put that value in `sha:`, rerun validation at that commit, and tick the checklist only after that.

---

## WARN (no rule fails on these; the reviewer will read them)

1. **Private core method call.** `__init__.py:63` and `:81` call `adapter._check_auth`. That method is defined on the core API-server adapter (`gateway/platforms/api_server.py:1413`). Rule 9 says the validator warns on this, but it does not: I checked, and `_check_auth` is not in the validator's private-method set (`hermes_cli/plugin_validate_private_imports.py`, `_core_private_methods()` returns False). It is disclosed at `README.md:63`. **Fix:** open a Hermes issue for a public auth-check seam, as rule 9 asks. Do not read `API_SERVER_KEY` directly, since rule 11 forbids it.
2. **Module scan and second module copy.** `dashboard/plugin_api.py:25-29` scans `sys.modules` by name (a read, not a write). If no match, `:31-33` loads a second copy of `herd_store` from its file path. The comment at `:23-24` says the two halves share one module state. The second copy has its own `WAKE_HANDLER` (`herd_store.py:63-64`) and its own locks (`herd_store.py:145`). **Fix:** have the dashboard import the package module, or remove the scan and document the second-copy behaviour.
3. **Shell-out in a shipped script.** `scripts/qa/catalog_audit.py:176` runs `git` through `subprocess`. `docs/submission/H-2-catalog-pr-package.md:70` says "Shell commands: none", which holds for the runtime files only. **Fix:** disclose it in the README, or leave `scripts/qa/` out of the pinned tree.
4. **Bytecode in history, not at HEAD.** Commit `b7a9ab4` added `scripts/qa/__pycache__/catalog_audit.cpython-313.pyc` and `tests/qa/__pycache__/test_catalog_audit.cpython-313-pytest-9.2.0.pyc`. Commit `e769135` removed them. `git ls-tree -r HEAD | grep -c '\.pyc$'` returns 0. Rule 17 scopes to the pinned tree, but reviewers can see history. **Fix:** nothing is required; be ready to explain it, or rewrite history if you prefer.
5. **Missing media.** `docs/submission/H-2-catalog-pr-package.md:24-27` points at `docs/media/*` for the banner and screenshots. `git ls-files docs/media` is empty. The catalog README calls these cosmetic, so they do not affect install, but the gallery would be broken. **Fix:** add the files and pin their URLs to the SHA, or drop the fields.
6. **README is inaccurate about reactions.** `README.md:15` lists "reactions" under "What it doesn't do (yet)". Reactions ship: `README.md:57`, and `dashboard/plugin_api.py:95-97` (`toggle_reaction`). **Fix:** remove "reactions" from that line. This matters under rule 13 accuracy.
7. **Reviewer attention on @mention wake.** `__init__.py:140-141` and `dashboard/herd_store.py:857-887` turn a teammate's human message into an agent user turn. The `herd_post` call is spelled out in the injected text (`README.md:47`). It is opt-in and disclosed (`README.md:41-45`, `:67`), and tool approvals stay with Hermes. This is not a rule violation, but expect questions about prompt injection from a peer.
8. **Version quoting.** `plugin.yaml:2` has `version: 0.1.0` unquoted. The catalog entry should quote it (H-2 line 19 does). `plugin.yaml` parses it as a string, so this is consistency only.

---

## Rule-by-rule evidence (static)

| Item | Result | Evidence |
|---|---|---|
| (a) Manifest | Pass | `plugin.yaml` parses. Validator "manifest fields" ok. `requires_hermes: ">=0.22.0"` at `plugin.yaml:7`, matching `H-2:20` (rule 14). `manifest_version: 2` (`:8`), `api_version: 1` (`:9`). `provides_tools` (`:11-14`) matches the three registrations at `__init__.py:129-134`. Validator "declared tools" ok. |
| (b) Capabilities (rule 6) | Pass | Registered: three tools, `register_platform_handler("api_server")` (`__init__.py:135`), `register_command` (`:136`), and `ctx.inject_message` (`:141`). No hooks or middleware. Validator probe: `inject_message`, `register_command`, `register_platform_handler`, `register_tool`. "Declared hooks/middleware" and "declared tools" all ok. The H-2 `capabilities:` block (`H-2:29-34`) uses the schema keys. |
| (c) Core imports (rule 9) | Warn | `agent.secret_scope` (`__init__.py:41`, `herd_store.py:249`), `hermes_constants` (`__init__.py:42`), `plugins.plugin_storage` (`herd_store.py:173`), `hermes_cli.config` (`:234`), `hermes_cli.plugin_events` (`:420`), `hermes_cli.urllib_security` (`:924`). The validator flags only `:924` (`private_import_findings`). Private method: W1. |
| (d) Runtime patching of core | Pass | `_store().WAKE_HANDLER = _wake` (`__init__.py:143`) writes the plugin's own module. `_wire_api_server` (`__init__.py:56-110`) adds routes and startup/cleanup hooks to the aiohttp app it is handed. That app is the platform-handler factory's argument (`hermes_cli/plugins.py:831-844`). Validator "no core override" ok. |
| (e) Desktop (rule 8) | Pass | Imports limited to `@hermes/plugin-sdk` and `react/jsx-runtime` (`desktop/plugin.js:3-23`). The sweep found no `import(`, `eval`, `new Function`, `document.`, `window.`, prototype writes, `MutationObserver`, `data-slot`/`data-tour`/`data-sidebar`/`data-testid`, `innerHTML`, `fetch(`, `localStorage`, or `hermesDesktop`. The only `exec(` is `RegExp.prototype.exec` at `:400`, which is a false positive. `globalThis.crypto` (`:61`) is a read. `node --check` passes. Validator "desktop surface" ok. |
| (f) Secrets (rule 11) | Pass, except B1 transport | Peer key read via `agent.secret_scope.get_secret` (`herd_store.py:244-253`, used at `:906`). Declared as a `config_schema` secret (`plugin.yaml:31-35`, `env: HERD_PEER_KEY`). No `os.environ`/`getenv`, `.env`, `auth.json`, or keychain access in tracked code. `load_config_readonly` (`:234`) reads settings only. |
| (g) Self-updating (rule 3) | Pass | No update, download, pip, or git-pull logic in code. The only remote fetch is the peer sync (`herd_store.py:916-931`). `plugin_api.py:30-33` loads a local file only. |
| (h) Credentials in repo | Pass | `git grep` over tracked files and `git log -p --all` for `sk-`, `ghp_`, `AKIA`, `xox[bp]-`, `Bearer`, and PRIVATE KEY patterns: no real matches. The only hit is a detector regex at `scripts/qa/catalog_audit.py:209`. |
| Rule 17 (binaries/bytecode) | Pass at HEAD | No binaries in tracked files. Bytecode only in history (W4). |
| Rule 18 (login backend) | Pass | No `register_login_backend` or `browser_vault`. |
| Rule 12 (approvals) | Pass | No subprocess or approval bypass in runtime code. Wake is a normal user-turn injection (W7). |
| Rule 13 (disclosure) | Mostly pass | `README.md:60-68` covers network, inbound endpoint, background loops, stored credentials, data location, agent turns, and shell. Two inaccuracies: B1 (line 63) and W6 (line 15). |
| Rule 10 (dependencies) | Pass | No `python_dependencies` declared. Validator "python dependencies": none declared. |
| Rule 14 (metadata) | Pass | `requires_hermes` matches in `plugin.yaml:7` and `H-2:20`. `manifest.json` version `0.1.0` matches `plugin.yaml:2`. |

Rule 5 (owner or major contributor) is a human check. `plugin.yaml:6` homepage points at `tyleramberry/herd`.

---

## Commands run

- `python -m pytest tests/ -q` in `/tmp/herd-venv`, Python 3.9.6, with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`. **128 passed.**
- `node --check desktop/plugin.js`. **Exit 0.**
- `python -I scripts/qa/catalog_audit.py .`. **0 FAIL, 1 WARN** (rule 9, `herd_store.py:924`).
- Hermes validator, in-process: `validate_plugin_dir(repo, None)` from `hermes_cli/plugin_validate.py:502`. This is the call `hermes plugins validate` makes without `--install-deps` (`plugins_cmd_catalog.py:900`). Run from `/tmp/herd-validate-runner/run_validate.py` with `/tmp/herd-hv`. **`ok: true`, exit 0.** 16 checks passed, including "security scan: safe". Its only warning is `herd_store.py:924`.
- **Not run:** the `hermes plugins validate` CLI itself. The wrapper says `hermes pm repair` is required, and that would change the Hermes install outside this workspace, so I did not run it. Also not run: `--install-deps`, and CI.

Scratch files are in `/tmp` only: `/tmp/herd-venv`, `/tmp/herd-hv`, `/tmp/herd-redirect-probe`, `/tmp/herd-validate-runner`, `/tmp/herd-hermes-home.*`.

---

## What I could not verify, and why

- **The `hermes plugins validate` CLI and its CI exit code.** That needs `hermes pm repair` on this Mac, which would modify the Hermes install. I ran the same validator function instead.
- **Whether `requires_hermes >=0.22.0` includes `open_credentialed_url`.** This decides whether B1's fallback is reachable for supported users. I only have the 2026.9.24 checkout, and the 0.22.0 release is not available here.
- **Runtime behaviour.** No live two-gateway test was run. The redirect result comes from a localhost probe with a fake key, not a real Hermes gateway.
- **Validator isolation note.** The validator reports `host_ready: false` and cites `tools.py:64 ctx.post_message()`. `tools.py:64` is `store.post_message`, so that reason looks like a name match, not a real ctx call. It is not an admission check. I did not confirm it beyond that.
- **Python versions.** Tests ran only on Python 3.9.6, not on the interpreter Hermes uses. Run them under that interpreter before pinning.
- **Desktop behaviour.** Only syntax and static rule checks were run. No rendering or interaction test.
- **Human judgments.** Rule 5 (owner or major contributor) and the tier and category choices.
- **Developer-guide middle section.** The fetch tool summarized it rather than quoting it. I relied on the canonical README (verbatim) for the rules and on the Hermes source for symbols.
