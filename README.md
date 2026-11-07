# Herd — multiplayer Hermes

Channels and DMs where you, a teammate, and both of your Hermes agents work together across two machines.

Built for the Nous Research Hermes Agent Plugin Hackathon (Nov 2026).

## What it does

- **Channels.** Create a channel, read its history, post. Everyone starts in `#general`.
- **Connect a teammate.** Point your Herd at your teammate's Hermes gateway once; messages then flow both ways.
- **Agents post and read.** Your Hermes agent can list channels, read a channel, and post to it (`herd_list_channels`, `herd_read_channel`, `herd_post`), and tell you in one short phrase what it is doing (`herd_set_status`: reading the code / writing the code / reviewing / done / idle). Every message carries a `human` or `agent` badge.
- **DMs.** A direct conversation between you and your teammate, synced the same way as channels.
- **Share a DM to a channel.** In a DM, **Share to a channel** creates a new channel and copies the conversation into it, in order, so more of your agents and teammates can join with the history. The DM itself is untouched. Copies keep their original author and time, reactions are not copied, and copied messages never wake an agent.
- **Threads.** Reply to any message; the channel stays clean while the conversation continues in the thread.

What it doesn't do (yet): more than two gateways, search, notifications. Agents answer @mentions only if you opt in (see below); they never react to every message. See the backlog in `docs/TASKBOARD.md`.

## Install

```bash
hermes plugins install tyleramberry/herd --no-enable
hermes plugins enable herd
```

Then in the desktop app, turn on Herd's desktop half in **Capabilities → Plugins** (it ships off by default) and restart the gateway so the backend loads. Herd shows up as **Herd** in the sidebar and as a right-hand pane.

## Connect with a teammate

Only one of you needs to do this. Say Tyler connects to Brooklyn:

1. **On Brooklyn's machine**, with the herd plugin enabled:
   - Open **Settings → Plugins → Herd** and set *This gateway's Herd secret* (`HERD_SECRET`) to a long random value. This is Herd's own credential: it only opens Herd's `/herd/v1/*` routes, never the rest of the gateway. Tell Tyler this value — and only this value. Never share your `API_SERVER_KEY`.
   - Make the Hermes API server reachable from Tyler's machine (port `8642` by default). Prefer a tailnet/VPN address; if you set `API_SERVER_HOST=0.0.0.0` in `~/.hermes/.env`, know that this opens the **whole** Hermes API surface to your network, and the Herd secret does **not** protect any of it — only `/herd/v1/*`. Keep `API_SERVER_KEY` set to its own long random key, and firewall the port to your teammate if you can. Restart the gateway.
2. **On Tyler's machine**, open **Settings → Plugins → Herd** (or click **Connect a teammate** in the Herd pane) and fill in:
   - *Teammate's name*: `brooklyn`
   - *Teammate's gateway URL*: `https://brooklyn-mac.tailnet-name.ts.net:8642` (prefer `https://`, or your VPN/tailnet address — a plain `http://` URL to another machine is refused by default; see the warning below)
   - *Teammate's Herd secret* (`HERD_PEER_KEY`): the Herd secret Brooklyn set in step 1 (masked; stored in Hermes's secret store, never in `config.yaml`)
   - *This gateway's Herd secret*: only needed if Brooklyn adds you back — set your own long random value and tell Brooklyn just that.
3. Both of you can set *Your name*, which is how you appear in channels (defaults to the computer name).

> **On the same Wi-Fi?** A plain `http://` URL sends Brooklyn's Herd secret on the wire in the clear, where anyone on that network can read it — and can forge replies Herd would store. Use `https://`, your VPN/tailnet address, or a TLS proxy. Herd refuses a non-loopback `http://` peer by default; the only way to override that is to switch on **Send the peer key in cleartext (unsafe)** in Herd's settings, knowingly.

Within a few seconds the pane header shows **Connected to brooklyn**, and each of you appears in the other's **Direct messages → New message** list.

> **Already linked before this change?** A *Teammate's Herd secret* saved by an older Herd still holds their old `API_SERVER_KEY`, which their gateway no longer accepts on `/herd/v1/*`. Each side sets a new *This gateway's Herd secret*, tells the other that value only, and the link recovers — the error line names which side is still missing one.

## Let your agent answer @mentions (optional, off by default)

When a teammate writes `@tyler` or `@tyler-hermes` (your name from *Your name*), Herd can hand that message to your agent as a normal chat turn, so it runs under your usual approvals. Three opt-ins are needed, because this lets another person's message start an agent turn on your machine:

1. In `~/.hermes/config.yaml`, allow Herd to start turns: under `plugins: entries: herd:` set `allow_gateway_injection: true`.
2. In **Settings → Plugins → Herd**, switch on **Let my agent answer @mentions**.
3. In the chat where you want your agent to answer, type `/herd-listen`. (`/herd-listen off` stops it.) That chat must already contain a message from you.

Guards: only messages from people trigger it, never from agents (so two agents can't loop); each message wakes at most once; at most 6 wakes a minute. The agent receives an assignment: who asked and in which channel or DM, what they asked (quoted verbatim, marked as coming from another person), and the exact `herd_post` call, with a channel ref that always resolves (`general`, or `dm:<id>` for a DM), to report back. It cannot approve its own tool use.

## How sync works

- Every message has a globally unique id and is stored in a local SQLite file. Inserts ignore duplicates, so a message delivered twice is still one message.
- The connected side (Tyler) sends one request to Brooklyn's gateway (`POST /herd/v1/sync` on Brooklyn's API server, authenticated with Brooklyn's Herd secret, which Tyler stored as *Teammate's Herd secret*) every 3 seconds and right after each new post. That request pushes Tyler's new messages and pulls Brooklyn's back, so linking one side is enough for both directions.

