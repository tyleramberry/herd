# Q-1 — SPINE Milestone QA Checklist

Owner: @sentry · Written: Nov 4, 2026 · Applies to: **Thu Nov 5 SPINE milestone**
("two gateways exchange one real message through the plugin"), the Q-2 QA round
(Nov 6–7), and the **Q-7 round (Nov 7–8)** for Tyler's Nov 6 directive —
S-13 promote-a-DM (F1, §6h TC-10), S-14 wake context (F2, TC-4.10–4.16 in §6b),
S-15 supervision status + badge (F3, §6i TC-11). Cross-references to source
lines are against `a248d5b` and move with the diff; re-anchor on the PR head.

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

### TC-4 (S-14 / F2 extension — assignment context on the wake)

Tyler directive F2. The wake stops being a dumped chat message and becomes an
assignment. The injected text must state, in plain language, **who** asked,
**what** is expected, and **where to report back**. F2 is **additive only**: every
guards row below is the S-7 contract, and any change to a guard is a bug.

Ground rules (pinned against `herd_store.wake_text` / `_maybe_wake` at `a248d5b`
so Smith and QA build the same thing):

- Today `wake_text` already carries all three fields in some form:
  `"[Herd] {author_name} mentioned you in {channel_name} … {quoted} … reply with
  herd_post to {channel_name}"`. F2 is graded on **explicitness and correctness of
  the refs**, not on the mere presence of the sentence.
- **The "where" ref must be callable.** `wake_text` substitutes the human label
  `"your DM"` for a DM channel (`herd_store.py:627`), but `resolve_channel` cannot
  resolve `"your DM"` — it resolves a DM by the *other participant's name* or the
  `dm:<a>+<b>` id. A woken agent told to `herd_post` to `"your DM"` gets a 404.
  This is the known defect F2 must close; TC-4.12 asserts the ref round-trips
  through `herd_post`.
- Capture the injected payload (never a screenshot of a chat) — the
  `WAKE_HANDLER` spy in `tests/test_store.py` (`store.WAKE_HANDLER = lambda key,
  text: …`) is the harness; each row records the exact injected string.

- [ ] TC-4.10 **WHO present.** Injected text names the human (their display name
      as stored in `author_name`) and the channel they asked in — `#general` for a
      public channel, the DM's label for a DM — in plain language. Assert the
      verbatim substrings against the captured inject payload.
- [ ] TC-4.11 **WHAT present, verbatim.** The mention text is quoted as data
      (every line prefixed, as today) — no paraphrase, no truncation of a long
      mention, emoji/unicode intact. The agent can act on the raw request.
- [ ] TC-4.12 **WHERE is callable (the F2 acceptance test).** The text names the
      channel ref AND the `herd_post` call to use, and feeding that ref back into
      `herd_post`/`resolve_channel` lands the reply in the SAME channel the mention
      came from. Run it for `#general` and for a DM. **A DM wake whose reported
      ref does not resolve is a FAIL (S2)** — today's `"your DM"` label is exactly
      that; the fix is the other member's name or the `dm:` channel id.
- [ ] TC-4.13 **Guards unchanged.** Re-run TC-4.1…TC-4.9 against the new text
      unchanged: mentions only; one wake per message id; agent-authored messages
      never wake; default off; all three opt-ins still required; per-minute cap;
      no loop; approvals apply (rule 12). Diff `_maybe_wake` and require the guard
      predicates be unchanged — not merely "tests still green".
