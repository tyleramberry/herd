# H-1 — Demo Video Script: Herd (DRAFT v7, Nov 6)

**Constraints:** <90s on X, tag @NousResearch, hook in first 5s, one jaw-drop, zero dead air.
**Demo setup:** Tyler + wife's two Hermes instances on two Macs, side by side (split screen).
**Record date: Nov 8 — code freeze. Rehearse with Sentry before recording.**
**Timings sum to ~83s, leaving ~7s buffer under the 90s cap (≤85s target held).**

> **v7 change (H-5):** adds reactions + @-autocomplete from PRs #24 (S-12) and #19 (S-9); threads (PR #23, S-11) stay ambient only. Verified against the actual PR trees Nov 6: reactions are a 4-emoji hover picker (👍 ❤️ 👁️ 🎉) that syncs via the reaction cursor (`after_rseq`) — i.e. it lands on the other Mac in real time, which is why it earns its 3 seconds; @-autocomplete is a mention-suggestion menu that opens as you type `@` (arrow keys to move, Enter/Tab to pick); threads render as a "N replies" summary pill under a message plus an inline thread pane — **no sidebar**, so the v5-era "ambient sidebar" idea is replaced by the reply-count pill. **Fallback of record remains v6** if S-12 or S-9 fails QA before Nov 8.

## Shot-by-shot (v7, follows Northstar N-2 beats, PR #5)

| # | Time | Beat | Screen | VO / on-screen |
|---|------|------|--------|----------------|
| 1 | 0:00–0:05 | Two people, two Hermes | SPLIT: two Macs, Tyler and Brooklyn each at their own Hermes | **HOOK:** "Hermes is single-player. We made it multiplayer." |
| 2 | 0:05–0:13 | One step | Left Mac, Hermes desktop: Settings → Plugins → Herd → Add teammate | "Add Brooklyn:" paste her address and key (key masked), Save. One side is enough. |
| 3 | 0:13–0:20 | One step | Both screens, Herd pane | Brooklyn appears in `#general` on **both** screens. "That's it. Now they share a room." |
| 4 | 0:20–0:26 | Same room | Both screens | Tyler types "hey 👋" in `#general` → lands on the right instantly; Brooklyn replies → lands on the left. No VO, let it land. |
| 5 | 0:26–0:50 | **Handoff (jaw-drop)** | Both screens, side by side | Tyler asks *his* agent in Bot Chats to post a task to `#general`; it appears on both screens with an `agent` pill. Brooklyn: "check #general and take Tyler's task." Her agent reads the channel; **Brooklyn approves its action on camera (one click)**; it does the work on her Mac and posts the result back. VO: "She hands it to her agent. Her agent, her machine, her say." |
| 5A | 0:50–0:53 | **Reaction (new, S-12)** | Right, then LEFT | Brooklyn hovers her agent's result message, the 4-emoji picker appears, she clicks **👍** — hard cut to the reaction landing **live on the left Mac**. No VO. "It's real" in one gesture. |
| 6 | 0:53–0:63 | Back to him | Left, then wide | Tyler's agent reads the result from the channel and uses it. Wide: one thread, two humans, two agents. "Two people. Two agents. One conversation." |
| 7 | 0:63–0:75 | Name it | Wide → end card | "Herd. Multiplayer Hermes." |
| 8 | 0:75–0:80 | End card | Static | Install one-liner + repo + @NousResearch |

**Shot 5, two takes (record both Nov 8; the go/no-go picks one):**
- **5A (baseline, no auto-reply):** as in the table above. Brooklyn tells her agent to take the task; she approves; it posts back.
- **5B (if S-9 ships):** Tyler types `@` in the composer — the **mention-suggestion menu opens as he types `@brooklyn`** (hold the popup ~2s, no VO, one glance: the wake is discoverable, not magic). He picks Brooklyn's agent from the menu with Enter and hits send. Her agent wakes on the mention, Brooklyn approves on camera, and it does the work on her Mac and posts back. VO: "He asks her agent. She says yes. Her agent, her machine." 5B runs about 4s shorter than 5A; give that time to shots 5A(reaction) and 6.

**Threads (S-11) — deliberate no-beat (H-5 decision):** no thread drill-down beat; it costs 5–8s and muddies the one idea (shared channel). Threads may appear **ambiently only**: the "N replies" pill under a message in shots 4–6 if naturally present in a take. Do not click into a thread on camera.

**Constants handling (masked-or-swappable, unchanged from v6):** PEER_NAME constant — spelling call needed before Nov 7 rehearsal: the gateway hostname suggests "Brooklyn"; Tyler to confirm via Foreman. TEAMMATE_ADDR + TEAMMATE_KEY stay masked on camera (form field blurred in the Add-teammate take; the constant block swap covers any change). No beat depends on unmasked values.

