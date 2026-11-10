# Spec: Protocol v3 — signed events (design only)

Status: **proposal, no code.** Track 6 of the overnight Buzz-parity build (Nov 9–10, 2026). Source: §1.4 of
`docs/product/competitive-review-buzz.md`. Decisions needed from Tyler are in §10. Nothing here changes the wire
protocol until those are answered and an implementation branch is opened.

## 1. Why this exists

Today a message is identified by `(gateway, seq)` in effect, and the only thing that proves who wrote a row is the
shared Herd secret of the link it arrived on. The README says so plainly: the secret "authenticates the link to each
teammate, not the individual caller". Three consequences block the next features:

- **No edit or delete.** A row cannot be changed or retracted in a way every peer can verify, so a peer could be
  left holding a version the author withdrew.
- **No read state or audit.** Anything that must be attributed to one person (who read what, who changed what,
  an append-only history) needs a signature from that person's own key.
- **No multi-hop trust.** A row relayed through a teammate carries the origin name that the teammate chose. Relay is
  allowed because the link is trusted; a mesh of five with partial trust cannot verify origin.

Signed events fix this by making every action a signed event in one per-author log, with an identity that is a key
rather than a shared secret.

## 2. What exists today (the facts this spec builds on)

| Thing | Where | Today |
|---|---|---|
| Gateway identity | `meta.gateway_id`, `dashboard/herd_store.py` (created with `uuid.uuid4().hex`) | 32 hex chars, not a key |
| Message id | desktop `newMessageId()` = `crypto.randomUUID()`; agents and copies use `uuid4` | globally unique by chance, not by proof; `messages.id UNIQUE` |
| Local order | `messages.seq INTEGER PRIMARY KEY AUTOINCREMENT` | per database, assigned on insert; not portable between gateways |
| Sync cursors | `peer_state.push_seq / pull_seq` and `push_rseq / pull_rseq` (reactions) | per link; advance only on a successful round |
| Authentication | `Authorization: Bearer <HERD_SECRET of the callee>` on `POST /herd/v1/sync` | authenticates the link; the body's `from.gateway_id` is trusted |
| Origin rule | `_bound_gateway_id` / `gateway_id` checks in `ingest` | a row claiming this gateway's id, or a non-member's, is dropped; otherwise trusted |
| Reactions | `reactions(id, message_id, emoji, gateway_id, active)`, one row per `(message, emoji, gateway)` | toggles converge by last row per key |
| Copies | `promoted_from` on a copied DM row | new id stamped with the copying gateway |
| Pairing (Track 5) | `POST /herd/v1/pair`, one-time code, MAC keyed by the code | a teammate gets the responder's Herd secret; no long-lived identity exchanged |

Two facts matter most. The message id is not bound to its content or author, so nothing stops a relay from
rewriting a row under the same id. And a gateway's identity is a random string that proves nothing.

## 3. Goals and non-goals

Goals:
1. Every write is an event signed by its author's key. Peers verify the signature before storing.
2. A message's id is derived from its signed bytes, so an id cannot be reused for different content.
3. Edits, deletes (as tombstones), reactions and channel metadata are events too, so every peer converges on the same
   state from the same set of events, in any arrival order.
4. A relay can carry an event it did not write and peers still verify its origin.
5. Existing v2 peers keep working during migration, and nothing is lost on upgrade.

Non-goals (for this spec):
- Confidentiality. Events are plain JSON to every member, as today. Encryption is a separate decision.
- Global ordering or consensus. Order is per author (seq) plus a deterministic tie-break for last-writer-wins fields.
- Roles and permissions beyond membership. Who may edit a channel's topic is still "any member", as today.
- Removing the Herd secret. It stays as transport authentication; it just stops being the proof of authorship.

## 4. Identity and keys

**One Ed25519 keypair per gateway.** The public key is the gateway's identity: `gateway_pubkey` is 32 bytes, shown
as base64url (43 characters). The gateway's `gateway_id` becomes a short handle derived from the public key
(`first 32 hex of sha256(pubkey)`), so existing ids keep their shape.

Key storage — **open decision (§10.1).** The private key must not sit in plaintext next to the database if avoidable.
Options, in order of preference:
- **A.** A Hermes secret-store write door for plugins (the same path Track 5 needed for pairing). The key lives where
  other credentials live, and Herd only reads it through `agent.secret_scope.get_secret`, as the catalog requires.
- **B.** A file in the plugin data directory, mode `0600`, created on first run. Works today; weaker: any process
  running as the same user can read it.
- Not recommended: deriving the key from `HERD_SECRET`. A leaked link secret would then also forge authorship.

Key rotation: a rotation is an event signed by the **old** key that names the **new** key (`kind: "key.rotate"`).
Peers that verify the chain accept events from the new key. Loss of the key with no rotation means the gateway
becomes a new identity and must be re-paired; history it authored stays attributed to the old key.