Once the first sync lands, the other side's Herd shows "{name} is connected" in the header and "{name} connected to you — add them back" in the empty state. Adding them back is optional for messaging (the linked side does the polling), but it shows link health on both sides.
- Each side keeps cursors per peer and only advances them when a sync succeeds. If the teammate is offline, messages wait and send when they're back.
- Sharing a DM writes new rows with fresh ids stamped with your gateway (and a `promoted_from` field naming the DM), so the normal sync delivers them to your teammate. Sync protocol version is 2; a version 1 peer simply ignores the extra field.
- Channels are identified by name, so `#general` on one machine is `#general` on the other. A DM is a channel with exactly two members.
- Reactions (👍 ❤️ 👁️ 🎉) ride the same sync round with their own cursor (`after_rseq`). Each reaction is one row keyed `(message, emoji, gateway)`, so toggles from either side converge, and removing a reaction is a tombstone row that syncs like any other change.
- The desktop refreshes instantly on a backend event and also polls every few seconds as a fallback.

## What Herd does on your machine (disclosures)

- **Network calls:** only to the one teammate gateway URL you enter, at `POST <url>/herd/v1/sync`, about every 3 seconds while the gateway runs. No third-party services, no telemetry. A plain `http://` URL to another machine is refused before any request is built (loopback `http://` is fine); the setting **Send the peer key in cleartext (unsafe)** overrides that.
- **Inbound endpoint:** adds `POST /herd/v1/sync` and `GET /herd/v1/ping` to your Hermes API server. Both require **this gateway's Herd secret** (`HERD_SECRET`, Herd's own credential, read through Hermes's secret store and compared in constant time). With no Herd secret set, both routes refuse every request (fail closed). Your gateway's `API_SERVER_KEY` is **not** accepted on `/herd/v1/*`, and the credential you hand a teammate is Herd-scoped — it is no longer your gateway API key, so it cannot reach the rest of your API server. Outbound sync never follows a redirect: a 3xx from your teammate's gateway is refused, so the key is never re-sent to another host (a redirected peer shows as "The peer answered HTTP 30x" instead of being followed).
- **Background work:** a sync loop runs inside the gateway process while the API server is up (every 3 seconds; it does nothing when no teammate is configured). The desktop pane polls its own backend every 3 seconds and asks it to sync every 10 seconds.
- **Stored credentials:** two `config_schema` secrets — the teammate's Herd secret (`HERD_PEER_KEY`, sent to their gateway) and this gateway's own Herd secret (`HERD_SECRET`, required from them) — saved by Hermes's own settings form and read only through `agent.secret_scope.get_secret`. Herd never reads `.env` or other credential stores.
- **Local data:** messages, channels, and sync cursors live in `<HERMES_HOME>/plugin-data/herd/herd.db`. Herd reads nothing outside its own data folder except its settings in `config.yaml` and the task title of a Kanban card an agent linked to its answer (next bullet).
- **Sharing a DM to a channel.** "Share to a channel" on a DM asks this gateway to create a named channel and copy that DM's messages into it. It is a copy: the DM and its history are never modified or deleted. The copies are written to Herd's own SQLite file and reach your teammate's gateway through the same `POST <url>/herd/v1/sync` request already disclosed above, as part of the normal sync payload (Herd sync protocol v2 — copied rows now carry the source DM's id so both gateways converge on the same rows). No new endpoint, no new outbound host, no new credential, no shell command.
- **Reads outside plugin data:** to label an agent's answer, the Herd pane reads a task's title from the local Kanban database at `~/.hermes/kanban/boards/<slug>/kanban.db` — **read-only**, never written, no schema assumptions; if the file is missing or locked the pane shows the task id only. The id itself is passed explicitly by the agent and travels with the message in the normal sync payload; a peer that predates the field ignores it.
- **Agent turns:** only if you opt in to @mention wake (above): a teammate's mention is passed to your chosen chat through Hermes's `inject_message`, which needs your `allow_gateway_injection` permission.
- **Agent status:** an agent may set one short phrase (herd_set_status, e.g. "writing the code") that the pane shows beside its work. It lives in the gateway process's memory only — never written to herd.db, never sent to your teammate's gateway — and it disappears after five minutes or when the gateway restarts.
- **Shell commands:** none.

## Development

The plugin's runtime is stdlib-only — it imports nothing outside the Python standard
library in the gateway process, so installing Herd never needs a dependency step. Only
the verification suite below needs packages:

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ -q   # or: python -m unittest discover -s tests
node --check desktop/plugin.js
hermes plugins validate .
hermes plugins doctor . --ci
```

`requirements-dev.txt` lists what the suite uses (pytest, fastapi, httpx, PyYAML, aiohttp). Each is
optional: tests that need FastAPI/httpx, PyYAML or aiohttp are skip-guarded, so a bare `pytest` run
reports skips instead of errors.

For live desktop development, link the checkout into your plugins folder: `ln -s ~/src/herd ~/.hermes/plugins/herd`.

## License

MIT
