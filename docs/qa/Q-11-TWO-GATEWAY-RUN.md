# Q-11 — reproducible two-gateway SPINE run (TC-2.1 / 2.2 / 2.3, three consecutive, S-16)

**Card:** Q-11 (`t_16d10f75`) · closes the evidence gaps Q-9 (`docs/qa/Q9-SPINE-RUNLOG.md` §7) left open.
**Recorded by:** smith — **2026-11-07, canonical run 14:09:35–14:09:41 MST** (21:09:35 UTC).
**Machine:** `Tylers-MacBook-Air-104.local` (macOS 26.6.2, arm64), Python 3.11.15 (gate venv `venv-q11`).
**Branch / head:** `q11-two-gateway-harness` @ `b69a9d03e99441c165d797ee60fa067fca00e1f9` (== `origin/main`);
the harness and this doc are the only additions (uncommitted).
**What kind of document this is:** this is a **reproducible run the recorder performed**. Anyone can
re-run it with one command (§1) and get the same rows. That is the opposite of Q-9 §5, which was a
recording of someone else's two-Mac run, backed up by gateway A's saved state.

---

## 0. Verdict summary (read this first)

| Question | Answer | Evidence in this run |
|---|---|---|
| **TC-2.1** A→B (human posts on A, B sees it, tagged with A's `gateway_id`) | **PASS ×3** | B's own backend returned each `q11-a2b-{1,2,3}` row exactly once, with `gateway_id=fd9ec989…` (A) and `gateway_name='q11-a'`. #1 arrived in **0.18 s** with no sync call from the driver. |
| **TC-2.2** B→A | **PASS ×3** | A's backend returned each `q11-b2a-{1,2,3}` exactly once, with `gateway_id=3fabd337…` (B) and `gateway_name='q11-b'`. #1 arrived in **2.00 s**, delivered by A's 3 s background loop (A's `last_attempt` moved 21:09:36.919 → 21:09:39.276). |
| **TC-2.3** agent on A posts with `herd_post`, human on B sees it | **PASS ×3** | B's rows have `author_type='agent'`, `author_name="q11-a's Hermes"` (same as the tool returned), A's `gateway_id`, and appear exactly once. |
| **Three consecutive, not once** (Q-11 row 5) | **PASS** | `Q-11.three-consecutive  12/12 #1/#2/#3 exchange rows landed`; `Q-11.no-duplicates  13 ids posted; every one held exactly once on A and on B`. |
| **S-16 payload** (`task_id`) | **PASS** | 3/3 `task_id`s arrive on B unchanged (`t_16d10f75`, `t_2f22ab63`, `t_810b8329`). A post with no `task_id` stays empty on both sides. A bad id is refused and nothing is written. A **pre-S-16 peer** (`27ee87c`) takes A's real payload without error or damage, and re-feeding it is idempotent. |
| Q-9 gap **1** — no B-side primary evidence | **CLOSED** | Every A→B row is asserted on what **B's own backend** returns (the data behind B's channel view), not on A's cursors. |
| Q-9 gap **3** — no three-consecutive capture | **CLOSED** | §3: 12 exchanges, each with its id, latency and the side it was read on. Run 3× back-to-back, all exit 0 (§2.6). |
| Q-9 gap **5** — TC-2.3 not evidenced | **CLOSED (with one caveat)** | 3 agent-authored posts land on B. Caveat: the post is written by the plugin's real `herd_post` handler called in-process, not by a live agent turn (§1.3, §7). |
| What this run still does **NOT** cover | **see §7** | One machine, two processes, loopback only (not two Macs on a LAN). No desktop UI rendering. No live agent turn. A stub stands in for the Hermes api_server adapter. This is not the frozen-SHA Q-4 rehearsal. |
| Relation to **Q-4** (`docs/qa/Q4-REHEARSAL-RUN-2026-11-07.md`, landed as #49 while this branch was open) | **complements, does not replace** | Q-4 already rehearsed the SPINE on this same SHA (`b69a9d0`) with two **live** `hermes` gateways — real api_server, real secret scope, restart persistence (TC-2.6), `last_error` empty. That is stronger than this harness on those axes and remains the run of record for them. What Q-4's table does **not** have: **TC-2.3 at all**, the **S-16 `task_id` payload** row, a **pre-change peer** check, or any script on `main` that reproduces the run. This run supplies those four, deterministically, in ~6 s. |

**One-line QA statement:** the SPINE (TC-2.1/2.2/2.3) passes three times in a row in each direction
between two real gateway processes, checked on the receiving side. The S-16 `task_id` field survives
the round trip, and a pre-S-16 peer accepts it safely. This is repeatable with one command. It
**complements** the two-Mac Q-4 run and the Q-4 clean-install rehearsal on the same SHA; it does not
replace either.

---

## 1. How to reproduce

### 1.1 Command

From the repo root (or anywhere, because `ROOT` comes from the script's own path):

```
# Python 3.11 with: pytest fastapi pyyaml httpx uvicorn aiohttp, plus the hermes-agent repo
# importable (for hermes_constants / agent.secret_scope). No other dependency.
P=<python>
env -u PYTHONPATH $P scripts/qa/two_gateway_run.py            # exit 0 = all PASS, 1 = any FAIL, 2 = a gateway didn't start
env -u PYTHONPATH $P scripts/qa/two_gateway_run.py --keep     # keep both temp homes + gateway logs (path on the last line)
env -u PYTHONPATH $P scripts/qa/two_gateway_run.py --old-peer-ref <REF>   # override the pre-S-16 ref (§1.4)
```

As run for this log (this machine, this session):

```
P=/Users/tyleramberry/.hermes/profiles/smith/cache/scratch/venv-q11/bin/python
```

`env -u PYTHONPATH` matters: this machine's shell exports a `PYTHONPATH` pointing at a different
interpreter's `site-packages`, which silently breaks `fastapi`/`aiohttp` imports inside the gateway
processes.

The driver itself imports only the standard library. A full run takes about **6 s** (5.5–6.0 s across
the seven runs in this session). Each run uses a fresh `mkdtemp` directory, so back-to-back runs don't
interfere.

### 1.2 Topology

| | gateway A (`q11-a`) | gateway B (`q11-b`) |
|---|---|---|
| Process | `two_gateway_run.py --gateway` (its own Python process) | same, separate process |
| Peer port (aiohttp `AppRunner`) | `/herd/v1/sync`, `/herd/v1/ping` via `herd._wire_api_server(peer_app, StubAdapter())`, plus the real 3 s `_start_sync_loop` → `_sync_pass` → `store.sync_all`; and `POST /harness/agent-post` (§1.3) | same |
| API port (uvicorn) | `plugin_api.router` mounted at `/api/plugins/herd` | same |
| SQLite | `<tmp>/a/herd.db` | `<tmp>/b/herd.db` |
| Own key (checked by `StubAdapter._check_auth`, `Bearer <key>`) | `KEY_A` | `KEY_B` |
| Peer settings (`store.SETTINGS_OVERRIDE`) | `peer_name=q11-b`, `peer_url=<B.peer>`, `__secrets__.HERD_PEER_KEY=KEY_B` | **none** (the README's one-sided link) |
| `HERMES_HOME` | `<tmp>/a/hermes-home` (keeps it away from the operator's `~/.hermes`) | `<tmp>/b/hermes-home` |

All four ports are free loopback ports picked by binding a real socket. B starts first, then A. The
driver waits until both `/status` and both own-key `/herd/v1/ping` return 200. The driver only
reaches the gateways over HTTP with stdlib `urllib`.

Canonical run: A api `127.0.0.1:59766`, peer `:59765`; B api `:59764`, peer `:59763`.

Because the link is one-sided, A is the only side that syncs. Each A pass **pushes** A's new rows
and **pulls** B's. B's own `POST /sync` does nothing (B has no peers). So TC-2.2 (B→A) can only
arrive through A: by A's background loop for #1, and by `POST {A.api}/sync` for #2/#3.

### 1.3 The one harness-only route: `POST /harness/agent-post`

`dashboard/plugin_api.py`'s `POST /channels/{id}/messages` always sets `author_type="human"` and
takes no `task_id`. That's deliberate: the desktop composer only ever posts as the human, and
letting an HTTP client **forge** an agent-authored message would be a product defect. This run does
**not** change it.

TC-2.3 and S-16 need a row **written through the agent path**. So `gateway_main()` adds one route to
the **harness's own** aiohttp app (the same app as the peer route, never in plugin code). It runs the
same own-key `StubAdapter._check_auth` check, then calls the plugin's **real agent tool handler**
in-process. That's the exact function Hermes calls for the `herd_post` tool:

```python
args = {"channel": body.get("channel") or "general", "content": body.get("content") or "",
        "task_id": body.get("task_id")}
out = await asyncio.to_thread(tools.herd_post, args)   # JSON string
return web.json_response({"tool_result": out})
```

**The writing step is the plugin's real agent handler, called in-process in gateway A. Every hop
between the gateways is real HTTP, the real 3 s sync loop and real SQLite. The backend composer
route stays human-only on purpose.** `tools.herd_post` makes its own message id, so for agent posts
the driver reads the id from the tool result (`message.id`).

### 1.4 How the pre-change ref is found (merge-base is NOT pre-change here)

This branch's merge-base with `origin/main` is `origin/main` itself (`b69a9d0`), which already has
S-16. So the reference harness's `merge-base` approach would test new code against new code and
prove nothing. The harness finds the ref like this instead:

1. `--old-peer-ref REF` if given. Otherwise
2. `git log --format=%H -S task_id -- dashboard/herd_store.py`, take the **oldest** hit (the commit
   that **introduced** `task_id`), then add `^`. On this branch the list has exactly one commit,
   `a20f742` ("S-16 (F4): an agent's answer links to the Kanban board (#46)"). That gives
   `a20f742^` = **`27ee87c`**. Taking the oldest hit, not `--max-count=1` (the newest), keeps this
   correct after later commits change how often `task_id` appears.
3. Fallback if git isn't available: `a20f742^`.
4. **Self-check:** if the fetched `herd_store.py` contains `task_id` anywhere, the row **FAILs** with
   `ref <ref> is not pre-change — it already knows task_id`. In this run the source had
   **0** occurrences and `PROTOCOL_VERSION = 2`.

---

## 2. Per-row evidence (real output, canonical run 14:09:35 MST)

Identities: **A.gateway_id = `fd9ec989326b44b9ae3945e1213af2c9`**, **B.gateway_id = `3fabd337e6ef4ca5923d83b62758ba5f`**.

```
== Q-11 two-gateway SPINE run ==
  root:    /Users/tyleramberry/herd/.worktrees/t_16d10f75
  workdir: /var/folders/xl/2_dzsc754nxcb_t9bbd6m3n40000gn/T/herd-q11-77o_oc29
  A (q11-a) api=http://127.0.0.1:59766  peer=http://127.0.0.1:59765
  B (q11-b) api=http://127.0.0.1:59764  peer=http://127.0.0.1:59763

  PASS  ENV.healthy  /status A=200 B=200; /herd/v1/ping A=200 B=200; A.gateway_id=fd9ec989326b44b9ae3945e1213af2c9 B.gateway_id=3fabd337e6ef4ca5923d83b62758ba5f v=2
  PASS  ENV.settings  A ping display_name='q11-a' (spawned as 'q11-a')
```

### 2.1 TC-2.1 — A→B (asserted on B)

```
  PASS  TC-2.1.A->B#1  id=q11-a2b-1 on q11-b: rows=1 gateway_id=fd9ec989326b gateway_name='q11-a' content_ok=True latency=0.18s sync=plugin-only (post HTTP 200)
  PASS  TC-2.1.A->B#2  id=q11-a2b-2 on q11-b: rows=1 gateway_id=fd9ec989326b gateway_name='q11-a' content_ok=True latency=0.02s sync=driver (post HTTP 200)
  PASS  TC-2.1.A->B#3  id=q11-a2b-3 on q11-b: rows=1 gateway_id=fd9ec989326b gateway_name='q11-a' content_ok=True latency=0.02s sync=driver (post HTTP 200)
  PASS  TC-2.1.A->B (3 consecutive)  landed=3/3 in-order-on-B=True
```

Each post goes to **A's own backend** (`POST /api/plugins/herd/channels/general/messages`, body
`{"id": "q11-a2b-i", "content": "Q-11 A->B exchange i"}`). The driver then polls **B's backend**
(`GET /channels/general/messages`) every 0.1 s, for up to 10 s. That's the same list B's channel
view reads, with no reload or refocus. Each check requires: exactly one row with that id,
`content` equal to what was posted, `gateway_id == A.gateway_id`, and `gateway_name == 'q11-a'`.
#1 had no driver `/sync`. It was delivered by the plugin's own post kicker (`post_message` →
`request_sync`).

### 2.2 TC-2.2 — B→A (asserted on A)

```
  PASS  TC-2.2.B->A#1  id=q11-b2a-1 on q11-a: rows=1 gateway_id=3fabd337e6ef gateway_name='q11-b' content_ok=True latency=2.00s sync=plugin-only (post HTTP 200)
  INFO  TC-2.2#1 delivered by A's background loop: A last_attempt 2026-11-07T21:09:36.919+00:00 -> 2026-11-07T21:09:39.276+00:00 (no driver /sync, no A-side post, B has no peer configured)
  PASS  TC-2.2.B->A#2  id=q11-b2a-2 on q11-a: rows=1 gateway_id=3fabd337e6ef gateway_name='q11-b' content_ok=True latency=0.04s sync=driver (post HTTP 200)
  PASS  TC-2.2.B->A#3  id=q11-b2a-3 on q11-a: rows=1 gateway_id=3fabd337e6ef gateway_name='q11-b' content_ok=True latency=0.02s sync=driver (post HTTP 200)
  PASS  TC-2.2.B->A (3 consecutive)  landed=3/3 in-order-on-A=True
```

The harness waits 0.5 s before TC-2.2#1. Without that wait, A's post kicker from TC-2.1#3 (it
sleeps 50 ms before syncing) was still pending. It picked up #1 in about 0.17 s, so the loop was
never tested. I confirmed this while building the harness: with a gap, the same B post took
2.12–2.33 s and A's `last_attempt` moved by one 3 s step. After the gap nothing on A is pending, so
#1 can only arrive through A's background loop. The `last_attempt` change above shows that pass.

### 2.3 TC-2.3 — agent on A → B (asserted on B)

```
  PASS  TC-2.3.agent->B#1  tool ok=True id=971f2e7d-f7d4-4b39-8a30-37e645e6031b on q11-b: rows=1 author_type='agent' author_name="q11-a's Hermes" gateway_id=fd9ec989326b content_ok=True latency=0.14s
  PASS  TC-2.3.agent->B#2  tool ok=True id=bc6089b9-4480-47fe-bc3f-567c7a7e01f2 on q11-b: rows=1 author_type='agent' author_name="q11-a's Hermes" gateway_id=fd9ec989326b content_ok=True latency=0.02s
  PASS  TC-2.3.agent->B#3  tool ok=True id=3699e0a7-8bac-4588-a5c7-6a521fd621ca on q11-b: rows=1 author_type='agent' author_name="q11-a's Hermes" gateway_id=fd9ec989326b content_ok=True latency=0.02s
  PASS  TC-2.3.agent->B (3 consecutive)  landed=3/3 in-order-on-B=True
```

The tool JSON was `{"ok": true, "message": {...}}` each time. B's row `author_name` matches the
tool's `author_name`. #1 had no driver `/sync`.

### 2.4 S-16 — `task_id` payload

```
  PASS  S-16.task_id#1  tool ok=True id=911d4a53-8022-44d6-b0e4-4137de0decc1 on q11-b: rows=1 author_type='agent' author_name="q11-a's Hermes" gateway_id=fd9ec989326b content_ok=True task_id='t_16d10f75' (posted 't_16d10f75') latency=0.01s
  PASS  S-16.task_id#2  tool ok=True id=196433b0-d814-4fea-b45b-09f8e49df208 on q11-b: rows=1 author_type='agent' author_name="q11-a's Hermes" gateway_id=fd9ec989326b content_ok=True task_id='t_2f22ab63' (posted 't_2f22ab63') latency=0.01s
  PASS  S-16.task_id#3  tool ok=True id=4aa810b9-de1a-467e-a51a-d102268b6a7d on q11-b: rows=1 author_type='agent' author_name="q11-a's Hermes" gateway_id=fd9ec989326b content_ok=True task_id='t_810b8329' (posted 't_810b8329') latency=0.01s
  PASS  S-16.task_id round-trip (3 consecutive)  landed=3/3 in-order-on-B=True
  PASS  S-16.task_id absent stays absent  id=e50f5330-bebc-4eab-b1af-0846ed09ea60 B.task_id=None A.task_id=None tool.task_id=None latency=0.01s
  PASS  S-16.bad task_id refused  tool={"ok": false, "error": "task_id must be a Kanban task id like 't_e7741438'."} A count 13->13 content seen on=[]
  INFO  pre-change ref a20f742d019f9ce1a7bc8689737cd830932327a6^ = 27ee87c; task_id occurrences in its herd_store.py: 0
  INFO  A's real export: HTTP 200, 13 rows; task-tied rows fed: [('911d4a53', 't_16d10f75'), ('196433b0', 't_2f22ab63'), ('4aa810b9', 't_810b8329')]
  PASS  S-16.pre-change peer ingests the new payload  ref=a20f742d019f9ce1a7bc8689737cd830932327a6^ (27ee87c) v=2 accepted=3 re-feed accepted=0 stored=3/3 task_id-column=False id/content/author_type verbatim, idempotent
  PASS  S-16.pre-change export_batch has no task_id key  3 rows exported by the pre-change module, 0 carry task_id (keys: ['author_name', 'author_type', 'channel_id', 'content', 'created_at', 'gateway_id', 'gateway_name', 'id', 'promoted_from', 'seq', 'thread_parent_id'])
```

How (d) works. The driver calls **A's own peer route** (`POST {A.peer}/herd/v1/sync`, body `{}`,
A's key) and gets A's real export: 13 rows plus `from` and `channels`. It keeps the three task-tied
rows and builds `{"v": 2, "from": …, "channels": …, "messages": [3 rows], "reactions": [],
"after_seq": 0, "after_rseq": 0}`. **Positive control:** before feeding, it checks that at least one
row has a non-empty `task_id` (all 3 did). It then loads `27ee87c:dashboard/herd_store.py` by path
with its own temp DB and `AUTO_SYNC=False`, and feeds a deep copy to `handle_peer_sync`.

Results: it returned a dict with `v=2` and `accepted=3`. Each row was stored exactly once, with
`id`, `content` and `author_type` unchanged. The pre-change `messages` table has **no** `task_id`
column. A second identical feed returned `accepted=0` and still exactly one row each. The
pre-change `export_batch` emits no `task_id` key, which shows the field really is new and an old
peer simply ignores it. The temp dir is deleted afterwards.

One harness detail: the pre-change module's `_notify` (desktop broadcast) is replaced with a no-op
in the driver process. It has no listener there and only logs a "dropped" traceback. Ingest and
export logic are untouched.

### 2.5 Roll-ups

```
  PASS  Q-11.three-consecutive  12/12 #1/#2/#3 exchange rows landed (TC-2.1, TC-2.2, TC-2.3, S-16.task_id)
  PASS  Q-11.no-duplicates  13 ids posted; every one held exactly once on A and on B
  PASS  SYNC.link-healthy  A->B connected=True last_error=''; B saw A 18 syncs
  ...
  25/25 checks passed (5.6s)
```

The 13 posted ids are the 12 exchanges plus the "absent" post. The bad-`task_id` post never got
an id because it was refused.

### 2.6 Repeatability (3× back-to-back plus the other runs this session, final harness code)

| Run | When (MST) | Exit | Result |
|---|---|---|---|
| back-to-back 1 | ~14:05:52 | 0 | `25/25 checks passed (5.9s)`; TC-2.2#1 2.29 s |
| back-to-back 2 | ~14:05:58 | 0 | `25/25 checks passed (5.8s)`; TC-2.2#1 2.25 s |
| back-to-back 3 | ~14:06:04 | 0 | `25/25 checks passed (5.5s)`; TC-2.2#1 2.12 s |
| after mutation restore | 14:06–14:09 | 0 | `25/25 checks passed (5.8s)` |
| `--keep` | ~14:09 | 0 | `25/25 checks passed (6.0s)`, last line `kept: /var/folders/…/herd-q11-77wlua5x` (contained `a/herd.db`, `b/herd.db`, `a.log`, `b.log`; deleted afterwards) |
| **canonical** | **14:09:35** | **0** | `25/25 checks passed (5.6s)`; TC-2.2#1 2.00 s |

(The "when" for the back-to-back runs comes from each run's own `last_attempt` UTC stamps.)

---

## 3. Three-consecutive table (canonical run)

| Exchange | Message id | Read on | Latency | How delivery was triggered | Result |
|---|---|---|---|---|---|
| TC-2.1.A->B#1 | `q11-a2b-1` | **B** | 0.18 s | none from the driver — A's post kicker | PASS |
| TC-2.1.A->B#2 | `q11-a2b-2` | **B** | 0.02 s | driver `POST {A.api}/sync` | PASS |
| TC-2.1.A->B#3 | `q11-a2b-3` | **B** | 0.02 s | driver `POST {A.api}/sync` | PASS |
| TC-2.2.B->A#1 | `q11-b2a-1` | **A** | 2.00 s | none from the driver — **A's 3 s background loop** (B has no peer) | PASS |
| TC-2.2.B->A#2 | `q11-b2a-2` | **A** | 0.04 s | driver `POST {A.api}/sync` | PASS |
| TC-2.2.B->A#3 | `q11-b2a-3` | **A** | 0.02 s | driver `POST {A.api}/sync` | PASS |
| TC-2.3.agent->B#1 | `971f2e7d-f7d4-4b39-8a30-37e645e6031b` | **B** | 0.14 s | none from the driver — A's post kicker | PASS |
| TC-2.3.agent->B#2 | `bc6089b9-4480-47fe-bc3f-567c7a7e01f2` | **B** | 0.02 s | driver `POST {A.api}/sync` | PASS |
| TC-2.3.agent->B#3 | `3699e0a7-8bac-4588-a5c7-6a521fd621ca` | **B** | 0.02 s | driver `POST {A.api}/sync` | PASS |
| S-16.task_id#1 (`t_16d10f75`) | `911d4a53-8022-44d6-b0e4-4137de0decc1` | **B** | 0.01 s | driver `POST {A.api}/sync` | PASS |
| S-16.task_id#2 (`t_2f22ab63`) | `196433b0-d814-4fea-b45b-09f8e49df208` | **B** | 0.01 s | driver `POST {A.api}/sync` | PASS |
| S-16.task_id#3 (`t_810b8329`) | `4aa810b9-de1a-467e-a51a-d102268b6a7d` | **B** | 0.01 s | driver `POST {A.api}/sync` | PASS |

Latency runs from just before the post request to the first poll that sees the row (polls every
0.1 s, so it is rounded up to the poll). Only the **#1** rows (no driver sync) show the latency a
user would actually see. The driver-triggered rows are sped up on purpose to keep the run short.

---

## 4. Sync state of both sides (canonical run)

```
  INFO  A /status peer: name=q11-b url=http://127.0.0.1:59763 remote_name=q11-b connected=True last_ok=2026-11-07T21:09:40.842+00:00 last_attempt=2026-11-07T21:09:40.836+00:00 last_error=''
  INFO  B /status incoming: gateway_id=fd9ec989326b44b9ae3945e1213af2c9 name=q11-a syncs=18 last_seen=2026-11-07T21:09:40.839+00:00 linked_back=False
  INFO  B /status peers configured: 0 (one-sided link)
  INFO  A has 13 rows in #general, B has 13 rows in #general
  INFO  A peer_state (after stop): {"url": "http://127.0.0.1:59763", "push_seq": 13, "pull_seq": 13, "remote_name": "q11-b", "last_ok": "2026-11-07T21:09:40.842+00:00", "last_error": ""}
```

- **A (linked side):** `connected=True`, `last_error=''`, and `last_ok` is current. That is the
  opposite of Q-9 §4's pre-#26 symptom (`last_ok` stale, `last_error="No key set for this peer."`).
  The background loop resolved the peer key and synced. `GET /status` does not show the cursors, so
  the harness reads A's `peer_state` from `a/herd.db` **after both gateways have stopped**:
  **`push_seq=13`, `pull_seq=13`**. Both sides hold 13 rows in `#general`, so both cursors are at
  the end.
- **B (one-sided):** no peers configured. It saw **18** incoming syncs from A
  (`gateway_id=fd9ec989…`). `linked_back=False` is correct for the README's one-sided link.
- **No manual reload on B:** every delivery was found by polling B's normal list endpoint. Nothing
  was restarted or refreshed on B.
- **Exchange #1 in each direction had no driver `/sync`:** TC-2.1#1 and TC-2.3#1 rode A's post
  kicker (`request_sync`). TC-2.2#1 rode A's **3 s background loop** (`last_attempt`
  21:09:36.919 → 21:09:39.276).

---

## 5. Mutation check (the harness can actually fail)

`dashboard/herd_store.py` was backed up first (`cp dashboard/herd_store.py /tmp/q11_store.bak`,
SHA-1 `fcb7e96653f0d12ebd3cf3173f7870a4f324e353`). Each mutation was applied, the harness was run,
and the file was restored with **`cp /tmp/q11_store.bak dashboard/herd_store.py`** (never
`git checkout`). The SHA-1 was back to `fcb7e966…` after every restore.

**M1 — `_valid_message`: `"task_id": _kanban().normalize_task_id(m.get("task_id")) or "",` → `"task_id": "",`** — exit **1**, `20/25 checks passed`:
```
  FAIL  S-16.task_id#1  tool ok=True id=75143cd7-ca08-4b05-949e-32bef2b02c75 on q11-b: rows=1 author_type='agent' author_name="q11-a's Hermes" gateway_id=8f116f7749e3 content_ok=True task_id=None (posted 't_16d10f75') latency=0.02s
  FAIL  S-16.task_id#2  … task_id=None (posted 't_2f22ab63') latency=0.01s
  FAIL  S-16.task_id#3  … task_id=None (posted 't_810b8329') latency=0.01s
  FAIL  S-16.task_id round-trip (3 consecutive)  landed=0/3 in-order-on-B=True
  FAIL  Q-11.three-consecutive  9/12 #1/#2/#3 exchange rows landed (TC-2.1, TC-2.2, TC-2.3, S-16.task_id)
```

**M2 — `_valid_message`: `"author_type": str(m.get("author_type") or "human"),` → `"author_type": "human",`** — exit **1**, `16/25 checks passed`:
```
  FAIL  TC-2.3.agent->B#1  tool ok=True id=3b9f805c-064f-45af-a1c5-a62c913d30d6 on q11-b: rows=1 author_type='human' author_name="q11-a's Hermes" gateway_id=a6d8805b4896 content_ok=True latency=0.32s
  FAIL  TC-2.3.agent->B#2  … author_type='human' …
  FAIL  TC-2.3.agent->B#3  … author_type='human' …
  FAIL  TC-2.3.agent->B (3 consecutive)  landed=0/3 in-order-on-B=True
  FAIL  S-16.task_id#1..#3  … author_type='human' … (task_id itself correct)
  FAIL  S-16.task_id round-trip (3 consecutive)  landed=0/3 in-order-on-B=True
  FAIL  Q-11.three-consecutive  6/12 #1/#2/#3 exchange rows landed (TC-2.1, TC-2.2, TC-2.3, S-16.task_id)
```

**M3 — `export_batch`: `rows = [dict(r) for r in examined if …]` → `rows = []`** — exit **1**, `4/24 checks passed (134.0s)`:
```
  FAIL  TC-2.1.A->B#1  id=q11-a2b-1 on q11-b: rows=0 gateway_id=None gateway_name=None content_ok=False latency=not within 10s sync=plugin-only (post HTTP 200)
  FAIL  TC-2.1.A->B#2 / #3, TC-2.1.A->B (3 consecutive)  landed=0/3 in-order-on-B=False
  FAIL  TC-2.2.B->A#1  id=q11-b2a-1 on q11-a: rows=0 gateway_id=None gateway_name=None content_ok=False latency=not within 10s sync=plugin-only (post HTTP 200)
  FAIL  TC-2.2.B->A#2 / #3, TC-2.2.B->A (3 consecutive)  landed=0/3 in-order-on-A=False
  FAIL  TC-2.3.agent->B#1..#3 (+ roll-up), S-16.task_id#1..#3 (+ roll-up), S-16.task_id absent stays absent
  FAIL  S-16.pre-change peer ingests the new payload  positive control failed: assembled payload has no row with a non-empty task_id (the check would prove nothing)
  FAIL  Q-11.three-consecutive  0/12 #1/#2/#3 exchange rows landed (TC-2.1, TC-2.2, TC-2.3, S-16.task_id)
  FAIL  Q-11.no-duplicates  ['q11-a2b-1:A=1,B=0', … 'd3cbca73-…:A=1,B=0']
```
(M3 has 24 rows, not 25, because the positive control stops (d) before its second row,
`export_batch has no task_id key`, runs.)

**Restore:** after M3, `git status --porcelain` showed only `?? SPEC.md` and
`?? scripts/qa/two_gateway_run.py`. The next run printed `25/25 checks passed (5.8s)`, exit 0.

---

## 6. Gates on this branch (verbatim, 2026-11-07 ~14:09 MST, harness present in the tree)

| Gate | Output |
|---|---|
| `env -u PYTHONPATH $P -m pytest tests/ -q` | `187 passed, 1 warning, 35 subtests passed in 8.16s` (baseline 187 / 35 — unchanged) |
| `cp desktop/plugin.js /tmp/q11_p.mjs && node --check /tmp/q11_p.mjs` | exit 0 |
| `node tests/s15_pane_render_probe.mjs` | `PROBE OK`, exit 0 (21 `ok` lines, 0 fail) |
| `node tests/s16_task_badge_render_probe.mjs` | `PROBE OK`, exit 0 (13 `ok` lines, 0 fail) |
| `env -u PYTHONPATH hermes plugins validate .` | `Validation passed.` (exit 0; no line mentions `two_gateway_run`) |
| `env -u PYTHONPATH hermes plugins doctor . --ci` | `OK: runtime discovery, manifest parsing, import, and registration passed` / `registrations: 4 tool(s), 0 hook(s)` |
| `env -u PYTHONPATH $P scripts/qa/catalog_audit.py .` | `catalog_audit: 0 FAIL, 0 WARN  (tools registered: ['herd_list_channels', 'herd_post', 'herd_read_channel', 'herd_set_status'])`. **Verified, not assumed:** run with `scripts/qa/two_gateway_run.py` in the tree, and no audit line mentions it. |

---

## 7. Gaps — what this run does NOT prove

1. **One machine, two processes, loopback.** Not two Macs, not a LAN, no mDNS or `.local` names, no
   firewall, no Wi-Fi. Q-9's real failure (Brooklyn's `:8642` refusing TCP) is a network problem
   this harness can't see. The two-Mac exchange on the frozen SHA is still **Q-4's** job.
2. **No desktop or UI rendering.** "B sees it" is checked on B's backend list endpoint, which feeds
   the pane, not on the rendered pane. The desktop push (`_notify` → `hermes_cli.plugin_events`)
   is **not** exercised. Each gateway log shows `plugin event plugin.herd.… dropped: no tui_gateway
   in this process` (29 tracebacks in A's log in a `--keep` run). Delivery here relies on polling,
   which the desktop also does as a backstop.
3. **No live agent turn.** The agent post is written by the plugin's real `tools.herd_post`
   handler, called in-process through the harness-only route (§1.3). No model, Hermes tool loop or
   `register()`/`ctx.register_tool` wiring is involved.
4. **Not the real Hermes api_server.** `StubAdapter` copies the `Bearer <API_SERVER_KEY>` check.
   The real adapter, its port, its middleware and multiplex secret scoping are not exercised.
   Settings and the peer key come from `store.SETTINGS_OVERRIDE`, not `config.yaml` or
   `agent.secret_scope`. That means the pre-#26 problem (no secret scope in the loop) **cannot
   show up here**. Its absence in this run is not proof of the #26 fix.
5. **The pre-change peer is checked in-process, not as a running gateway.** `27ee87c`'s
   `herd_store.py` is fed A's real export body directly (`handle_peer_sync`), not over HTTP from an
   old-build gateway process. Only the other direction is covered (new body → old peer). An old
   peer *pushing* to a new one is covered by the unit tests, not here.
6. **Only #1 latencies are realistic.** #2/#3 and all S-16 rows are sped up with a driver
   `POST {A.api}/sync`. TC-2.2#1's 2.0–2.3 s depends on where the 3 s loop happened to be, and can
   be anywhere from 0 to ~3 s.
7. **One-sided link only.** B has no peer configured (the README setup). A run where both sides
   link to each other is not covered.
8. **Failures are slow.** Every missing delivery waits the full 10 s timeout, so a broken build
   (M3) took **134.0 s** to report. A passing run takes about 6 s.
9. **Exit code 2 (a gateway fails to start) was not triggered** in this session. The code path
   prints both log tails and returns 2, but no run exercised it.
10. **Not the frozen build.** This is `b69a9d0` (`origin/main` at record time). F-3's freeze was
    cancelled (`618fe22`), so any later SHA needs a re-run. The point of this harness is that a
    re-run is one command.
11. **Not a substitute for Q-4's live-gateway rehearsal.** `docs/qa/Q4-REHEARSAL-RUN-2026-11-07.md`
    (Sentry, #49) ran the SPINE on this same SHA through two **live** `hermes` gateways: the real
    api_server and its middleware, the real `agent.secret_scope` binding for the background loop
    (`last_error` empty — the #26 signature absent), a restart that keeps history, and the redirect
    security probe. Those are exactly the axes §7.4 says this harness cannot see, so the live
    rehearsal stays the run of record for them. Keep both: Q-4 for "the installed product works",
    this harness for "the phone can be re-checked in 6 s after any sync-touching merge".

---

## 8. Sign-off

**smith — QA-selected evidence, 2026-11-07 14:09 MST** (canonical run 14:09:35–14:09:41 MST, exit 0, `25/25 checks passed`):

- **ENV.healthy, ENV.settings** — PASS
- **TC-2.1 A→B #1/#2/#3 + 3-consecutive** — PASS (asserted on B)
- **TC-2.2 B→A #1/#2/#3 + 3-consecutive** — PASS (asserted on A; #1 via A's 3 s loop)
- **TC-2.3 agent→B #1/#2/#3 + 3-consecutive** — PASS (agent post written by the real `herd_post` handler in-process; see §7.3)
- **S-16.task_id #1/#2/#3 + round-trip** — PASS
- **S-16.task_id absent stays absent** — PASS
- **S-16.bad task_id refused** — PASS
- **S-16.pre-change peer ingests the new payload** (`27ee87c`) — PASS
- **S-16.pre-change export_batch has no task_id key** — PASS
- **Q-11.three-consecutive (12/12), Q-11.no-duplicates (13 ids)** — PASS
- **SYNC.link-healthy** — PASS
- **Mutation check M1/M2/M3** — each turned its target rows FAIL (exit 1); restored byte-for-byte; re-run PASS.

Not signed here: the two-Mac live exchange and the frozen-SHA rehearsal (Q-4), and desktop rendering.
