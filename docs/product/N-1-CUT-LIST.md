# N-1 — Locked Cut-List (v1, Nov 5)

Owner: @northstar · Locked: Thu Nov 5, 2026 · Applies through submission (Nov 11, 5 PM EST)

This file is the scope-creep yardstick. If a feature is not in **IN**, it does
not get built before Nov 11. Changing this list needs Tyler's OK in writing.

The one-sentence product: **Herd is multiplayer Hermes — channels and DMs where
humans and their Hermes agents work together across two machines, inside the
Hermes desktop app.**

---

## IN (ship by freeze, Nov 8)

| # | Feature | "Done" means | Owner | Board |
|---|---|---|---|---|
| 1 | **Channels** | Create a channel, see a channel list, open one, read history, post. Stored in the plugin's SQLite (channels, messages, participants). One default channel, `general`, exists on first run. | Smith | S-1, S-4 |
| 2 | **Two-gateway fan-out** | A message posted on gateway A shows up in the same channel on gateway B without a reload, and the reverse. Exactly **two** gateways. Polling is an acceptable transport if push isn't ready. | Smith | S-2 (SPINE) |
| 3 | **Add a teammate** | An **Add teammate** form (Settings → Plugins → Herd; final placement is Smith's call) (name, gateway URL, key). The key is a Herd-declared secret, read via `get_secret`, never core's `HERMES_PEER_*` keys or `bot_peers` (Sentry ruling, Q-3 CA-4). Adding on one side connects both directions. After it, the teammate shows as a participant. | Smith | S-4 |
| 4 | **Agents post and read** | Three agent tools, registered via `plugin.yaml`: `herd_list_channels`, `herd_post`, `herd_read_channel`. Agent messages are labeled as agent-authored (`author_type=agent`) so humans can tell who said what. | Smith | S-3 |
| 5 | **DMs** | A DM is a channel with exactly two participants and a `dm` flag. No separate data model, no separate sync path. Shows in its own "Direct messages" section of the list. | Smith | S-4 |
| 6 | **Empty and error states** | Empty channel list, empty channel, peer unreachable. Plain copy, no stack traces. | Smith | S-1, S-5 |
| 7 | **Two-way teammate visibility** *(added Nov 5, Tyler live-feedback)* | If only one side registered a teammate, the other side's pane shows a clear one-step fix, not "no teammate connected". | Smith | S-8 |
| 8 | **@-mention autocomplete** *(added Nov 5, Tyler request)* | Typing `@` in the composer suggests taggable participants (humans + agents), keyboard navigable; selecting inserts a mention token that triggers S-7 wake. | Smith | S-9 |
| 9 | **Single + button** *(added Nov 5, Tyler request)* | The New Message / New Channel buttons collapse into one `+` with a small menu. | Smith | S-10 |
| 10 | **Threads** *(added Nov 5 — Tyler approved moving this from OUT to IN)* | Reply-in-thread like Slack; thread view from any message. | Smith | S-11 |
| 11 | **Reactions** *(added Nov 5 — Tyler approved moving this from OUT to IN)* | Hover-to-react with 👍 ❤️ 👁️ 🎉; counts aggregate; cross-gateway like messages. | Smith | S-12 |

### Why `herd_read_channel` is in (scope addition vs. the original board)

The board's S-3 listed only post + list. The demo payoff is "two agents
collaborating in one channel," and an agent can't collaborate on a message it
can't read. One read tool is the smallest thing that makes the payoff true.
Cost: one more handler against tables S-1 already creates.

## OUT (post-hackathon backlog, do not build before Nov 11)

- Edits/deletes, file sharing, rich embeds
- Presence / typing indicators, unread badges, notifications
- Voice, video
- Channel permissions, roles, private channels, invites/links
- Message search
- More than two gateways, relay servers, NAT traversal
- Message history sync for peers who join late (new peers see messages from join onward)
- Encryption beyond whatever the transport already gives
- MySI plugin, any second plugin

## Stretch (gated; pending Tyler's call, Nov 5)

- **Agent answers when @mentioned.** A Herd message that @mentions a local
  agent is queued into that agent's chat via `ctx.inject_message`, under the
  owner's own approvals (rule 12). Mentions only, one wake per message, agent-
  authored messages never wake anything, off by default (opt-in setting,
  `allow_gateway_injection`). The owner says one thing in that agent's chat
  first. Smith estimate: 4–6 h plus a two-machine test on Tyler's hardware.
  - **Start:** as soon as Sentry signs off TC-2 (SPINE) on real hardware.
  - **Go/no-go:** Fri Nov 7, 12:00 PM, Foreman. Go = works on both Macs 3 times in a row.
  - **No-go:** the feature stays off in the build, and in the demo the human asks their agent to check the channel.
  - Never at the expense of S-4/S-5 or the freeze.
- Unread dot on channels with new messages, only if everything above is done.

Auto-wake on *every* message (no mention) stays OUT.

## Risks that could force a cut

- **R-1 — Join flow. Updated Nov 5.** `hermes peer add` is a real core command,
  but Sentry ruled (Q-3 CA-4) that Herd may not read core's peer registry or
  `HERMES_PEER_*` keys in the catalog build. So Herd has its **own** join: the
  Add-teammate form above. The story ("one step to connect") holds; the demo
  hook moves from the terminal to the form.
- **R-2 — SPINE slips past Fri Nov 6.** Then DMs (IN #5) drop to backlog and
  the demo uses `general` only. Fan-out and agent posting are never cut; they
  are the product.
- **R-3 — Agent tool registration fails catalog rules (Q-3).** Fall back to
  the two original tools only if `herd_read_channel` is the problem; the demo
  then has the human paste the task into Bot Chats.

## Positioning vs. core Group Chat (answers Q-3 CA-8)

Hermes core already has cross-machine **Group Chat** rooms and `hermes peer dm`.
Both are **one person's bots** talking to each other: a room is driven by one
Desktop that holds every connection's credentials, and members are 2–6 Bots.

**Herd is for two people.** Two humans, each on their own Hermes and their own
machine, share one persistent channel, and each brings their own agent into it.
Nobody holds the other's keys, and each agent runs under its own owner's
approvals. Humans talk to humans there too, not only to bots.

Rules that follow from this:
- Never pitch "agents talking across machines" as the new thing. Core does that.
  Pitch **"you and a teammate, with both your agents, in one channel."**
- The demo must show two humans, two Desktops, two sets of credentials.
- Catalog copy and README must answer "how is this different from Group Chat?"
  in one line (see N-3).

## Canonical names (for code, docs, QA)

- Plugin id: `herd` · Display name: **Herd**
- Tools: `herd_list_channels`, `herd_post`, `herd_read_channel`
- API namespace: `/api/plugins/herd/`
- Default channel: `general` (no `#` in data; UI shows `#general`)
