# Spec: Multi-user (up to 5 people) + Buzz-style right-half threads + badge change

Owner: Foreman (PM) · Requested by Tyler, Nov 8 (overnight build) · Reference: Buzz by Block (open source,
Apache-2.0, github.com/block/buzz) — team chat where AI agents are first-class members with their own identity.

## 1. Multi-user: up to 5 people (was 2)

Today Herd syncs with exactly one peer. Change it to a **mesh of up to 5 gateways** (Tyler + up to 4 others).

Requirements
1. Settings hold a **list of peers** (name, url, key) — up to 4 remote peers — instead of the single
   `peer_name`/`peer_url`/`peer_key` triple. Keep backward compatibility: an existing single-peer config must
   keep working (migrate it into the list on load; do not lose the stored secret).
2. **Per-peer sync state**: cursors, `last_ok`, `last_error`, `remote_gateway_id` per peer (a
   `peer_state` row keyed by peer name). One peer failing must never stall or error the others.
3. **Fan-out**: a message authored locally is pushed to every configured peer; an inbound message from peer A
   is stored once locally and forwarded to the other peers B, C, D (so every gateway converges) — but
   **never echoed back to the peer it came from** (no ping-pong loops).
4. **Convergence**: dedupe on the message's client UUID with `INSERT OR IGNORE`; every row keeps its origin
   `gateway_id`. Two peers posting at the same time must converge to the same set of rows on all gateways.
   Reactions and threads ride the same path and must converge too.
5. **Per-peer isolation**: auth failures, timeouts, and redirects are handled per peer (the no-redirect opener
   from the B1 fix stays mandatory). Surface each peer's status in the UI; never leak one peer's key to another.
6. **Groups**: channels may hold up to 5 humans plus any number of their agents. Filter/deny sending a
   channel's messages to a gateway that is not a member.

## 2. Threads open in the right half of the screen (Buzz-style)

Clicking "reply in thread" (or a thread's reply count) opens a **right-hand panel**:

- The panel occupies roughly the right 35–45% of the Herd pane; the channel column stays visible and
  scrollable. Panel has: thread root message, its replies in order, its own composer, a close control.
- `Esc` closes; a close button is visible; the panel is not a separate route (it lives inside the `/herd`
  route/pane).
- Thread state comes from the existing thread model (`_thread_root_id`); no new sync path.
- Reuse the app's UI kit components and theme variables — it must look native, not custom-styled.
- Stay inside the plugin SDK: no DOM queries outside our pane, no `document.`/`window.` access, no imports
  beyond `@hermes/plugin-sdk`, `react`, `react/jsx-runtime`.

## 3. Badges

Remove the **human** badge from message rows. Keep the **agent** badge (and any agent-identifying styling).
Agent-authored messages must remain unmistakable; human messages should read as the default, unbadged case.

## 4. Hard constraints (unchanged, non-negotiable)

- Runtime stays stdlib-only; no new runtime dependencies. Test-only deps go in `requirements-dev.txt`.
- Catalog admission rules: no core overrides, no private core APIs, desktop stays inside the SDK surface,
  credentials only via `agent.secret_scope`, no self-updater.
- Every gate must stay green: `python -m pytest tests/ -q`, `node --check desktop/plugin.js`,
  `hermes plugins validate .`, `hermes plugins doctor . --ci`, `python scripts/qa/catalog_audit.py .`
  (0 FAIL).
- Add regression tests for: N-peer fan-out (3 gateways in the harness), no-echo, convergence with
  simultaneous posts, per-peer failure isolation, config migration from single-peer, and the thread panel's
  render contract.

## 5. Deliverable

- A branch with the work, tests, and green gates.
- `git format-patch` files for every commit (so the parent repo can apply them with history intact).
- `RESULT.md`: what changed, file-by-file, gate output, what was verified vs. assumed, and anything you could
  not verify (with the reason). Cite file:line for claims.
