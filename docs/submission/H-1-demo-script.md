# H-1 — Demo Video Script: Herd (DRAFT v2, Nov 5)

**Constraints:** <90s on X, tag @NousResearch, hook in first 5s, one jaw-drop, zero dead air.
**Demo setup:** Tyler + wife's two Hermes instances on two Macs, side by side (split screen).
**Record date: Nov 8 — code freeze. Rehearse with Sentry before recording.**
**All timings sum to ~78s, leaving ~10s buffer under the 90s cap.**

## Shot-by-shot

| # | Time | Screen | VO / on-screen |
|---|------|--------|----------------|
| 1 | 0:00–0:05 | SPLIT: two Macs, two desktop apps | **HOOK:** "This is one agent. This is another. They've never met." (pause — no dead air, beat is intentional) |
| 2 | 0:05–0:15 | Left Mac, terminal | "Hermes connects them with one command:" on-screen: `hermes peer add riley --url <gateway-url> --key ****` |
| 3 | 0:15–0:25 | Left desktop app, Herd pane | Herd picks up the peer — it appears in the channel member list. "Hermes already lets gateways peer. Herd turns that into a shared room." |
| 4 | 0:25–0:45 | Both screens, side by side | **THE JAW-DROP:** Tyler types a task into a Herd channel; it appears on *her* screen too, her agent picks it up, does the work on her Mac, and posts the result back into the same channel (via `herd_post_message`). "Her agent did the work. On her machine. We both watched." |
| 5 | 0:45–0:60 | Right Mac | Wife replies / pushes a result back; Tyler's agent receives it. Two-way, both humans see the same thread. |
| 6 | 0:60–0:75 | Wide, both Macs | "Herd — multiplayer Hermes. Channels and DMs where humans and their agents work together across machines." |
| 7 | 0:75–0:78 | End card | On-screen: repo/install one-liner + @NousResearch tag |

## Copy

**Post copy (short, punchy):**
> Two Macs. Two Hermes agents. One command to connect them — then they just… work together. Herd is multiplayer Hermes: channels + DMs for humans and agents across machines. Built for the @NousResearch Hermes hackathon. 🐄

**Alt hooks (test at rehearsal):**
- "My agent just hired my wife's agent."
- "Watch one agent do a job on a computer it's never touched."

## Rehearsal checklist (for @sentry)
- [ ] Full dry run timed — MUST land ≤85s with natural pacing
- [ ] `hermes peer add` join flow works on BOTH Macs from clean state
- [ ] Network/latency checked on the home LAN — no visible stalls in the jaw-drop
- [ ] Screen recording at final resolution; captions legible at 100% zoom
- [ ] Key in demo command is masked/redacted on screen
- [ ] Backup: pre-recorded fallback of shot 4 in case live demo flakes
- [ ] Post copy reviewed; @NousResearch tag present

## Why the framing changed in v2
`hermes peer add` / `hermes peer dm` are **core Hermes** (see `hermes peer` in the
Hermes CLI reference). Core already does cross-machine bot DMs from the terminal.
If the video credits Herd for the one-command join, judges who know Hermes will
notice. What Herd adds, and what the video must spend its seconds on: the
**shared channel in the desktop app** that both humans and both agents read and
post to. Shot 4 should be shot so it is obviously not a terminal DM.

## Open items
- **Northstar (N-2):** confirm the "what Herd adds over core peer DMs" line; it drives shots 3–6
- **Smith:** shot 4 needs S-2 (fan-out) + S-3 (agent posts to channel) working on two real Macs; shot 3 needs S-4 (Herd UI showing registered peers)
- Confirm gateway URL + API_SERVER_KEY handling for the two-Mac demo (Foreman/Smith)
- Confirm wife's instance name for the script (`riley` placeholder)
- Screenshots for H-2 package can be pulled from this same session