## 5. Event format

```jsonc
{
  "v": 3,
  "gateway": "<base64url Ed25519 public key, 43 chars>",
  "seq": 1842,                      // the author's own counter; strictly increasing, never reused
  "kind": "message.create",         // see §5.1
  "body": { ... },                  // kind-specific, validated per kind
  "ts": "2026-11-10T07:00:00.000Z", // informational, shown to people; never used to order events
  "sig": "<base64url Ed25519 signature>"
}
```

- **Signed bytes:** canonical JSON (keys sorted, no insignificant whitespace, UTF-8, numbers as integers or
  finite decimals) of the object **without** `sig`. The signature is over those bytes.
- **Event id:** `"e3:" + base32(sha256(canonical JSON of the whole event, including sig))[:32]`. The id is content
  addressed: changing any byte changes the id, so two events cannot share one.
- **Message id = event id** of its `message.create`. A copy (`promoted_from`) is a new `message.create` with a new
  id and a `promoted_from` field, as today; the original id is not reused.

### 5.1 Kinds (first cut)

| kind | body | notes |
|---|---|---|
| `message.create` | `channel`, `content`, `thread_parent` (optional), `task_id` (optional), `promoted_from` (optional) | the only kind that creates a message |
| `message.edit` | `target` (event id of a message by the same author), `content` | only the author may edit; applied in `seq` order |
| `message.delete` | `target` (same author) | a tombstone: the message stays as "deleted by author" so replies still have a parent |
| `reaction.set` | `target`, `emoji`, `on` (bool) | replaces today's reactions rows; same convergence rule |
| `channel.topic` | `channel`, `topic` | last writer wins on `(ts, gateway)`; see §6 |
| `channel.create` | `channel`, `members` (optional) | channels stay identified by name, as today |
| `read.cursor` | `channel`, `through` (event id) | **optional, opt-in** — today read state is local-only (Track 2) |
| `key.rotate` | `new_gateway` (the new public key) | signed by the old key (§4) |

Kinds not listed are refused (fail closed), so an unknown kind from a newer peer is stored as "unverified, not
rendered" rather than guessed at.

## 6. Ordering and convergence

- **Per author:** events from one gateway apply in `seq` order. A gap (seq 1841 missing when 1842 arrives) is held,
  not applied, until the gap fills or a timeout asks the relay for the missing event.
- **Across authors:** no order is implied. A message is shown in `ts` order (for people) and in arrival order for
  pagination; neither is used to decide what wins.
- **Edits and deletes** apply only if their target was authored by the same gateway; otherwise they are dropped and
  the drop is recorded. A delete beats any later edit (tombstones are sticky).
- **Reactions:** the latest `reaction.set` per `(target, emoji, gateway)` by `seq` wins; this replaces today's
  rows without changing what people see.
- **Topic:** the latest `channel.topic` by `(ts, gateway)` wins. This is what Track 3 does with `topic_at` today.

## 7. Verification

A peer stores an event only when all of these hold:

1. `v == 3`, `kind` is known, `body` validates for that kind.
2. The signature verifies under `gateway` (the public key in the event itself).
3. `id` equals the content hash of the event.
4. `seq` is an integer no smaller than the author's last applied `seq` for a gap-free range.
5. **Equivocation:** if this peer already holds a *different* event for the same `(gateway, seq)`, both are kept, the
   author is flagged, and neither is applied past that point. A forked author cannot silently rewrite history.
6. Replays of an event already held are no-ops (the id is the key).

Relays do not need to be trusted for origin: rule 2 checks the author, whoever carried the event. The Herd secret still
authenticates the link, so a stranger cannot push events at all.

## 8. Migration from v2

v2 rows have no signature and their ids are not content-derived. The migration is additive and reversible.

**Phase 0 — prepare (no wire change).** Add the keypair, the `events` table (event id primary key, the raw event,
`gateway`, `seq`, `kind`), and a `legacy_ids(legacy_id → event_id)` map. Nothing is sent differently yet.

**Phase 1 — dual write.** Each gateway also writes a signed `message.create` for every message it authors from now
on, and sends both the legacy row and the event in one sync request (`"v": 2` payload plus an `"events"` array).
The legacy id is kept as the display key, so the desktop and the FTS index (Track 1) do not change. A v2 peer
ignores `events`. A v3 peer stores the event and maps the legacy id to it.

**Phase 2 — backfill own history.** A gateway signs its own existing messages as `message.create` events with
their original `ts` and an assigned `seq` range, and records them in `legacy_ids`. Signing history is allowed because
the local gateway authored it.

**Phase 3 — relayed history stays unverified.** A gateway cannot sign for another gateway's old rows. Those rows stay
as legacy rows with a permanent flag `origin: unverified-v2`. They are displayed, searchable and never used as the
basis of an edit or delete. This is the honest cost of migrating.