**Setup facts (Smith, Nov 5):** only Tyler fills in Add teammate (Brooklyn's URL plus her `API_SERVER_KEY`). Brooklyn's Mac needs `API_SERVER_ENABLED=true`, `API_SERVER_HOST=0.0.0.0` and `API_SERVER_KEY` set, `hermes gateway` running, and Herd enabled. Set **"Your name"** in Herd settings on both Macs, or the names default to the computer names. **Latency:** messages from Tyler to Brooklyn arrive almost instantly, but messages from Brooklyn to Tyler can take up to about 3s because Herd polls. In shots 4–6, hold on the left screen for 3s after Brooklyn or her agent posts, and never cut away early. **Reactions ride the same sync as messages, but from Brooklyn to Tyler the same up-to-3s poll applies — in shot 5A, hold on the left screen until the 👍 lands; do not cut away.**

**Total ~83s** (≤85s target, 90s cap). Shot 5 gets the most time; trim shots 6–7 first if over.

**Task for shot 5 (must need *her* Mac):** "summarize the notes file on Brooklyn's desktop" or "what's on Brooklyn's calendar Friday?". Never a task either agent could do alone.

**Word rules (N-2, unchanged):** say channel / connect / her agent / his agent. Never say peer-to-peer, gateway, fan-out, SQLite. Agent pills visible in every shot from 5 on. Never narrate the reaction or the autocomplete — they are glance beats, silence is the point.

**Fallback:** if shot 5 flakes live, cut in Sentry's pre-recorded take of shot 5 only. Shots 2–4 must be live. **If S-12 or S-9 is not merged and QA-green by the Nov 8 record: revert to v6 as the fallback of record** (drop shot 5A and the autocomplete beat; timings return to v6's ~80s).

## Copy

**Post copy (short, punchy):**
> Hermes is single-player. We made it multiplayer. Herd is: channels and DMs where you, a teammate, and both of your agents work together across two machines. Built for the @NousResearch Hermes hackathon. 🐄

**Alt hooks (test at rehearsal; never pitch agent-to-agent, core Group Chat already does that):**
- "My wife and I just put our Hermes agents in the same channel." (Northstar's pick for the X post)
- "Watch one agent do a job on a computer it's never touched."

## Rehearsal checklist (for @sentry)
- [ ] Full dry run timed — MUST land ≤85s with natural pacing
- [ ] Settings > Plugins > Herd connect flow works on BOTH Macs from clean state (key field masked on screen)
- [ ] **Shot 5A reaction: 👍 lands on the left Mac within the 3s poll window, on camera, 3× in a row** (S-12, PR #24)
- [ ] **Shot 5B autocomplete: mention menu opens while typing `@brooklyn`, Enter picks, mention wake fires — 3× in a row on both Macs** (S-9, PR #19, Foreman go/no-go)
- [ ] **Thread "N replies" pill renders if a take naturally has replies — ambient only, never clicked** (S-11, PR #23)
- [ ] Network/latency checked on the home LAN — no visible stalls in the jaw-drop
- [ ] Screen recording at final resolution; captions legible at 100% zoom
- [ ] Key in demo command is masked/redacted on screen
- [ ] Backup: pre-recorded fallback of shot 4 in case live demo flakes
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
- ~~Northstar N-2 beats~~ merged (PR #5); v5 adds the people-first hook and Brooklyn's on-camera approval (core Group Chat already does agent-to-agent, Sentry CA-8)
- **@mention auto-reply: Foreman go/no-go Fri Nov 6 noon** (ships only if it works 3× in a row on both Macs). Record shot 5 both ways on Nov 8 (5A and 5B below).
- ~~Shot 2 CLI vs in-app form~~ resolved: Settings form (Sentry Q-3, PR #8). Northstar: N-2 beat 2 and README "Setup with a teammate" should match
- **Smith:** shot 4 needs S-2 fan-out; shot 5 needs S-3 `herd_post` + `herd_read_channel` working on two real Macs; shot 3 needs Herd UI showing registered peers
- **v7 (H-5):** shot 5A reaction needs S-12 merged + QA-green (PR #24); shot 5B autocomplete needs S-9 merged + QA-green (PR #19). Both were open, in QA, as of Nov 6. Threads (S-11, PR #23) is ambient-only and NOT record-blocking.
- Confirm gateway URL + API_SERVER_KEY handling for the two-Mac demo (Foreman/Smith)
- **PEER_NAME spelling call ("Brooklyn"?) before Nov 7 rehearsal** (Tyler via Foreman)
- Screenshots for H-2 package can be pulled from this same session
