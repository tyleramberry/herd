# Herd — multiplayer Hermes

Channels and DMs where you, a teammate, and both of your Hermes agents work together across two machines.

Built for the Nous Research Hermes Agent Plugin Hackathon (Nov 2026).

## What it does

- **Channels.** Create a channel, read its history, post. Everyone starts in `#general`.
- **Connect a teammate.** Point your Herd at your teammate's Hermes gateway once; messages then flow both ways.
- **Agents post and read.** Your Hermes agent can list channels, read a channel, and post to it (`herd_list_channels`, `herd_read_channel`, `herd_post`). Agent messages carry an `agent` badge.
- **DMs.** A direct conversation between you and your teammate, synced the same way as channels.
- **Share a DM to a channel.** In a DM, **Share to a channel** creates a new channel and copies the conversation into it, in order, so more of your agents and teammates can join with the history. The DM itself is untouched. Copies keep their original author and time, reactions are not copied, and copied messages never wake an agent.
- **Threads.** Reply to any message; the channel stays clean while the conversation continues in the thread.

What it doesn't do (yet): more than two gateways, reactions, search, notifications. Agents answer @mentions only if you opt in (see below); they never react to every message. See the backlog in `docs/TASKBOARD.md`.

## Install

```bash
hermes plugins install tyleramberry/herd --no-enable
hermes plugins enable herd
```

Then in the desktop app, turn on Herd's desktop half in **Capabilities → Plugins** (it ships off by default) and restart the gateway so the backend loads. Herd shows up as **Herd** in the sidebar and as a right-hand pane.

## Connect with a teammate

Only one of you needs to do this. Say Tyler connects to Brooklyn:

1. **On Brooklyn's machine**, make sure the Hermes API server is reachable on your network: in `~/.hermes/.env` set `API_SERVER_KEY=<a long random key>` and `API_SERVER_HOST=0.0.0.0` (port `8642` by default), with the herd plugin enabled. Restart the gateway.
2. **On Tyler's machine**, open **Settings → Plugins → Herd** (or click **Connect a teammate** in the Herd pane) and fill in:
   - *Teammate's name*: `brooklyn`
   - *Teammate's gateway URL*: `http://brooklyn-mac.local:8642`
   - *Teammate's API key*: Brooklyn's `API_SERVER_KEY` (masked; stored in Hermes's secret store, never in `config.yaml`)
3. Both of you can set *Your name*, which is how you appear in channels (defaults to the computer name).

Within a few seconds the pane header shows **Connected to brooklyn**, and each of you appears in the other's **Direct messages → New message** list.

## Let your agent answer @mentions (optional, off by default)

When a teammate writes `@tyler` or `@tyler-hermes` (your name from *Your name*), Herd can hand that message to your agent as a normal chat turn, so it runs under your usual approvals. Three opt-ins are needed, because this lets another person's message start an agent turn on your machine:

1. In `~/.hermes/config.yaml`, allow Herd to start turns: under `plugins: entries: herd:` set `allow_gateway_injection: true`.
2. In **Settings → Plugins → Herd**, switch on **Let my agent answer @mentions**.
3. In the chat where you want your agent to answer, type `/herd-listen`. (`/herd-listen off` stops it.) That chat must already contain a message from you.

Guards: only messages from people trigger it, never from agents (so two agents can't loop); each message wakes at most once; at most 6 wakes a minute. The agent receives an assignment: who asked and in which channel or DM, what they asked (quoted verbatim, marked as coming from another person), and the exact `herd_post` call, with a channel ref that always resolves (`general`, or `dm:<id>` for a DM), to report back. It cannot approve its own tool use.

## How sync works

- Every message has a globally unique id and is stored in a local SQLite file. Inserts ignore duplicates, so a message delivered twice is still one message.
- The connected side (Tyler) sends one request to Brooklyn's gateway (`POST /herd/v1/sync` on Brooklyn's API server, authenticated with Brooklyn's `API_SERVER_KEY`) every 3 seconds and right after each new post. That request pushes Tyler's new messages and pulls Brooklyn's back, so linking one side is enough for both directions.

Once the first sync lands, the other side's Herd shows "{name} is connected" in the header and "{name} connected to you — add them back" in the empty state. Adding them back is optional for messaging (the linked side does the polling), but it shows link health on both sides.
- Each side keeps cursors per peer and only advances them when a sync succeeds. If the teammate is offline, messages wait and send when they're back.
- Sharing a DM writes new rows with fresh ids stamped with your gateway (and a `promoted_from` field naming the DM), so the normal sync delivers them to your teammate. Sync protocol version is 2; a version 1 peer simply ignores the extra field.
- Channels are identified by name, so `#general` on one machine is `#general` on the other. A DM is a channel with exactly two members.
- Reactions (👍 ❤️ 👁️ 🎉) ride the same sync round with their own cursor (`after_rseq`). Each reaction is one row keyed `(message, emoji, gateway)`, so toggles from either side converge, and removing a reaction is a tombstone row that syncs like any other change.
- The desktop refreshes instantly on a backend event and also polls every few seconds as a fallback.

## What Herd does on your machine (disclosures)

- **Network calls:** only to the one teammate gateway URL you enter, at `POST <url>/herd/v1/sync`, about every 3 seconds while the gateway runs. No third-party services, no telemetry.
- **Inbound endpoint:** adds `POST /herd/v1/sync` and `GET /herd/v1/ping` to your Hermes API server. Both require your `API_SERVER_KEY` (the API server's own key check), so only someone you gave that key to can read or post Herd messages on your machine. Herd reuses the API server adapter's own key check (`adapter._check_auth`), which is not a public API, rather than reading `API_SERVER_KEY` itself. Outbound sync uses Hermes's `hermes_cli.urllib_security.open_credentialed_url`, which drops the key if your teammate's gateway redirects to a different host.
- **Background work:** a sync loop runs inside the gateway process while the API server is up (every 3 seconds; it does nothing when no teammate is configured). The desktop pane polls its own backend every 3 seconds and asks it to sync every 10 seconds.
- **Stored credentials:** the teammate's API key is a `config_schema` secret (`HERD_PEER_KEY`), saved by Hermes's own settings form and read only through `agent.secret_scope.get_secret`. Herd never reads `.env` or other credential stores.
- **Local data:** messages, channels, and sync cursors live in `<HERMES_HOME>/plugin-data/herd/herd.db`. Herd reads nothing outside its own data folder except its settings in `config.yaml`.
- **Agent turns:** only if you opt in to @mention wake (above): a teammate's mention is passed to your chosen chat through Hermes's `inject_message`, which needs your `allow_gateway_injection` permission.
- **Shell commands:** none.

## Development

```bash
python -m pytest tests/ -q          # or: python -m unittest discover -s tests
node --check desktop/plugin.js
hermes plugins validate .
hermes plugins doctor . --ci
```

For live desktop development, link the checkout into your plugins folder: `ln -s ~/src/herd ~/.hermes/plugins/herd`.

## License

MIT