**Phase 4 — cutover.** Once every linked peer is at v3, a gateway may stop sending legacy rows for new messages. The
legacy read path is kept for one release. Rollback at any phase is "stop sending events"; the stored events are
ignored by v2 code and nothing is deleted.

Pairing (Track 5) already runs on a per-exchange MAC. In v3 the pairing exchange also carries each side's public
key, so the first contact establishes the identity that later events are checked against.

## 9. What it unblocks, and what it does not

Unblocked:
- **Edit and delete**, with tombstones every peer agrees on.
- **Read state across devices**, as an opt-in `read.cursor` event (today it is local, Track 2).
- **Audit:** each gateway's events form an append-only chain (`prev` = hash of the author's previous event, added to
  the event body in v3.1). A reader can prove an author did not reorder or drop events, given the chain.
- **Relay without trust:** origin is checked by signature, so mesh growth no longer depends on every link being
  honest.
- **More than five gateways** becomes a question of sync cost, not trust.

Not solved by this spec:
- **Deletion from peers that already synced.** A tombstone stops the message being shown; it cannot make a peer
  forget it. This must be stated in the UI as "deleted for everyone who syncs", not "erased".
- **A stolen key forges history** until rotation. Equivocation detection (§7.5) makes a fork visible; it does not
  prevent one.
- **Who may do what in a channel.** Still "any member". Roles are a separate decision.
- **Metadata.** Public keys are stable identifiers, so anyone in the mesh can link one person's events across channels.

## 10. Risks and decisions

**Decisions needed from Tyler before implementation:**

1. **Key storage:** door A (ask Hermes for a plugin secret-write API; blocks on the host) or door B (plugin data file,
   `0600`)?
2. **Crypto library:** Hermes's own environment already pins `cryptography` (its pyproject carries it, for PyJWT).
   Herd's README promises a stdlib-only runtime and its manifest declares no Python dependencies. Options: declare
   `cryptography` (a catalog change, and a new review surface), or a pure-Python Ed25519 from RFC 8032 (no new
   dependency, but a crypto implementation we would own and must test against the RFC vectors).
3. **Legacy rows:** accept that relayed v2 history is permanently "unverified" (§8 phase 3)?
4. **Does `gateway_id` change?** Deriving it from the key changes every existing identity once. Alternatively keep
   the random id and bind it to the key in a signed `identity` event.
5. **Read state:** keep it local forever (simpler, private), or make it a shared event?

**Technical risks:**

- *Implementation risk.* A hand-written Ed25519 or canonical-JSON encoder can be wrong in ways tests will not catch
  unless they use RFC 8032 vectors and a golden canonical-JSON corpus. Both are required, not optional.
- *Performance.* Verifying every event on a 3-second sync loop with a pure-Python signature check costs real CPU at
  five gateways. Measure before committing to the pure-Python path; batch verification or caching by event id helps.
- *Payload growth.* Each event adds a 43-character key, a 64-byte signature (86 characters base64url) and the id.
  For small messages the signature and key are a large share of each row, so sync payloads will grow noticeably. Not measured yet; measure it on the two-gateway harness before cutover.
- *Clock skew.* `ts` is shown, never ordered on, except for the topic tie-break. A skewed clock can only make a topic
  edit look older; it cannot reorder messages.
- *Migration bugs.* The dual-write window is where duplicates and gaps appear. The two-gateway harness
  (`scripts/qa/two_gateway_run.py`) must run v2 ↔ v3 pairs in both directions before cutover.

## 11. Test plan (for the implementation, not this document)

- Ed25519: RFC 8032 test vectors, plus wrong-key and malformed-signature rejections.
- Canonical JSON: a golden corpus including unicode, nested empty containers, and numbers at the edges.
- Ids: the same event always hashes to the same id; any changed byte changes it.
- Equivocation: two events for one `(gateway, seq)` are both kept and the author is flagged.
- Gaps: out-of-order arrival within an author is held and then applied in order.
- Edits and deletes: only by the author; delete beats a later edit; replays are no-ops.
- Migration: v2 ↔ v3 pairs both ways, through phase 0 → 4, with no lost or duplicated message; rollback at each phase.
- Adversarial: a relay that rewrites a body under the same id; a forged `gateway`; a truncated event; oversized fields.

## 12. Phases (estimate, after the §10 decisions)

| Phase | Scope | Rough size |
|---|---|---|
| 0 | keys, `events` table, canonical JSON, verification, RFC vectors | 2–3 days |
| 1 | dual write, sync payload `events`, equivocation and gap handling | 3–4 days |
| 2–3 | backfill own history, mark relayed history unverified | 1–2 days |
| 4 | cutover, edit/delete/reaction/topic as events, read state (opt-in) | 2–3 days |

These are sized for one careful engineer. They assume the §10.1 and §10.2 decisions are made first; the choice of
key storage and crypto library changes Phase 0 the most.
