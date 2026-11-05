# H-1 — Demo Video Script: Herd (DRAFT v4, Nov 5)

**Constraints:** <90s on X, tag @NousResearch, hook in first 5s, one jaw-drop, zero dead air.
**Demo setup:** Tyler + wife's two Hermes instances on two Macs, side by side (split screen).
**Record date: Nov 8 — code freeze. Rehearse with Sentry before recording.**
**Timings sum to ~80s, leaving ~10s buffer under the 90s cap.**

## Shot-by-shot (v3, follows Northstar N-2 beats, PR #5)

| # | Time | Beat | Screen | VO / on-screen |
|---|------|------|--------|----------------|
| 1 | 0:00–0:05 | Alone | SPLIT: two Macs, two Hermes apps | **HOOK:** "This is one agent. This is another. They've never met." |
| 2 | 0:05–0:13 | One step | Left Mac, Hermes desktop: Settings > Plugins > Herd | "Connect them:" paste Riley's URL and key (key field masked), Save. One screen, no terminal. |
| 3 | 0:13–0:20 | One step | Both screens, Herd pane | Riley appears in `#general` on **both** screens. "That's it. Now they share a room." |
| 4 | 0:20–0:26 | Same room | Both screens | Tyler types "hey 👋" in `#general` → lands on the right instantly; Riley replies → lands on the left. No VO, let it land. |
| 5 | 0:26–0:50 | **Handoff (jaw-drop)** | Both screens, side by side | Tyler asks *his* agent in Bot Chats to post a task to `#general`; it appears on both screens with an `agent` pill. Riley: "check #general and take Tyler's task." Her agent reads the channel, does it **on her Mac**, posts the result back. VO: "She hands it to her agent. Her agent did the work, on her machine." |
| 6 | 0:50–0:62 | Back to him | Left, then wide | Tyler's agent reads the result from the channel and uses it. Wide: one thread, two humans, two agents. "Two people. Two agents. One conversation." |
| 7 | 0:62–0:75 | Name it | Wide → end card | "Herd. Multiplayer Hermes." |
| 8 | 0:75–0:80 | End card | Static | Install one-liner + repo + @NousResearch |

**Total ~80s** (≤85s target, 90s cap). Shot 5 gets the most time; trim shots 6–7 first if over.

**Task for shot 5 (must need *her* Mac):** "summarize the notes file on Riley's desktop" or "what's on Riley's calendar Friday?". Never a task either agent could do alone.

**Word rules (N-2):** say channel / connect / her agent / his agent. Never say peer-to-peer, gateway, fan-out, SQLite. Agent pills visible in every shot from 5 on.

**Fallback:** if shot 5 flakes live, cut in Sentry's pre-recorded take of shot 5 only. Shots 2–4 must be live.

## Copy

**Post copy (short, punchy):**
> My agent just handed a job to my wife's agent. Herd is multiplayer Hermes: channels and DMs where you, a teammate, and both of your agents work together across two machines. Built for the @NousResearch Hermes hackathon. 🐄

**Alt hooks (test at rehearsal):**
- "My agent just handed a job to my wife's agent." (Northstar's pick for the X post)
- "Watch one agent do a job on a computer it's never touched."

## Rehearsal checklist (for @sentry)
- [ ] Full dry run timed — MUST land ≤85s with natural pacing
- [ ] Settings > Plugins > Herd connect flow works on BOTH Macs from clean state (key field masked on screen)
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
- ~~Northstar N-2 beats~~ merged into v3 (PR #5)
- ~~Shot 2 CLI vs in-app form~~ resolved: Settings form (Sentry Q-3, PR #8). Northstar: N-2 beat 2 and README "Setup with a teammate" should match
- **Smith:** shot 4 needs S-2 fan-out; shot 5 needs S-3 `herd_post` + `herd_read_channel` working on two real Macs; shot 3 needs Herd UI showing registered peers
- Confirm gateway URL + API_SERVER_KEY handling for the two-Mac demo (Foreman/Smith)
- Confirm wife's instance name for the script (`riley` placeholder)
- Screenshots for H-2 package can be pulled from this same session
