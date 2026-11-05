# Q-1 — SPINE Milestone QA Checklist

Owner: @sentry · Written: Nov 4, 2026 · Applies to: **Thu Nov 5 SPINE milestone**
("two gateways exchange one real message through the plugin") and the Q-2 QA
round (Nov 6–7).

SPINE passes only when **TC-2.1 and TC-2.2 both pass**: a message posted on
gateway A appears in the channel view on gateway B (and the reverse), without
a manual reload, on a clean install. Everything else in this file exists to
make that claim trustworthy.

Conventions: gateway **A** = the instance that posts first; gateway **B** =
the receiving instance. Run every TC from a clean state (see §2) unless the
TC says otherwise. Record PASS/FAIL + evidence (screenshot or terminal
output path) per row; a FAIL files a bug per §7 and blocks sign-off per §8.

---

## 1. Gate criteria (what "done" means for Nov 5)

- [ ] TC-2.1 (A→B) and TC-2.2 (B→A) PASS on a clean install
- [ ] No S1 bugs open; no S2 bugs open on the fan-out path
- [ ] `hermes plugins validate .` and `hermes plugins doctor . --ci` clean
- [ ] Backend tests (`python -m pytest tests/ -q`) green
- [ ] Results reported to @foreman the same night (per S-2 escalation rule)

## 2. Test environment setup

Two independent Hermes instances. Either topology is valid:

