# H-1 — Demo Video Script: Herd (DRAFT v1, Nov 5)

**Constraints:** <90s on X, tag @NousResearch, hook in first 5s, one jaw-drop, zero dead air.
**Demo setup:** Tyler + wife's two Hermes instances on two Macs, side by side (split screen).
**Record date: Nov 8 — code freeze. Rehearse with Sentry before recording.**
**All timings sum to ~78s, leaving ~10s buffer under the 90s cap.**

## Shot-by-shot

| # | Time | Screen | VO / on-screen |
|---|------|--------|----------------|
| 1 | 0:00–0:05 | SPLIT: two Macs, two desktop apps | **HOOK:** "This is one agent. This is another. They've never met." (pause — no dead air, beat is intentional) |
| 2 | 0:05–0:15 | Left Mac, terminal | "I connect them with one command:" on-screen: `hermes peer add riley --url <gateway-url> --key ****` |
| 3 | 0:15–0:25 | Left desktop app, channel UI | Join flow lands in the app — peer appears in the channel. "No config files. No pairing dance. One command." |
| 4 | 0:25–0:45 | Both screens, side by side | **THE JAW-DROP:** Tyler types a task into the channel; wife's Hermes agent picks it up and executes on *her* Mac — output streams back live. "Her agent did the work. On her machine." |
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

## Open items
- Confirm gateway URL + API_SERVER_KEY handling for the two-Mac demo (Foreman/Smith)
- Confirm wife's instance name for the script (`riley` placeholder)
- Screenshots for H-2 package can be pulled from this same session
