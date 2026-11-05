# N-3 — Naming & Copy Pass (v1, Nov 5)

Owner: @northstar · For: @herald (H-2 catalog entry), @smith (README, plugin.yaml, UI strings)

## Name

- **Herd** (plugin id `herd`). Keep it. Short, memorable, a group of animals
  that moves together, fits the Hermes/Nous animal-adjacent vibe. 🐄 is fine on
  X, not in the catalog entry.
- Tagline: **Multiplayer Hermes.** Use it everywhere, same two words.

## Catalog entry (for H-2 `herd.yaml`)

```yaml
title: Herd
description: >-
  Multiplayer Hermes. Share a channel with a teammate on their own machine,
  and bring both your agents. Group Chat connects your bots; Herd connects
  people.
```

Why: it leads with the tagline, answers the Group Chat question in one line
(Q-3 CA-8), and is honest that v1 is two people on two machines.

**"What Herd adds" line for the H-2 PR description:**
> Core Group Chat and `hermes peer dm` connect one person's bots across their
> machines. Herd connects two people: each keeps their own Hermes, credentials
> and approvals, and both humans and both agents share one persistent channel.

## plugin.yaml description (for Smith)

`Channels and DMs shared between two Hermes gateways, for humans and agents.`

## Agent tool descriptions (what the model reads; for Smith, S-3)

- `herd_list_channels` — "List Herd channels and DMs this Hermes can see, with
  their ids and member names."
- `herd_post` — "Post a message to a Herd channel or DM. Everyone in it,
  including people and agents on the other machine, will see it. Use for
  sharing results or handing off a task."
- `herd_read_channel` — "Read recent messages from a Herd channel or DM,
  newest last. Use before replying or when asked to pick up a task from a
  channel."

## UI strings (for Smith)

| Where | Copy |
|---|---|
| Pane title | Herd |
| Sidebar sections | Channels · Direct messages |
| Empty: no peers | **Nobody here yet.** Connect a teammate's Hermes to start a channel together. |
| Empty: channel | **No messages yet.** Say hi, or ask your agent to post here. |
| Composer placeholder | Message #{channel} |
| Agent badge | `agent` (small pill next to the name, theme vars only) |
| Peer unreachable | **Can't reach {peer}.** Messages will send when they're back. *(only if queued; otherwise: "Messages won't send until they're back.")* |
| New channel button | New channel |
| New DM button | New message |
| Add teammate button | Add teammate |
| Add teammate form | Name · Their Hermes address · Key · **Connect** |

## README polish (suggestions for Smith, apply by Nov 7)

1. First line: `# Herd — multiplayer Hermes`, then one sentence:
   "Channels and DMs where you, a teammate, and both of your Hermes agents
   work together across two machines."
2. Add a **"What it does"** list of exactly four bullets matching N-1 IN #1–5
   (channels, connect a peer, agents post and read, DMs).
3. Add a GIF or screenshot from the Nov 8 recording right under the intro.
4. Add a **"What it doesn't do (yet)"** line linking the backlog. Judges trust
   honest scope.
5. Add the **rule-13 disclosures** section from H-2 verbatim (Sentry's Q-3
   needs README and PR description to match).
6. Replace "Under active construction. See `docs/` for architecture." with a
   status line once SPINE is green.
7. Replace the "Setup with a teammate" `hermes peer add` block with: "Open Settings → Plugins →
   Herd → **Add teammate**, paste their gateway address and key. One side is
   enough." (Herd no longer uses core peers, Q-3 CA-4.)
8. Add a one-line **"How is this different from Group Chat?"** using the
   "What Herd adds" line above.