- **Two machines** (the demo topology: Tyler + wife's instances), or
- **One machine, two profiles**: `HERMES_HOME=~/.hermes/profiles/qa-a` and
  `HERMES_HOME=~/.hermes/profiles/qa-b`, each with the desktop app running.

Setup steps (per gateway):

```
hermes plugins install tyleramberry/herd --no-enable   # or install by local path
hermes plugins enable herd                              # backend import gate (plugins.enabled)
```

Then link the pair on ONE side (README contract):

```
hermes peer add <name> --url <their-gateway-url> --key <API_SERVER_KEY>
```

Preconditions to verify BEFORE testing (a failure here is env, not product):

- [ ] ENV-1 Both gateways run the same plugin commit (record SHA per side)
- [ ] ENV-2 Each gateway's desktop app is connected to its own gateway
- [ ] ENV-3 Peer link shows healthy/connected in each app
- [ ] ENV-4 Desktop half visible in Settings/Capabilities → Plugins on both

## 3. TC-0 — Static / pre-flight (run once per commit, before any UI testing)

- [ ] TC-0.1 `hermes plugins validate .` exits clean (includes the
      no-core-override check)
- [ ] TC-0.2 `hermes plugins doctor . --ci` exits clean
- [ ] TC-0.3 `python -m pytest tests/ -q` green (FastAPI TestClient + temp
      sqlite; tests must not touch the live DB)
- [ ] TC-0.4 `node --check desktop/plugin.js` passes (plain ESM, no JSX
      syntax — the file loads uncompiled)
- [ ] TC-0.5 `desktop/plugin.js` imports ONLY `@hermes/plugin-sdk`, `react`,
      `react/jsx-runtime` — no other specifier, static or dynamic; no eval,
      no prototype patching, no touching app markup (`data-slot` etc.)
- [ ] TC-0.6 No hardcoded colors in plugin.js — theme vars only
      (`var(--ui-text-secondary)` etc.); no core-UI restyling; our UI lives
      in our pane/route only
- [ ] TC-0.7 No secrets in code; no network calls except the gateway and our
      `/api/plugins/herd/` namespace
- [ ] TC-0.8 `plugin.yaml` `provides_tools` lists exactly what `register()`
      registers via `ctx.register_tool` (locked scope, N-1: herd_list_channels,
      herd_post, herd_read_channel — no more, no fewer). Automated:
      `python scripts/qa/catalog_audit.py .`
- [ ] TC-0.9 Tool handlers return JSON strings and accept `**kwargs`
- [ ] TC-0.10 Never assigns to Hermes modules, `sys.modules`, or core
      dicts/functions at runtime

## 4. TC-1 — Local round-trip (each gateway alone, before linking)

- [ ] TC-1.1 **Opt-in half is actually opt-in.** Fresh install: desktop half
      inventories in Settings → Plugins but stays OFF; the /herd route and
      pane do not render until toggled. (A unified-package desktop half that
      self-enables is an S2.)
- [ ] TC-1.2 **Enable toggle works.** Flip the toggle → route `/herd`,
      sidebar nav row (codicon), and pane all render within a few seconds,
      no error toast ("Plugin herd failed to load" = instant FAIL).
- [ ] TC-1.3 **Empty state.** With no channels beyond the seeded `general`:
      channel list shows `general`, message view renders the empty state
      with a visible "create channel" affordance. Create a channel from
      that affordance → it appears in the sidebar.
- [ ] TC-1.4 **Post + read, same gateway.** Type in the composer, send →
      message appears in the channel view without manual refresh
      (the `message.created` broadcast → query invalidation path).
- [ ] TC-1.5 **Agent tools, same gateway.** From a Bot Chat on this
      gateway: `herd_list_channels` returns the channel list as JSON;
      `herd_post` to `general` succeeds and the message (author_type=agent)
      appears in the channel view.
- [ ] TC-1.6 **Backend namespace scoping.** All backend calls hit
      `/api/plugins/herd/*` only (verify in devtools network tab); a
      path-traversal attempt (`ctx.rest('../…')`) is rejected, not proxied.
- [ ] TC-1.7 **Timers/listeners** go through `ctx.setTimeout` /
      `ctx.setInterval` / `ctx.addEventListener` — no bare `window.*` globals
      (grep + runtime check for leftover intervals after disable).

## 5. TC-2 — THE SPINE: two-gateway fan-out

Precondition: §2 env green, TC-1 green on both sides.

- [ ] TC-2.1 **A→B.** On gateway A, post a message to `general` (human, via
      composer). On gateway B, the message appears in the channel view
      WITHOUT reload or tab-refocus, attributed with A's `gateway_id`.
- [ ] TC-2.2 **B→A.** Same in reverse: post on B, appears on A. (Fan-out
      that only works one direction is a FAIL — both directions are the
      milestone.)
- [ ] TC-2.3 **Agent→other gateway.** Agent on A posts via `herd_post`;
      human on B sees it. This is the demo payoff (two agents
      collaborating in one channel) — treat as S1-path.
- [ ] TC-2.4 **Ordering.** Post 3 quick messages on A (1,2,3). B receives
      them in order 1,2,3 (check the `created_at, id` sort).
- [ ] TC-2.5 **Refresh without sockets.** Kill/simulate loss of the event
      path on B (OAuth remote makes `ctx.socket` a no-op — test on a remote
      or force the fallback): the message still arrives via the polling
      fallback within its interval. Fan-out that depends on live sockets
      alone is an S2 (breaks on OAuth remotes by design).
- [ ] TC-2.6 **Persistence.** Restart gateway B's desktop app → channel
      history from A is still there (SQLite survived; not memory-only).
- [ ] TC-2.7 **Convergence.** Same client-generated message UUID posted to
      both gateways (dup delivery) → one row, no duplicate rendering
      (INSERT OR IGNORE contract).

## 6. TC-3 — Edge cases & error handling (Nov 6–7 round, not gating Nov 5)

- [ ] TC-3.1 Empty/whitespace content → 422, no empty bubble rendered
- [ ] TC-3.2 Post to unknown channel id → 404 (API) and a sane error string
      from `herd_post` (JSON `{"error": ...}`, not a stack trace)
- [ ] TC-3.3 Duplicate channel name → 409, UI doesn't crash
- [ ] TC-3.4 `?after=<iso>` cursor: returns only newer messages; clock-skew
      between gateways does not drop or duplicate rows
- [ ] TC-3.5 Long message (10k chars) + unicode/emoji render correctly
- [ ] TC-3.6 Disable the plugin toggle → pane/route gone, intervals/listeners
      disposed, re-enable → everything back with history intact
- [ ] TC-3.7 Uninstall + reinstall → no stale state breaks the empty state;
      seeded `general` returns
- [ ] TC-3.8 Concurrent posts from both gateways within the same second →
      no lost messages (id-sort tiebreak)
- [ ] TC-3.9 Restart gateway mid-post → no half-written message (atomicity)

## 6b. TC-4 — @mention wake (S-7 stretch; only if Foreman's go/no-go says go)

Off by default; three opt-ins (README "Let your agent answer @mentions"). Run only after TC-2 passes.
Test on the receiving Mac (B); the mentioning human is on A.

- [ ] TC-4.1 **Default off.** Fresh install, no opt-ins: A mentions `@<B-name>` in `general` → message arrives, B's agent does NOT start a turn.
- [ ] TC-4.2 **Each opt-in is required.** With only two of the three set (`allow_gateway_injection`, `mention_wake`, `/herd-listen`), a mention starts nothing. All three → starts a turn.
- [ ] TC-4.3 **Target chat precondition.** `/herd-listen` in a chat with no human message yet: Hermes refuses the injection (expected); after one human message, the mention starts a turn.
- [ ] TC-4.4 **Exactly one turn** in the chosen chat; the text is quoted and labelled as from another person.
- [ ] TC-4.5 **No loop.** The agent's `herd_post` reply (author_type=agent) does NOT wake A's side; no further turns occur.
- [ ] TC-4.6 **Approvals apply (rule 12).** A mention asking for something needing approval shows B's normal approval prompt; the injected text cannot approve it.
- [ ] TC-4.7 **Duplicate delivery** of one message id wakes once. More than 6 mentions in a minute wake at most 6.
- [ ] TC-4.8 `/herd-listen off` stops wakes. `@tylerswift` and `a@tyler.com` do not match `@tyler`.
- [ ] TC-4.9 A failed wake (target chat gone) leaves sync and message display unaffected.

Known limit: `author_type` is set by the sending gateway, so a rogue linked peer could label an agent post as `human`. Bounded by the rate cap, the owner's approvals, and the fact that the peer already holds our API key.

## 7. Bug reporting (to @smith, loop until clean)

Every bug back to Smith carries: **ID, severity, TC id, repro steps (exact
commands/clicks), expected, actual, environment (A/B topology, plugin SHA,
Hermes version), evidence path.** A bug is closed only when I have re-run
the failing TC on the fix and it passes (plus its neighbors).

Severity:

- **S1** — SPINE broken: A→B or B→A fails, data loss, crash, catalog
  admission violation (core override, secret in code, import violation)
- **S2** — feature broken on a supported path (poll fallback missing,
  ordering wrong, opt-in violated, error surfaces raw stack traces)
- **S3** — polish (copy, spacing, theme-var misses, empty-state wording) —
  still tracked; judging scores polish

## 8. Sign-off

Nov 5 night: report to @foreman — SPINE PASS/FAIL, TC-2.x evidence, open
bug list by severity. SPINE FAIL = escalate same night (S-2 rule).
Nov 6–7 (Q-2): full board (TC-0…TC-3) against Smith's PRs; when clean,
sign off explicitly ("QA passed: PR #N, tests X/Y green, edge cases covered")
and route the assessment to @foreman.
