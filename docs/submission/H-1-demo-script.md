# H-1 — Demo Video Script: Herd (v10, Nov 7 — new scope woven in under F-3 REVISED; H-6 apply pass)

**Constraints:** <90s on X, tag @NousResearch, hook in first 5s, one jaw-drop, zero dead air.
**Demo setup:** Tyler + wife's two Hermes instances on two Macs, side by side (split screen).
**Record: Nov 8 session (planned). Rehearse with Sentry first.** *The **Nov 8 freeze is CANCELLED** (F-3
REVISED): the video may be **re-recorded any time up to Nov 10** if a later feature makes a better 90
seconds — shots below are versioned so a re-take is a delta, not a rewrite.*
**Timings sum to ~79s, leaving ~11s buffer under the 90s cap (≤85s target held).**
**Base at prep:** `origin/main` @ `cd6d46c` (Nov 7). **The demo runs on the CURRENT build** — the old
two-Mac window ran 28 commits behind main and is not evidence (shots 3–5 must be re-verified on the build
you record). Every `herd.yaml` SHA reference is re-pinned at open and at each bump.

> **v10 change (Nov 7 — new scope woven in; F-3 REVISED):** **S-15** (status phrase, #41) and **S-16**
> (task badge, #46) are merged + QA-green, so both are now **IN** this script — S-15 ambient in shot 5,
> S-16 ambient at the end of shot 6. v9's shot-5 mention take, shot 5A reaction and the locked-constants
> block are unchanged; §2.4 donors were re-timed (shot 7 12→9s, shot 8 5→4s) to fund them. **S-13**
> (promote a DM, #37, protocol v2) is **merged and code-complete, but its 5s demo beat stays STAGED** in
> `docs/submission/H-6-new-scope-surfaces.md` §2.1: its F-3 gate (two-gateway TC-10.4 on **two real
> Macs**, F-3 B1) is being re-verified under Q-11 — add the beat only if that closes before recording,
> then re-time to ≤85s. Its rule-13 **disclosure** ships regardless (the behaviour is merged).

> **v9 change (H-1 final pass, Nov 6 — Foreman gate resolved):** the **@mention handoff is the
> primary shot-5 take, not a fallback.** Foreman's go/no-go is **GO** — TC-2 (two real gateways) passed
> on real hardware Nov 6 (Q-9, confirmed first-hand by Tyler), which was the stated precondition for
> S-7. The three surfaces it needs are all **merged and QA-green**: @-mention autocomplete **S-9 (#19)**,
> mention wake **S-7 (#13)**, and assignment context **S-14 (#33)**. v9 keeps the reaction beat (shot 5A,
> S-12 / #24), the locked-constants block and the threads-ambient-only ruling; it renames the old
> "5A baseline" take to **take 5-baseline** so "5A" means only the reaction.

## Shot-by-shot (v10, follows Northstar N-2 beats, PR #5)

| # | Time | Beat | Screen | VO / on-screen |
|---|------|------|--------|----------------|
| 1 | 0:00–0:05 | Two people, two Hermes | SPLIT: two Macs, Tyler and Brooklyn each at their own Hermes | **HOOK:** "Hermes is single-player. We made it multiplayer." |
| 2 | 0:05–0:13 | One step | Left Mac, Hermes desktop: Settings → Plugins → Herd → Add teammate | "Add Brooklyn:" paste her address and key (key masked), Save. One side is enough. |
| 3 | 0:13–0:20 | One step | Both screens, Herd pane | Brooklyn appears in `#general` on **both** screens. "That's it. Now they share a room." |
| 4 | 0:20–0:26 | Same room | Both screens | Tyler types "hey 👋" in `#general` → lands on the right instantly; Brooklyn replies → lands on the left. No VO, let it land. |
| 5 | 0:26–0:48 | **Handoff (jaw-drop) — @mention, PRIMARY** | Both screens, side by side | Tyler types `@` in `#general`; the **mention menu opens as he types `@brooklyn`** (hold ~2s, no VO). He picks her agent and sends the ask. Cut to Brooklyn's Mac: her agent **wakes with the assignment** (S-14) — who asked, which channel, how to answer. **Brooklyn approves its action on camera (one click)**; it works on her Mac and posts the result back to `#general`; the result lands on both screens. **S-15 ambient:** one phrase from the fixed vocabulary (reading the code / writing the code / reviewing / done / idle) sits beside her agent's in-flight work — if the take shows it cleanly, hold 2s when it flips to `done`. Call out nothing. VO: "He asks her agent. She says yes. Her agent, her machine." |
| 5A | 0:48–0:52 | **Reaction (S-12)** | Right, then LEFT | Brooklyn hovers her agent's result, the 4-emoji picker appears, she clicks **👍**, hard cut to the reaction landing **live on the left Mac**. No VO. |
| 6 | 0:52–1:06 | Back to him + humans stay in charge (N-2 beat 5) **+ S-16 badge** | Left, then DM views both sides, then wide | Tyler's agent reads the result and uses it. Tyler DMs Brooklyn — "nice 😄 it actually worked". **Last 2s (S-16):** the agent's answer carries a **task badge (id + title — Q-8 = YES, live DB read)**; Tyler clicks it → the `herd` board opens (**board-level**: the badge carries the task id; the card itself is **not** focused — PM ruling #47). One line: **"Every answer points back at the work."** Wide: "Two people. Two agents. One conversation." |
| 7 | 1:06–1:15 | Name it | Wide → end card | "Herd. Multiplayer Hermes." **(donor: 12→9s)** |
| 8 | 1:15–1:19 | End card | Static | Install one-liner + repo + @NousResearch **(donor: 5→4s)** |

**Total 79s** — 11s under the cap. If S-13's QA closes before recording, add its 5s beat
(after shot 6, `H-6 §2.1`) and re-time to ≤85s.

**Shot 5, primary take (record this):** as in the table above — the `@` menu glance, the mention that
wakes Brooklyn's agent with a real assignment, Brooklyn's on-camera approval, the result on her Mac. This
is the take the go/no-go picked. **Record the shot 5A reaction separately, on the same take**, so the two
glance beats do not compete.

**Shot 5, fallback take — "take 5-baseline" (record it too on Nov 8; use ONLY if the mention take flakes
live):** Tyler asks *his own* agent in Bot Chats to post the task to `#general`; Brooklyn tells her agent
to take it; she approves on camera; it posts back. No `@` menu, no wake — the v7 handoff, kept in the can
as the fallback of record.

**Threads (S-11): deliberate no-beat (H-5 decision).** No thread drill-down: it costs 5–8s and muddies
the one idea (shared channel). Threads may appear **ambiently only** (the "N replies" pill under a
message in shots 4–6 if a take naturally has replies). Never click into a thread on camera.

## Locked constants (Tyler-confirmed Nov 5, closed item)
```text
PEER_NAME     = Brooklyn                    # spelling locked; "Your name" setting on both Macs
PEER_ADDR     = Brooklyns-MacBook-Pro-3.local   # LAN .local address ON CAMERA is approved (Tyler)
                                  # if mDNS flakes on record day, swap to the LAN IP — swappable here only
PEER_KEY      = **** MASKED                 # never on camera: mask the Key field in the Add-teammate take
TASK          = "summarize the notes file on Brooklyn's desktop"   # must need HER Mac
```
Everything on screen is either this block or blurred. The Key field is the only masked value; the LAN
address renders unmasked as approved. If any value changes, edit only this block and re-render the
on-screen text.

**Setup facts (Smith, Nov 5):** only Tyler fills in Add teammate (Brooklyn's URL plus her
`API_SERVER_KEY`). Brooklyn's Mac needs `API_SERVER_ENABLED=true`, `API_SERVER_HOST=0.0.0.0` and
`API_SERVER_KEY` set, `hermes gateway` running, and Herd enabled. Set **"Your name"** in Herd settings on
both Macs, or the names default to the computer names. **Mention wake** additionally needs the Herd
setting **"Let my agent answer @mentions"** ON and `allow_gateway_injection: true` for `herd` in
`config.yaml` on Brooklyn's Mac, with a chat selected for it via `/herd-listen` — **set this up before the
take** (it is off by default). **Latency:** messages from Tyler to Brooklyn arrive almost instantly, but
messages from Brooklyn to Tyler can take up to about 3s because Herd polls. In shots 4–6, hold on the
left screen for 3s after Brooklyn or her agent posts, and never cut away early. **Reactions ride the same
sync, so from Brooklyn to Tyler the same up-to-3s poll applies: in shot 5A-reaction, hold on the left
screen until the 👍 lands.**

**Total 79s** (≤85s target, 90s cap; matches the shot table 0:00–1:19). Shot 5 gets the most time; trim shots 6–7 first if over.

**Task for shot 5 (must need *her* Mac):** "summarize the notes file on Brooklyn's desktop" or "what's on
Brooklyn's calendar Friday?". Never a task either agent could do alone.

**Word rules (N-2):** say channel / connect / her agent / his agent. Never say peer-to-peer, gateway,
fan-out, SQLite, **wake, inject, mention-wake, autocomplete, or poll**. Agent pills visible in every shot
from 5 on. Never narrate the reaction or the `@` menu: they are glance beats, silence is the point.

**Fallback:** if the mention take flakes live, cut in **take 5-baseline** for shot 5 (recorded Nov 8, or
Sentry's pre-recorded copy). If only the reaction take flakes, drop **shot 5A-reaction** (−4s; shots 6–8
each start 4s earlier, total ~75s). Shots 2–4 must be live. Never cut the hook or shots 2–4.

## Copy

**Post copy (short, punchy):**
> Hermes is single-player. We made it multiplayer. Herd is: channels and DMs where you, a teammate, and
> both of your agents work together across two machines. Built for the @NousResearch Hermes hackathon. 🐄

**Alt hooks (test at rehearsal; never pitch agent-to-agent, core Group Chat already does that):**
- "My wife and I just put our Hermes agents in the same channel." (Northstar's pick for the X post)
- "Watch one agent do a job on a computer it's never touched."

## Rehearsal checklist (for @sentry)
- [ ] **PREREQ — update the demo rig to the current build before anything else.** The live two-Mac
      SPINE window (QA Q-10 run log) ran a build **28 commits behind main**, so it did not exercise
      S-9's pick-tail fix (#36), S-12 reply-resurrection (#34), S-13 (#37), S-15 (#41) or S-16 (#46).
      Rehearse and record on the build you will actually show; re-verify shot 3 (peer visible), shot 4
      (fan-out), shot 5 (@mention) and the S-16 badge on it — a green old-build run is **not** evidence.
- [ ] Full dry run timed — MUST land ≤85s with natural pacing
- [ ] Settings > Plugins > Herd connect flow works on BOTH Macs from clean state (key field masked on screen)
- [ ] **Shot 5 mention (primary; S-9 #19 + S-7 #13 + S-14 #33): typing `@brooklyn` opens the mention
      menu, Enter picks the agent, the mention wake fires with the assignment context (who / which
      channel / how to answer), the agent answers with `herd_post`, and the reply lands on both Macs —
      3× in a row.** Needs "Let my agent answer @mentions" ON + `allow_gateway_injection` + `/herd-listen`
      on Brooklyn's Mac.
- [ ] Shot 5 fallback (take 5-baseline) also rehearsed and timed — no auto-reply, Brooklyn drives her agent
- [ ] **Shot 5A-reaction: 👍 lands on the left Mac within the 3s poll window, on camera, 3× in a row** (S-12, PR #24)
- [ ] **Thread "N replies" pill renders if a take naturally has replies: ambient only, never clicked** (S-11, PR #23)
- [ ] Network/latency checked on the home LAN — no visible stalls in the jaw-drop
- [ ] Screen recording at final resolution; captions legible at 100% zoom
- [ ] Key in demo command is masked/redacted on screen
- [ ] Backup: pre-recorded fallback of shot 5 (take 5-baseline) in case the live mention take flakes
- [ ] **S-16 badge (S-16 #46): click opens the `herd` board; badge shows id + title on both Macs within one sync cycle**
- [ ] **S-15 ambient status: the phrase flips to `done` and is legible; if it is not clean on the take, skip it — it is ambient, never narrated**
- [ ] Post copy reviewed; @NousResearch tag present

## Why shot 2 is the Settings form (v4)
`hermes peer add` / `hermes peer dm` are **core Hermes** (see `hermes peer` in the
Hermes CLI reference). Core already does cross-machine bot DMs from the terminal.
Showing that command would demo core, not Herd, and Sentry's Q-3 ruling strips
Herd's `hermes peer` reuse from the catalog build anyway. So shot 2 is Herd's own
connect form under Settings > Plugins > Herd. What Herd adds, and what the video must spend its seconds on: the
**shared channel in the desktop app** that both humans and both agents read and
post to. Shot 4 should be shot so it is obviously not a terminal DM.

## Open items
- ~~Northstar N-2 beats~~ fully integrated: beats 1–3 and 6 mapped to shots 1–2 and 7–8; beat 3 = jaw-drop shot 5; beat 5 (humans stay in charge) added to shot 6 DM moment. **Deliberate deviation on N-2 beat 4 (agents talk agent-to-agent): dropped — core Group Chat already does agent-to-agent, per Sentry CA-8; the video's differentiator is the human-in-charge approval on camera.** Word rules from N-2 applied. Real-latency rule applied to shot 4→5 handoff.
- ~~@mention auto-reply: Foreman go/no-go~~ **RESOLVED GO (Foreman, Nov 6):** TC-2 / Q-9 passed on two real Macs Nov 6 (confirmed first-hand by Tyler) — the stated precondition; S-7 (#13), S-9 (#19) and S-14 (#33) are merged and QA-green. **Shot 5 is now the @mention take as a first-class beat**; take 5-baseline is the fallback of record.
- ~~Shot 2 CLI vs in-app form~~ resolved: Settings form (Sentry Q-3, PR #8). Northstar: N-2 beat 2 and README "Setup with a teammate" should match
- ~~Smith surfaces~~ **verified via Q-9 (Nov 6):** two real gateways exchanged real messages — S-2 fan-out (shot 4), S-3 `herd_post` + `herd_read_channel` on two Macs (shot 5), Herd pane showing the registered peer (shot 3) all exercised. Confirm the exact on-camera `PEER_ADDR` value at rehearsal (constants block).
- ~~Confirm wife's instance name~~ CLOSED (Tyler, Nov 5): **Brooklyn**, locked in the constants block
- ~~v8 feature gates~~ S-12 (#24) and S-9 (#19) both merged + QA-green; S-9's round-1 findings were fixed in its merge. The "fall back to v7" clause is retired — the fallback is now take 5-baseline (± the reaction beat).
- **New-scope surfaces (S-13 promote, S-15 status line, S-16 Kanban link):** **S-15 (#41) and S-16 (#46) are merged + QA-green and are IN this script** (S-15 ambient in shot 5, S-16 badge at the end of shot 6). **S-13's 5s beat stays STAGED** in `docs/submission/H-6-new-scope-surfaces.md` §2.1 — merged (#37, protocol v2) but its F-3 gate (TC-10.4 on **two real Macs**) is open and being re-verified under Q-11; add it only if that closes before recording, then re-time to ≤85s (H-6 §2.5). **No cut or unmerged feature appears in this script.**
- **⚠️ Demo-rig build lag (QA SPINE run log, Nov 6):** the two-Mac window that passed TC-2 ran a
  build 28 commits behind main. The recording rig must be updated to the current build first;
  treat every fix merged after that old build (S-9 pick-tail + Shift+Enter #36, S-12 #34, S-13 #37,
  S-15 #41, S-16 #46) as **unverified on camera** until the rehearsal re-runs shots 3–5 and the S-16
  badge on the new build.
- Screenshots for H-2 package can be pulled from this same session
