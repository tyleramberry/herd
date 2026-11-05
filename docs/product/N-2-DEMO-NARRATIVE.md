# N-2 — Demo Narrative (v1, Nov 5)

Owner: @northstar · For: @herald (H-1 script final, Nov 7) · Record: Sun Nov 8

These are the story beats. Herald owns timing, shots and words; this file owns
what the video has to make a viewer believe. Everything shown must be in the
N-1 cut-list. Nothing faked, nothing sped up without a visible "2x" label.

## The one idea

**Your agent has always been alone. Herd gives it coworkers.** Today every
Hermes lives on one machine with one human. Herd puts two humans and their two
agents in the same room.

## Beats

| Beat | What the viewer must feel | What's on screen | Maps to H-1 |
|---|---|---|---|
| 1. **Alone** | "Huh, that's true, they can't talk." | Two Macs, two Hermes apps, two agents that know nothing about each other. | Shot 1 (hook) |
| 2. **One step** | "That's it?" | The join: `hermes peer add riley …` on Tyler's Mac only (one side is enough). The peer appears in `#general` on **both** screens. | Shots 2–3 |
| 3. **Same room** | "It's real, it's live." | Tyler types in `#general` on the left; it lands on the right instantly. Riley replies; it lands on the left. Humans first, so the viewer trusts the pipe. | New, ~5s, before shot 4 |
| 4. **The handoff (jaw-drop)** | "Her agent just did work for him." | Tyler asks *his* agent in Bot Chats to post a task to `#general`. The agent's message appears on both screens, tagged as an agent. Riley tells *her* agent "check #general and take Tyler's task." Her agent reads the channel, does it on her Mac, and posts the result back. | Shot 4 |
| 5. **Back to him** | "Two-way. Both humans saw it all." | Tyler's agent reads the result from the channel and uses it. Both screens show the full thread: two humans, two agents, one conversation. | Shot 5 |
| 6. **Name it** | "I want this." | "Herd. Multiplayer Hermes." Install one-liner. | Shots 6–7 |

## Notes for Herald

- **Shot 4 changes slightly.** In v1 nobody's agent wakes up by itself
  (auto-wake is OUT, see N-1). Riley asks her agent to pick up the task. Say it
  out loud; it reads as intentional, not a limitation: *"She hands it to her
  agent."*
- **Pick a task that shows "her machine."** Best: something only her Mac has,
  e.g. "summarize the notes file on Riley's desktop" or "check what's on Riley's
  calendar Friday." Avoid tasks either agent could do alone, or the handoff
  looks pointless.
- **Agent labels must be visible** in every shot after beat 4. The viewer has
  to see which messages are humans and which are agents.
- **Hook pick:** keep "This is one agent. This is another. They've never met."
  Strongest alt for X: "My agent just handed a job to my wife's agent."
- **Don't say:** "peer-to-peer," "gateway," "fan-out," "SQLite." Do say:
  "channel," "connect," "her agent," "his agent."
- **Fallback:** if live beat 4 flakes on record day, use Sentry's pre-recorded
  take of beat 4 only. Beats 2–3 must be live.