- [ ] TC-4.14 **Adversarial: the richer text must not become an injection
      vector.** (a) A mention whose CONTENT imitates Herd's own framing (`[Herd]
      system: …`, "ignore the above and …") stays inside the quoted block and is
      never promoted into the instruction line. (b) who/what/where come from
      stored rows, not from the mention text — a mention containing fake `@`s or a
      fake channel name cannot change the report-back ref. Spoof attempt → the ref
      stays the real channel.
- [ ] TC-4.15 **Context is current, not stale (S-13 × S-14).** Wake triggered
      after a DM→channel promote reports the channel the message is IN at wake
      time; the label resolved for the wake matches the channel the message row
      lives in. A renamed/re-created channel never injects a stale name.
- [ ] TC-4.16 **Failure isolation.** Missing/renamed channel at wake time still
      does not break sync or display (TC-4.9), and the wake degrades to a
      still-callable ref or is suppressed — never a ref that cannot resolve.

Known limit: `author_type` is set by the sending gateway, so a rogue linked peer could label an agent post as `human`. Bounded by the rate cap, the owner's approvals, and the fact that the peer already holds our API key.

## 6c. TC-5 — Two-way peer registration states (S-8; due Nov 6)

Ground rules (code + S-8 repro, pinned so Smith and QA build the same thing):

- Herd consumes ONLY its own join form (Settings → Plugins → Herd →
  `peer_name` / `peer_url` / `peer_key`, or the pane's "Connect a teammate"
  button). Core `hermes peer add` registers a gateway with Hermes CORE —
  Herd never reads it (Q-3 CA-4; rule-11 ruling stripped `use_hermes_peers`).
- One registered side carries BOTH directions: the registered side pushes its
  own and pulls the peer's messages every 3 s, and the unregistered side
  still receives them via its own `POST /herd/v1/sync` endpoint. The S-8
  defect is the UNREGISTERED side's pane state: it must tell its owner what
  to do, not sit on a bare "No teammate connected".
- Run the whole matrix on two clean instances (§2 topology), same plugin
  SHA both sides (ENV-1). Every cell: record pane copy verbatim + screenshot.

- [ ] TC-5.1 **Neither side registered.** Both panes show an unconnected
      state with the connect affordance. Local features work with no peer at
      all (create channel, post, read — the pane must not require a peer).
      A post on A does not appear on B.
- [ ] TC-5.2 **One-way registration = the S-8 repro.** Register A→B only
      (A's join form: B's name, URL, key). (a) Messages still flow BOTH
      ways within one sync tick: post on A appears on B, post on B appears
      on A — a regression here is **S1** (it breaks the SPINE contract that
      one-sided linking is enough). (b) B's pane shows the actionable
      waiting state — "waiting for YOUR peer add" (or equivalent) with the
      exact steps, naming HERD'S OWN join form, not core `hermes peer add`.
      A bare "No teammate connected" on B is a FAIL of this TC.
- [ ] TC-5.3 **Second registration converges.** B registers A → both panes
      show Connected within one sync tick (~3 s), no restart; each side's
      participants list shows the other's correct display name (not the
      "peer" fallback), DMs between the two open to the same channel both
      sides.
- [ ] TC-5.4 **Wrong URL / wrong key.** Bad key → the "Add X's key" /
      auth-failure state; bad URL → "Can't reach X" state; neither crashes
      the pane or the backend. Fix the field → link recovers and back-syncs
      everything missed (cursors were not advanced past undelivered rows).
- [ ] TC-5.5 **Rename / re-register must not replay.** Change `peer_name`
      (or re-enter the same URL) on A → no duplicate participant rows, no
      message re-flood (push/pull cursors keyed by URL survive), status
      label shows the new name.
- [ ] TC-5.6 **Unregister.** Clear A's peer fields → sync stops (posts stay
      local on both sides), pane returns to the unconnected state, history
      intact. Re-register → converges again.
- [ ] TC-5.7 **Ambiguity trap (docs/copy).** Run core `hermes peer add`
      alone (no Herd form) → Herd pane still shows unconnected and no sync
      runs; the pane copy must not imply core registration connects Herd.
      If Smith's fix auto-detects via core peers instead of the form, rerun
      the catalog audit (TC-0.8) — reading core peers was ruled out in Q-3.

## 6d. TC-6 — @-mention autocomplete (S-9; due Nov 6)

Acceptance per spec: typing @ in the composer opens a dropdown of taggable
participants — humans AND agents — keyboard navigable, Enter/Tab selects,
and the inserted token renders highlighted and RELIABLY triggers the S-7
wake. The wake contract is `mention_handles()` in `herd_store.py`: display
name → slug (`[^a-z0-9]+`→`-`) → handles `{@slug, @slug-hermes}`, and BOTH
handles wake the peer's agent. The invariant under test:

**every token the dropdown can insert is in `mention_handles()` of that
participant** — a token that renders pretty but never matches is a silent
wake failure (S2).

- [ ] TC-6.1 **Dropdown contents.** On a channel after both sides have
      posted: typing @ lists the remote human participant AND the remote
      agent (the `-hermes` handle). Self may appear but must be harmless.
- [ ] TC-6.2 **Keyboard nav.** ↑/↓ move the highlight, Enter or Tab selects,
      Esc closes, further typing filters, click also selects. No selection
      + Enter = posts the text as typed (Slack parity).
- [ ] TC-6.3 **Inserted token matches the wake contract.** For a multiword
      name ("Tyler Amberry") the dropdown inserts `@tyler-amberry` (the
      slug), NOT `@Tyler` or `@Tyler Amberry`. For names with emoji/unicode,
      the slug still matches `mention_handles` on the receiving side.
- [ ] TC-6.4 **Wake round-trip (S-9 × S-7; run after TC-4).** All three
      opt-ins on B; on A send a mention chosen from the dropdown → exactly
      one wake on B, quoted + labelled, per TC-4.4. Then select YOURSELF
      from the dropdown on A → renders highlighted but never wakes (own
      `gateway_id` guard). Then a plain `@typo-name` from the dropdown-less
      path → no wake (TC-4.8 regression intact).
- [ ] TC-6.5 **Dropdown edges.** @ with no participants yet → no crash;
      `a@tyler` mid-word → no dropdown (matches the `(?<![\w@])@` regex);
      selecting does not eat surrounding text; backspace past @ closes it;
      long names truncate with layout intact (S3 otherwise).
- [ ] TC-6.6 **Duplicate slugs.** Two participants whose names slug to the
      same handle → dropdown shows both, distinguished; the ambiguous
      handle's wake behavior is documented and tested (S3 if it silently
      picks one).
- [ ] TC-6.7 **Cross-gateway rendering.** The chosen @token syncs verbatim
      and renders highlighted on the other gateway; the TC-4.5 no-loop
      guard still holds (agent replies never wake anything).

## 6e. TC-7 — Threads (S-11; due Nov 7)

Sync model to hold Smith to: a thread reply is a MESSAGE (same UUID
idempotency, same push/pull cursor, same `INSERT OR IGNORE` ingest) plus a
parent reference to the root message's ID — never to a local seq or
timestamp. Threads converge across gateways exactly like messages do;
anything with a second, separate sync path is a red flag.

- [ ] TC-7.1 **Thread UI.** Reply-in-thread opens a thread view
      (Slack-like); replies live in the thread; the root shows a reply
      count / jump affordance; the channel timeline is not polluted by the
      replies.
- [ ] TC-7.2 **A→B.** Root + replies posted on A render on B as the SAME
      thread within one sync tick, order stable (id/seq sort), no reload —
      event path first, then again with the event path down (poll fallback,
      TC-2.5 analog).
- [ ] TC-7.3 **B→A into the SAME thread.** B replies to a root that came
      from A → the reply lands in A's existing thread (parent resolves by
      message UUID on both sides), not a new or orphan thread.
- [ ] TC-7.4 **Convergence & dup delivery.** The same reply delivered twice
      → one row (ingest idempotent). Reply arrives before its root
      (offline catch-up / reordering) → no crash; the thread reattaches
      when the root lands; replies whose root never arrives degrade
      visibly but sanely.
- [ ] TC-7.5 **Cross-feature.** @-autocomplete works in the thread composer
      (S-9 × S-11); a thread reply from the other gateway that mentions
      the peer agent still wakes per TC-4 (or the limitation is
      documented); reactions work on thread replies (S-12 × S-11); threads
      in a DM are allowed or cleanly absent.
- [ ] TC-7.6 **Persistence & migration.** Restart B → thread history intact
      (TC-2.6 analog). Upgrade-in-place: a pre-threads `herd.db` (0.1.0
      message history) + new plugin → schema migrates without crash and
      the old history stays readable (migration documented in the PR;
      S2 if upgrade wipes or refuses the old DB). Fresh
      uninstall/reinstall still passes TC-3.7.
- [ ] TC-7.7 **Ordering & load.** 3 quick replies → order 1,2,3 on both
      sides (TC-2.4 analog); a 50-reply thread renders without noticeable
      jank.

## 6f. TC-8 — Message reactions (S-12; due Nov 7)

Locked set (per N-4 re-baseline): 👍 ❤️ 👁️ 🎉 — exactly these four, no
free-form emoji. Reactions are TOGGLEABLE state, not append-only messages,
so this is the most dangerous sync surface of the new scope: dup delivery
must not inflate counts, and a remove must not resurrect. Every TC below
ends with both sides showing the SAME reaction state.

- [ ] TC-8.1 **Add UI.** Hover a message → the four reactions are offered
      (only these four); click adds my reaction: count 1, visibly mine.
- [ ] TC-8.2 **Toggle & aggregate.** Click again removes mine: count
      decrements, empty state clean. Second person reacts the same emoji →
      count 2; one row per (message, reactor, emoji) — the dedup contract,
      the reaction analog of message UUID idempotency.
- [ ] TC-8.3 **A→B sync.** A reacts → appears on B within one sync tick, no
      reload (event path), and via the poll fallback when the event path
      is down.
- [ ] TC-8.4 **Convergence & dup delivery.** B reacts 👍 on the same
      message after A → count 2 with TWO distinct rows (per-reactor
      identity — beware the gateway_id / display_name mismatch that yields
      two rows for one person). The same reaction event delivered twice →
      no count inflation.
- [ ] TC-8.5 **Remove-then-add across offline.** A adds 👍 then removes it
      while B is offline; B comes back → converges to REMOVED (no
      resurrection after catch-up). A re-adds after B caught up →
      converges to ADDED. Interleave add/remove between the sides in both
      orders → final state identical on both sides after every
      interleaving.
- [ ] TC-8.6 **Edges.** React to a message not yet synced / unknown id →
      no crash, no phantom row; reactions on thread replies; the four
      emoji render correctly and distinctly on both Macs at UI size;
      reaction state survives gateway restart (SQLite) and plugin
      disable/re-enable (TC-3.6).
- [ ] TC-8.7 **Scope guard.** No new agent tool for reactions without a
      scope-change ruling (N-1 locks 3 tools): TC-0.8 catalog audit must
      still pass with 3 tools; any new endpoint stays in the
      `/api/plugins/herd/` + `/herd/v1/` namespaces (TC-0.7); reaction UI
      is human-only.

## 6g. TC-9 — Single + button (S-10; due Nov 6; polish)

- [ ] TC-9.1 One + affordance replaces New Message / New Channel; opens a
      small menu with exactly those two items.
- [ ] TC-9.2 Menu closes on Esc / click-outside with no action; New
      Message → DM picker; New Channel → create dialog; TC-1.3's
      empty-state create affordance still works (no regression).
- [ ] TC-9.3 Keyboard accessible; menu teardown disposes its
      listeners/interval (TC-1.7 pattern); no hardcoded colors in the new
      code (TC-0.6 grep).

## 6h. TC-10 — Promote a private DM into a shared room (S-13; F1; due Nov 8)

Tyler directive F1, the highest-priority new item. From an open DM, one human
action — **Share to a channel** — creates a named shared channel and replays the
DM's messages into it, in order. The DM is never touched. This is a new sync
payload on the critical path (risk R-5), so **TC-10.4 must pass on two gateways,
not just in unit tests** before merge.

Ground rules (pinned against `herd_store.py` / `plugin_api.py` at `a248d5b`, so
Smith and QA build and test the same thing):

- A DM is a channel row with `is_dm=1`, `id = "dm:<gid_a>+<gid_b>"` (sorted) and
  exactly two `members` (`open_dm` / `dm_channel_id`). A promoted room is a
  NORMAL channel: `is_dm=0`, `id` = the normalized name, `members=[]`.
- **Existing ingest contract that promote can silently violate.** `post_message`
  raises `409 "Message id … already exists in another channel"` when an id is
  reused across channels (`herd_store.py:406-411`), and `ingest` is
  `INSERT OR IGNORE` on the message id (`:494`). So a copy that keeps its ORIGINAL
  DM message id is silently DROPPED on the peer gateway (that id already exists
  there, in the DM) while still looking correct locally. **That is a data-loss
  path — S1 — and TC-10.5 is the test for it.** Copies must carry fresh ids.
- **Ordering.** `list_messages` sorts by `created_at, id`. Copies minted with
  `_now()` inside one tight loop can share a millisecond, leaving the `id`
  (random UUID) as the tiebreak → scrambled order. The replay must carry the
  SOURCE `created_at` (or an equivalent monotonic order/tiebreak) — TC-10.3.
- Channels converge for free: `export_batch` re-sends ALL channel rows every
  round and `_upsert_channel` `INSERT OR IGNORE`s public channels by normalized
  id. So the promotion is really a message-replay problem, not a channel problem —
  test the messages, not just the sidebar row.
- If S-15's status tool lands, `plugin.yaml provides_tools` grows; TC-0.8 /
  `scripts/qa/catalog_audit.py` must move in lockstep with whatever registers.

- [ ] TC-10.1 **Affordance.** From an OPEN DM, one human action — Share to a
      channel — offers to name the new room; it is offered in the DM view only
      (not on public channels), cannot be double-fired, and has a visible
      cancel/validation error path (a bad name follows TC-3.1's 422 copy).
- [ ] TC-10.2 **Happy path, local (the demo beat).** DM with 5 messages → Share to
      `dm-share`: a normal channel appears in the sidebar under that exact name,
      containing all 5 in original order; the DM still shows its 5, unchanged and
      still openable. Promote **copies**; it never deletes history.
- [ ] TC-10.3 **Order + timestamp provenance.** Post 3 messages on A (1,2,3, TC-2.4
      analog) → the promoted channel reads 1,2,3 on BOTH sides; the copies keep
      the source `created_at` (or an equivalent monotonic order) so order survives
      a tight-loop replay and a `?after_seq` resume. Same-millisecond ties must
      not scramble order — the tiebreak is pinned in the PR, not implied.
- [ ] TC-10.4 **Both gateways, one sync cycle (R-5 gate).** Within one sync tick
      (~3 s) B's channel list AND the promoted channel's messages appear without a
      manual reload — channel row and messages together, both directions (promote
      on A → B; promote on B → A). Run once with the event path up and once with
      it down (poll fallback, TC-2.5 analog). **This row is the merge gate for
      S-13**, not the unit tests.
- [ ] TC-10.5 **Copies have new ids; nothing is silently dropped.** Every copied
      message's id differs from its source DM message's id, and B's promoted
      channel message count equals A's. A copy reusing the source id is a FAIL
      even if it looks right locally — on B it would be `INSERT OR IGNORE`d away
      against the DM row (S1, silent history loss). Assert counts on BOTH sides.
- [ ] TC-10.6 **Idempotent / dup-delivery safe.** Replay the promote payload (dup
      sync delivery, TC-2.7 analog) → one row per message, no inflation. Sharing
      the SAME DM twice → either a clean `409 "already exists"` (the
      `create_channel` contract) or a no-op — never a partial second copy. Name
      collision follows TC-3.3 (409, UI doesn't crash).
- [ ] TC-10.7 **The DM is untouched (demo safety + R-5).** Before/after field
      compare of the DM row (`id, name, is_dm, members, created_at`) and its
      messages (`id, content, created_at, seq`) → identical. After the promote, a
      new message posted in the DM still reaches the peer, and `peer_state.push_seq
      /pull_seq` were not advanced past undelivered rows (TC-2.4/TC-2.7 stay green
      after a promote). A promote that eats the DM's cursor delays or drops DM
      sync — FAIL.
- [ ] TC-10.8 **Agent view (F1's fourth bullet).** `herd_list_channels` includes
      the promoted channel with `type: "channel"` (not `"dm"`), a sane
      `message_count`, and no `members` array; `herd_read_channel` returns the
      copies in order; `herd_post` to it lands in the promoted channel and NOT in
      the DM. An agent can be pointed at the room.
- [ ] TC-10.9 **Edges.** Empty DM → plain refusal or an empty room, never a crash
      or a phantom row; peer offline during promote → the room is local now and
      converges when the peer returns (TC-5.4 analog); a promote below the 48-char
      `_CHANNEL_NAME_RE` limit and one above it behave per TC-3.3; the DM's own
      participants/`is_dm` rendering on B is unchanged.
- [ ] TC-10.10 **Cross-feature carry-over is pinned, not guessed (S-11/S-12).**
      State in the PR what a copy does with (a) thread parent refs and (b)
      reactions on the source messages — copied with the message, or deliberately
      dropped and documented. The TC asserts the documented choice; a copy whose
      parent ref points at a row that does NOT exist in the promoted channel
      (orphan thread) or a reaction row inflated across the copy is a FAIL. If
      S-11/S-12 are cut before freeze, mark N/A in the run log.
- [ ] TC-10.11 **Protocol/version honesty (rule 13 / H-6).** `PROTOCOL_VERSION`
      bumped once, in one place, and visible in `/herd/v1/ping` + `/status`; a v1
      peer receiving a v2 body must not corrupt data or 500 (`handle_peer_sync`
      does not check `v` at all today — verify what an old side does with the new
      payload and record it). A version string no code checks is a disclosure item
      for Herald's H-6 text, not a silent pass.

## 6i. TC-11 — Live supervision status line + speaker badge (S-15; F3; due Nov 8)

Tyler directive F3. One short plain-English phrase beside an agent's in-flight
work, from a **fixed** vocabulary, plus a per-message human/agent badge. No
tool-by-tool stream. Rides existing plumbing only: `herd_store._notify` →
`broadcast_plugin_event` plus the pane's 3 s poll (`REFRESH_MS = 3000` in
`desktop/plugin.js`; the 10 s `SYNC_MS` loop is peer sync, not status).

Ground rules:

- Vocabulary, exactly five: `reading the code` · `writing the code` ·
  `reviewing` · `done` · `idle`. Anything else — including plausible variants
  ("thinking", "running tests", a tool name) — is a FAIL.
- **No status set ⇒ the pane shows NOTHING.** Never a guessed, invented or stale
  phrase. The S-15 card names this as the main way the feature fails; TC-11.2
  tests it FIRST.
- Badge baseline today: `MessageRow` (`desktop/plugin.js:322-333`) renders the
  author name always and a `Badge` reading "agent" ONLY for
  `author_type === 'agent'` — **human messages carry no badge**. "Every message
  carries a human/agent badge" is therefore a real delta; TC-11.6 tests both.
- A status setter is a NEW AGENT TOOL ⇒ `plugin.yaml provides_tools` + the
  `herd.yaml` capability list + rule-13 text must move together (rule 6:
  declarations equal what `register()` registers). Registering without declaring
  is S1, and `catalog_audit.py` must show 4 tools, not 3.

- [ ] TC-11.1 **Vocabulary lock.** For each of the five phrases the pane renders
      exactly that phrase beside the agent's in-flight work; an invented status
      ("thinking about it", "ran bash", "") renders nothing or is refused with a
      plain error — never an unknown phrase on screen. Assert the rendered string
      is one of the five (case/normalization pinned in the PR).
- [ ] TC-11.2 **Unset shows nothing (test first).** Fresh install, no status ever
      set, agent mid-turn → the work line renders nothing: no placeholder, no
      "idle", no last-known phrase. A guessed "idle" or a stale phrase here fails
      the feature's stated contract (S2).
- [ ] TC-11.3 **No staleness.** Set `writing the code` → it appears; with no
      further update past the documented bound it clears (or only ever changes on
      a real event). Repeated pane reloads/polls never resurrect a stale phrase.
      The TTL/clear rule must be stated in the PR code — "it eventually goes
      away" is not testable.
- [ ] TC-11.4 **The acceptance sentence, one assertion each.** (a) exactly the
      five-phrase set; (b) unset ⇒ empty; (c) every message renders a human/agent
      badge that matches its `author_type`.
- [ ] TC-11.5 **One phrase, no activity stream.** No second channel of activity
      text anywhere in the pane (no tool names, file paths or per-step lines), and
      no new event kind beyond the single status event — grep the diff, then watch
      the event log across a real agent turn. A tool-by-tool stream is out of
      scope by construction and a FAIL if present.
- [ ] TC-11.6 **Speaker badge both ways.** Human-posted message → "human" badge;
      `herd_post` message → "agent" badge; a message that arrived FROM the peer
      gateway shows the badge matching the `author_type` it carries. Badge is
      never inferred from the author name. (Known limit, already documented for
      TC-4: `author_type` is sender-set — note a mislabelled peer post, do not
      fail the build for it.)
- [ ] TC-11.7 **Transport honesty (the OAuth-remote trap).** With the event path
      down (sockets no-op on OAuth remotes, TC-2.5), status still reaches the pane
      via the 3 s poll of `/status`. Status set must not block or slow a post
      (`_notify` is fire-and-forget). A status that only arrives over the socket
      is S2.
- [ ] TC-11.8 **Scope + namespace guards.** The setter is a registered tool with a
      schema, returns a JSON string, accepts `**kwargs` (TC-0.9); any new endpoint
      stays under `/api/plugins/herd/` (TC-0.7); no hardcoded colors in the new
      pane code (TC-0.6); timers via `ctx.*` (TC-1.7); `catalog_audit.py` 0 FAIL
      with the declared tool count; rule-13 text for the status write path lands
      with Herald (H-6) and is signed off by Sentry before merge (gate item).
- [ ] TC-11.9 **Disable/re-enable & restart.** Toggle the plugin off → work line
      and badges go with the pane, no interval/listener leak (TC-3.6/TC-1.7);
      re-enable → back; a status set before a gateway restart does not come back
      as a stale phrase.
- [ ] TC-11.10 **Cross-feature.** Status renders while a thread view (S-11) is
      open without disturbing it; badges are correct on thread replies; status is
      unaffected by an in-flight promote (S-13).

### Decisions to pin BEFORE the S-13/S-14/S-15 code lands (Smith: confirm or correct)

These are the places where the spec is silent and a guess would be untestable.
Pinned here so the PR and the checklist cannot disagree (same discipline as
TC-5's ground rules):

- **D-1 (S-13) Room membership.** Public channels carry `members=[]` today, so
  "both participants present" cannot mean the channel row's `members`. QA's
  observable is the participants list + message authorship; if Smith adds real
  channel membership, say so and TC-10.4/TC-10.8 assert both members.
- **D-2 (S-13) Copy id provenance.** New ids per TC-10.5 (required — the original
  id is `INSERT OR IGNORE`d away on B). A dedicated ingest path that preserves the
  id under a new namespace is acceptable if it is named in the PR.
- **D-3 (S-13) Copy `created_at`.** Carried from the source (§ TC-10.3) with a
  stated tiebreak.
- **D-4 (S-13) Threads/reactions carry-over.** Copied or dropped — either is
  fine, undocumented is not (§ TC-10.10).
- **D-5 (S-15) Status scope.** Local gateway's agents only (rides `_notify` +
  the pane's own poll), or also the peer's agents (needs a sync field and a
  protocol change, contradicting "no new transport"). QA assumes local-only; if
  cross-gateway is in scope, add a row that a remote agent's line never shows a
  guessed phrase.
- **D-6 (S-15) Where the vocabulary is enforced** — backend setter or pane render —
  pinned so TC-11.1 can assert both the refusable input and the rendered output.
- **D-7 (S-13/S-15) Mixed-version window.** Both features add declared surface
  (`PROTOCOL_VERSION`, `provides_tools`). The freeze-day audit (TC-0.8, Q-3) runs
  on the merged head; a peer on the previous build must not 500 (TC-10.11).

Out of scope for Q-7: **S-16 (F4)** — its catalog ruling is Q-8 and no line of
code starts before that ruling. S-15 is cut #2 (Sat Nov 7, 18:00) if unmerged;
S-13 and S-14 are not cut (Foreman escalates to Tyler instead).

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

Q-7 worked examples (so the new surface is not argued case by case at 2 a.m.):

- **S1** — promote silently drops copies on the peer gateway (TC-10.5); promote
  mutates or deletes the DM / its history (TC-10.7); a status tool registers
  without `provides_tools` + `herd.yaml` + rule-13 in lockstep (TC-0.8/TC-11.8);
  an S-7 wake guard changed by F2 (TC-4.13).
- **S2** — promote does not converge on both gateways within a sync cycle
  (TC-10.4, the R-5 gate); replay order scrambled (TC-10.3); the wake's
  "where to report back" ref does not resolve for a DM (TC-4.12); a status that
  only arrives over an event socket, or a guessed/stale phrase when unset
  (TC-11.2/TC-11.3/TC-11.7).
- **S3** — human badge missing / badge inferred from the author name (TC-11.6);
  promote affordance copy or an empty state that names the wrong thing
  (TC-10.1); status line spacing/truncation.

Q-7 loop (same contract as Q-2, extended to the new surface): a FAIL files a bug
to @smith with ID, severity, TC id, exact repro, expected vs actual, A/B topology
+ plugin SHA + Hermes version, evidence path. I re-run the failing TC **and its
neighbors** on the fix before closing it — nothing closes on the engineer's word.
When the new-scope items are clean, the verdict goes to @foreman in a fresh
message (the Q-2 thread is capped): "QA passed: PR #N, tests X/Y green, edge cases
covered", plus the one-paragraph quality assessment. Anything cut per N-5 §3
(S-15 second, S-16 first) leaves the board the same hour it is cut, and its TC
rows are marked N/A in the run log rather than silently skipped.

## 8. Sign-off

Nov 5 night: report to @foreman — SPINE PASS/FAIL, TC-2.x evidence, open
bug list by severity. SPINE FAIL = escalate same night (S-2 rule).
Nov 6–7 (Q-2): full board (TC-0…TC-9) against Smith's PRs, including the new-scope sections TC-5…TC-9 (S-8 two-way peer registration, S-9 autocomplete,
S-10 + button, S-11 threads, S-12 reactions — N-4 re-baselines the cut-list:
threads + reactions IN with the four emojis, autocomplete and + button IN as
polish) as each PR lands; when clean,
sign off explicitly ("QA passed: PR #N, tests X/Y green, edge cases covered")
and route the assessment to @foreman.

Nov 7–8 (Q-7): the same full-board discipline for Tyler's Nov 6 directive —
TC-10 (S-13 promote), TC-4.10–4.16 (S-14 wake context), TC-11 (S-15 status +
badge) — as each PR lands, **on the merged head** (TC-10.4 is a two-gateway gate,
so unit tests alone never sign S-13 off). Per-PR sign-off:
"QA passed: PR #N, tests X/Y green in both clone-name variants, edge cases
covered", plus the one-paragraph quality assessment to @foreman. Two gate items
are Sentry-owned and block merge, not just sign-off: the H-6 rule-13 text for the
new write paths, and the freeze-day catalog audit (TC-0.8, Q-3)
`python scripts/qa/catalog_audit.py . --entry herd.yaml` → 0 FAIL with every WARN
explained. S-16 (F4) is not a Q-7 item: it waits on the Q-8 ruling.
