# Hermes Multiplayer

Multiplayer Hermes: channels and DMs for you, your teammates, and everyone's agents.

Channels and DMs where you, up to four teammates, and each of your Hermes agents work together across up to five machines.

Built for the Nous Research Hermes Agent Plugin Hackathon (Nov 2026).

## What it does

- **Channels.** Create a channel, read its history, post. Everyone starts in `#general`.
- **Search.** Press ⌘K and pick **Search Hermes Multiplayer messages**, or use the search box on the Hermes Multiplayer page. It searches the message text of every channel and DM this gateway holds, best match first, and a result jumps to its message (or its thread, for a reply). Searching is local: nothing is sent anywhere.
- **Connect teammates.** Point your Hermes Multiplayer at each teammate's Hermes gateway once (up to four); messages flow to all of them, and anything a teammate passes on reaches the rest of the mesh.
- **Agents post and read.** Your Hermes agent can list channels, read a channel, and post to it (`multiplayer_list_channels`, `multiplayer_read_channel`, `multiplayer_post`), and tell you in one short phrase what it is doing (`multiplayer_set_status`: reading the code / writing the code / reviewing / done / idle). Agent messages carry an `agent` badge; human messages are the plain, unbadged default.
- **People.** The sidebar lists everyone in the mesh with a dot that is green while their Hermes is exchanging messages with yours (within the last 20 seconds). Click a teammate to open your DM with them. Click your own row to change your name without opening Settings; a name set there wins over the *Your name* setting, and clearing it falls back to the setting.
- **DMs.** A direct conversation between you and your teammate, synced the same way as channels.
- **Share a DM to a channel.** In a DM, **Share to a channel** creates a new channel for the two people in that DM and copies the conversation into it, in order. Nobody else in the mesh receives it: a shared channel's member list is the two of you, and it cannot be changed later. The DM itself is untouched. Copies keep their original author and time, reactions are not copied, and copied messages never wake an agent.
- **Threads.** Reply to any message. The thread opens in a panel on the right, beside the channel, with the root, its replies and its own composer; `Esc` or the close button shuts it. **Open as page** docks the thread as a tab beside the chat, for longer replies; the panel stays as a peek, and **Open in Hermes Multiplayer** brings it back to the Hermes Multiplayer page.
- **Channel members.** A channel can list up to five people (you included), and only those gateways receive it. A channel without a list is open to every gateway in the mesh. When you create a channel, the form offers the teammates you're linked to: tick up to four and only you and they receive it. The list is fixed once the channel exists.
- **Topic.** Every public channel has a one-line topic (up to 200 characters). Open a channel and use **Edit topic** (or **Add a topic**). Topics sync to the mesh, and the most recently set topic wins.
- **Composer.** **Emoji** opens a small tray that inserts at the cursor. Messages render a safe markdown subset: `code`, **bold** and *italic* (or _italic_), plus fenced code blocks, bullet and numbered lists, quotes and headings, so an agent's answer reads as written. Text is shown as typed otherwise: links are not made clickable and HTML is never rendered. A half-written message is kept per channel (and per thread) until you send it or clear it.
- **Reading.** A channel opens at its newest message and follows new ones while you are at the bottom; scrolled up to read history, you stay where you are. Messages sent close together by one author share a header, days are separated by a divider, and hovering a time shows the exact date and time.
- **Keyboard.** **Open Hermes Multiplayer** is `⌥⌘H` (`mod+alt+h`) and **New Hermes Multiplayer message** is `⌥⌘N` (`mod+alt+n`); both can be rebound in Hermes's keybinding settings.

What it doesn't do (yet): more than five gateways; private channels (the only restriction is the member list above, set when a channel is created); renaming a channel (its name is its identity across the mesh, so a rename would orphan its history); attachments; custom emoji. Agents answer @mentions once you point them at a chat (see below); they never react to every message. See the backlog in `docs/TASKBOARD.md`.

## Get started (about a minute, no setup knowledge needed)

Both of you do step 1. Then one person invites and the other pastes.

1. **Install.** Open **[the install page](https://tyleramberry.github.io/hermes-multiplayer/)** and click **Install in Hermes**. Hermes opens and asks you to confirm: click **Install**. (No button? Paste `hermes://plugin/install?repo=tyleramberry/hermes-multiplayer&enable=1` into your browser's address bar.)
2. **Invite.** In Hermes, click **Hermes Multiplayer** in the sidebar. Check your name, then click **Invite a teammate**. An invite is copied: text, email or Slack it to your teammate.
3. **Join.** Your teammate opens the invite link (it walks them through step 1 if they haven't installed yet), then pastes the invite into the box in Hermes Multiplayer. You're connected, and you'll both see each other in **People**.

**Optional: let your agent answer when someone @mentions you.** Click **Set up my agent** in the Hermes Multiplayer pane. A chat opens with the request already written: press Enter and approve the one-line change. No restart.

Prefer a terminal? `hermes plugins install tyleramberry/hermes-multiplayer --enable`, then in Hermes open **Capabilities → Plugins** and switch on Hermes Multiplayer's desktop half (Hermes ships every plugin's desktop half switched off, and only its own install dialog switches it on for you).

### If something goes wrong

| What you see | What to do |
|---|---|
| Hermes Multiplayer isn't in the sidebar | Open **Capabilities → Plugins** and switch Hermes Multiplayer on. |
| **Almost ready** with a **Finish setup** button | Click it. It switches the plugin on and restarts Hermes if needed. |
| "Couldn't reach the team room server" | Check this computer is online and try again. |
| "That isn't an invite link" | Ask your teammate to send the whole invite again. |
| "The team room refused this invite link" | The invite is wrong or old. Ask for a fresh one. |
| Your agent doesn't answer @mentions | The line at the top of the pane says exactly what is missing, with a button to fix it. |

Invites are keys: anyone with one can read and post in your room, so only send them to your team.

## Advanced

Most teams never need anything below. It covers running your own relay, linking two computers directly without a relay, and the details of agent @mentions.

### How the team room works

A team room is a small relay that holds your team's messages. Everyone joins with one link, nobody has to be reachable from anybody else, and a message written while your computer is asleep is waiting when you come back.

There is no built-in relay. The relay stores every channel message, DM and agent post in plaintext, readable by whoever operates it, so you run it yourself (next paragraph). **Invite a teammate** and **Start room** ask for the address of a relay you deployed. Invite again later with **+ → Invite a teammate**; it hands out the same room's invite, so your team never splits across two rooms. Starting or joining a room checks the relay answers first, so a dead relay fails right away with a plain message.

**Your own relay.** To keep your team's messages on a relay you run: deploy it once (free Cloudflare account) with `cd relay && npm install && npx wrangler deploy`, or run `node relay/server.mjs --port 8787 --data ./rooms` (node 22.5+) behind https. Then in Hermes Multiplayer paste its address into **Invite a teammate** (or **Other ways to connect → Use my own relay**) and start the room.

With a room you also get delivery in about a second, "is typing…", and who is online. Edits, deletes, reactions, threads, DMs, groups and private channels all travel through it. DMs and private channels are only handed to their members, and each Hermes Multiplayer proves itself to the room with its own token, so one member cannot ask for another's DMs.

Linking two gateways directly (below) still works, and can be mixed with a room.

### Link two gateways directly (no relay)

Only one of you needs to do this. Say Tyler connects to Brooklyn:

1. **On Brooklyn's machine**, with the Hermes Multiplayer plugin enabled:
   - Open **Settings → Plugins → Hermes Multiplayer** and set *This gateway's Hermes Multiplayer secret* (`HERMES_MULTIPLAYER_SECRET`) to a long random value. This is Hermes Multiplayer's own credential: it only opens Hermes Multiplayer's `/hermes-multiplayer/v1/*` routes, never the rest of the gateway. Tell Tyler this value — and only this value. Never share your `API_SERVER_KEY`.
   - Make the Hermes API server reachable from Tyler's machine (port `8642` by default). Prefer a tailnet/VPN address; if you set `API_SERVER_HOST=0.0.0.0` in `~/.hermes/.env`, know that this opens the **whole** Hermes API surface to your network, and the Hermes Multiplayer secret does **not** protect any of it — only `/hermes-multiplayer/v1/*`. Keep `API_SERVER_KEY` set to its own long random key, and firewall the port to your teammate if you can. Restart the gateway.
2. **On Tyler's machine**, open **Settings → Plugins → Hermes Multiplayer**  and fill in:
   - *Teammate's name*: `brooklyn`
   - *Teammate's gateway URL*: `https://brooklyn-mac.tailnet-name.ts.net:8642` (prefer `https://`, or your VPN/tailnet address — a plain `http://` URL to another machine is refused by default; see the warning below)
   - *Teammate's Hermes Multiplayer secret* (`HERMES_MULTIPLAYER_PEER_KEY`): the Hermes Multiplayer secret Brooklyn set in step 1 (masked; stored in Hermes's secret store, never in `config.yaml`)
   - *This gateway's Hermes Multiplayer secret*: only needed if Brooklyn adds you back — set your own long random value and tell Brooklyn just that.
3. Both of you can set *Your name*, which is how you appear in channels (defaults to the computer name).

> **On the same Wi-Fi?** A plain `http://` URL sends Brooklyn's Hermes Multiplayer secret on the wire in the clear, where anyone on that network can read it — and can forge replies Hermes Multiplayer would store. Use `https://`, your VPN/tailnet address, or a TLS proxy. Hermes Multiplayer refuses a non-loopback `http://` peer by default; the only way to override that is to switch on **Send the peer key in cleartext (unsafe)** in Hermes Multiplayer's settings, knowingly.

Within a few seconds the pane header shows **Connected to brooklyn**, and each of you appears in the other's **Direct messages → New message** list.

> **Already linked before this change?** A *Teammate's Hermes Multiplayer secret* saved by an older Hermes Multiplayer still holds their old `API_SERVER_KEY`, which their gateway no longer accepts on `/hermes-multiplayer/v1/*`. Each side sets a new *This gateway's Hermes Multiplayer secret*, tells the other that value only, and the link recovers — the error line names which side is still missing one.

#### Or pair with a short code

Instead of reading a long secret aloud, the one who already has Hermes Multiplayer can make a code:

1. **On the machine that holds the secret** (with Hermes Multiplayer set up and a Hermes Multiplayer secret saved), open **Other ways to connect → Show a pairing code** on the Hermes Multiplayer page. You get a 10-character code (like `ABCDE-FGHJK`) that is valid for ten minutes and for one use. Type this gateway's address under it once (Hermes Multiplayer remembers it) and press **Copy invite**: the invite is one line, `https://brooklyn-mac.tailnet-name.ts.net:8642#ABCDE-FGHJK`.
2. **On your teammate's machine**, open **Other ways to connect → Enter a pairing code** (or paste the one-line invite into the invite box), then **Pair**. The address and the code typed separately work too. Hermes Multiplayer fetches the Hermes Multiplayer secret and shows it once.
3. Paste that key into **Settings → Plugins → Hermes Multiplayer → Teammate's Hermes Multiplayer secret**, with the name and address as in the section above. Hermes Multiplayer cannot save it for you yet: Hermes's secret store has no write door for plugins.

Five wrong codes pause pairing for ten minutes and kill the live code. A new code replaces the old one. Pairing refuses a plain `http://` address to another machine, the same as the manual route. **Only give a code to someone you would give the Hermes Multiplayer secret to:** a correct code gets that secret in the reply.

#### More than two of you (up to five gateways)

Each teammate you link is one more gateway. You can link up to four teammates, so the mesh is five gateways at most.

- Fill in **Teammate 2's name**, **gateway URL** and **Hermes Multiplayer secret** (and 3 and 4 the same way) under **Settings → Plugins → Hermes Multiplayer**. Each teammate has its own secret slot (`HERMES_MULTIPLAYER_PEER_KEY`, then `HERMES_MULTIPLAYER_PEER_KEY_2`, `_3`, `_4`), so one teammate's secret is never offered to another.
- Or give the whole list in the Settings field **Teammates (advanced)**, or in `~/.hermes/config.yaml` under `plugins: entries: hermes-multiplayer: settings:` as `peers: [{name: ash, url: "https://ash.tailnet-name.ts.net:8642", key_env: HERMES_MULTIPLAYER_PEER_KEY_2}]`. Each entry names the secret slot its key lives in; a list entry without one is refused, never guessed.
- Names must be different, and so must URLs. A duplicate, or a fifth teammate, is refused and the pane says why.
- Teammate 1 is the original single peer. A config that already linked one teammate keeps working unchanged, and its secret stays where it was.

Every teammate has its own status line in the pane (connected, can't reach, or needs a secret), so one that is offline never hides the others.

### Agent @mentions in detail

Wake is on by default. When a teammate writes `@tyler` or `@tyler-hermes` (your name from *Your name*), Hermes Multiplayer hands that message to your agent as a normal chat turn, so it runs under your usual approvals. Two things must be in place, because this lets another person's message start an agent turn on your machine:

1. Hermes must allow Hermes Multiplayer to start turns: `allow_gateway_injection: true` under `plugins: entries: hermes-multiplayer:` in `~/.hermes/config.yaml`. A plugin may not grant itself that, so **Set up my agent** opens a chat with the request written for your own agent, which makes the change once you approve it. Hermes reads the setting fresh, so no restart is needed.
2. A chat that answers. The chat you have open is used by default; **Use this chat instead** picks another, and `/multiplayer-listen` in a chat does the same. **Stop** (or `/multiplayer-listen off`) clears it, and it stays off until you pick a chat again.

**Tagging your own agent.** You don't need a teammate to try it: type `@hermes` (or `@your-name-hermes`) in any channel on your own Hermes Multiplayer and your agent gets the message the same way, with the same two requirements. `@hermes` only ever means the agent on the machine it was typed on; it never wakes a teammate's agent. Writing your own name alone (`@tyler`) is not a request to your agent.

**You can see it was picked up.** When an agent is handed a mention, its gateway adds a 👀 reaction to that message. It is an ordinary reaction, so it syncs: the person who tagged sees it on their own screen. No 👀 means the mention was not handed over, and the owner's Hermes Multiplayer says why.

**Answers stay in the thread.** A mention inside a thread tells the agent to reply in that thread; a top-level mention is answered in the channel.

The pane's banner says either *Your agent answers @mentions in this chat* or exactly what is missing. A mention that doesn't reach the agent is never dropped silently: it stays in the channel with a short note saying why (no chat set, wake turned off in Settings, injection not allowed, too many in a minute), and `multiplayer_read_channel` reports the same note.

Guards: only messages from people trigger it, never from agents (so two agents can't loop); each message wakes at most once; at most 6 wakes a minute. The agent receives an assignment: who asked and in which channel or DM, what they asked (quoted verbatim, marked as coming from another person), and the exact `multiplayer_post` call, with a channel ref that always resolves (`general`, or `dm:<id>` for a DM), to report back. It cannot approve its own tool use.

## How sync works

- Every message has a globally unique id and is stored in a local SQLite file. Inserts ignore duplicates, so a message delivered twice is still one message.
- Each gateway sends one request to every teammate it is linked to (`POST /hermes-multiplayer/v1/sync` on that teammate's API server, authenticated with that teammate's Hermes Multiplayer secret, which you stored for them) every 3 seconds and right after each new post. Each request pushes the rows that teammate does not have yet and pulls theirs back, so linking one side is enough for both directions. A row that arrives from one teammate is passed on to the others, and never sent back to the gateway that wrote it, so a message reaches every gateway once. Teammates are synced in parallel: a slow or unreachable one waits on its own connection and does not delay the others.

Once the first sync lands, the other side's Hermes Multiplayer shows "{name} is connected" in the header and "{name} connected to you — add them back" in the empty state. Adding them back is optional for messaging (the linked side does the polling), but it shows link health on both sides.
- Each side keeps cursors per peer and only advances them when a sync succeeds. If the teammate is offline, messages wait and send when they're back.
- Sharing a DM writes new rows with fresh ids stamped with your gateway (and a `promoted_from` field naming the DM), so the normal sync delivers them to your teammate. Sync protocol version is 2; a version 1 peer simply ignores the extra field.
- Channels are identified by name, so `#general` on one machine is `#general` on the other. A DM is a channel with exactly two members.
- A DM channel is only accepted from a peer when its two member ids are plain identifiers (lowercase letters, digits, `-`, `_`, at most 64 characters, so no trailing newline or other whitespace); anything else is refused rather than repaired, because the id is shared with the peer.
- A DM is only synced to the two gateways that are in it: a sync request never returns another pair's DM — not its channel, its messages, or its reactions — and a request that carries no gateway id gets no DMs at all. Public channels are unaffected. In the normal two-gateway link nothing changes: the only DM you hold is the one with your teammate.
- Reactions (👍 ❤️ 👀 🎉; 👁️ from older builds is still accepted and shown) ride the same sync round with their own cursor (`after_rseq`). Each reaction is one row keyed `(message, emoji, gateway)`, so toggles from either side converge, and removing a reaction is a tombstone row that syncs like any other change.
- A synced row keeps the gateway id it names (its origin), so a teammate can relay messages written on another gateway in the mesh; the name shown for a relayed row is the one its origin declared. A row that claims your own gateway's id, or a malformed id, is dropped instead of stored, and the sync response reports how many were (`accepted: N, dropped: M`). A row in a channel with a member list is refused unless both its sender and its origin are members. The shared Hermes Multiplayer secret authenticates the link to each teammate, not the individual caller, so a linked teammate's gateway is trusted to relay the origins it names. What this guards against is a typo, a stale row, or a forged row that claims to be from this gateway or from a non-member, not a cryptographic proof of who is calling.
- The desktop refreshes instantly on a backend event and also polls every few seconds as a fallback.

## What Hermes Multiplayer does on your machine (disclosures)

- **Network calls:** only to the teammate gateway URLs you enter (up to four), at `POST <url>/hermes-multiplayer/v1/sync`, about every 3 seconds while the gateway runs. No third-party services, no telemetry. The peer client ignores ambient `http_proxy`/`HTTP_PROXY` (it builds its opener with an explicitly empty proxy map), so the peer key is never handed to a proxy. A plain `http://` URL to another machine is refused before any request is built (loopback `http://` is fine); the setting **Send the peer key in cleartext (unsafe)** overrides that. Starting or joining a team room first sends one `GET <relay>/health` (no key, no data) to check the relay answers.
- **Inbound endpoint:** adds `POST /hermes-multiplayer/v1/sync` and `GET /hermes-multiplayer/v1/ping` to your Hermes API server. Both require **this gateway's Hermes Multiplayer secret** (`HERMES_MULTIPLAYER_SECRET`, Hermes Multiplayer's own credential, read through Hermes's secret store and compared in constant time). With no Hermes Multiplayer secret set, both routes refuse every request (fail closed). Your gateway's `API_SERVER_KEY` is **not** accepted on `/hermes-multiplayer/v1/*`, and the credential you hand a teammate is Hermes Multiplayer-scoped — it is no longer your gateway API key, so it cannot reach the rest of your API server. Outbound sync never follows a redirect: a 3xx from your teammate's gateway is refused, so the key is never re-sent to another host (a redirected peer shows as "The peer answered HTTP 30x" instead of being followed).
- **Background work:** a sync loop runs inside the gateway process while the API server is up (every 3 seconds; it does nothing when no teammate is configured). The desktop pane polls its own backend every 3 seconds and asks it to sync every 10 seconds.
- **Pairing codes:** a code is kept on your gateway only as a keyed digest, in hermes-multiplayer.db. The exchange is `POST <url>/hermes-multiplayer/v1/pair` on the teammate's gateway, which needs no Hermes Multiplayer secret, only a live code: it returns your teammate's Hermes Multiplayer secret to a correct code, once. Wrong, used and expired codes get one reply. The key the pairing shows is held in the pane's memory until you hide it and is never written to storage.
- **Stored credentials:** one `config_schema` secret per teammate — `HERMES_MULTIPLAYER_PEER_KEY`, then `HERMES_MULTIPLAYER_PEER_KEY_2` to `_4`, each sent only to its own teammate's gateway — and this gateway's own Hermes Multiplayer secret (`HERMES_MULTIPLAYER_SECRET`, required from them) — saved by Hermes's own settings form and read only through `agent.secret_scope.get_secret`. Hermes Multiplayer never reads `.env` or other credential stores.
- **Team room (only if you join one):** the room link is the key. Anyone holding it can read and post in the room, so share it like a password. A link joined from the Hermes Multiplayer page is saved in Hermes Multiplayer's own data file (`hermes-multiplayer.db`), not in Hermes's secret store; to keep the key in the secret store instead, put the room address in the Settings field *Team room address* and the key in *Team room key* (`HERMES_MULTIPLAYER_RELAY_KEY`). Once joined, Hermes Multiplayer sends everything it holds (channels, DMs, reactions, edits) to the relay, which keeps a copy and whose operator can read it. Hermes Multiplayer keeps one request open to the relay and syncs with it on a post or about twice a minute.
- **Local data:** messages, channels, and sync cursors live in `<HERMES_HOME>/plugin-data/hermes-multiplayer/hermes-multiplayer.db`. Hermes Multiplayer reads nothing outside its own data folder except its settings in `config.yaml` and the task title of a Kanban card an agent linked to its answer (next bullet).
- **Read state:** which channels you have read (a cursor per channel, `read_cursors` in hermes-multiplayer.db) stays on this gateway. It is never synced. Opening a channel in the pane marks it read.
- **Notifications:** off by default. When you turn on **Notify me about new messages**, Hermes Multiplayer raises a desktop notification for a teammate's new message while Hermes is in the background: the sender's name, the channel or DM, and a preview of up to 120 characters. Hermes shows it through its own notifier (`ctx.os.notify`); Hermes Multiplayer sends nothing outside your machine for it.
- **Sharing a DM to a channel.** "Share to a channel" on a DM asks this gateway to create a named channel and copy that DM's messages into it. It is a copy: the DM and its history are never modified or deleted. The new channel's member list is the DM's two people, so only their gateways receive the copies. The copies are written to Hermes Multiplayer's own SQLite file and reach your teammate's gateway through the same `POST <url>/hermes-multiplayer/v1/sync` request already disclosed above, as part of the normal sync payload (Hermes Multiplayer sync protocol v2 — copied rows now carry the source DM's id so both gateways converge on the same rows). No new endpoint, no new outbound host, no new credential, no shell command.
- **Reads outside plugin data:** to label an agent's answer, the Hermes Multiplayer pane reads a task's title from the local Kanban database at `~/.hermes/kanban/boards/<slug>/kanban.db` — **read-only**, never written, no schema assumptions; if the file is missing or locked the pane shows the task id only. The id itself is passed explicitly by the agent and travels with the message in the normal sync payload; a peer that predates the field ignores it.
- **Agent turns:** only when a teammate mentions you, or you tag your own agent from your own Hermes Multiplayer, and a chat is set (above): the mention is passed to your chosen chat through Hermes's `inject_message`, which needs your `allow_gateway_injection` permission. A handed-over mention gets a 👀 reaction from your gateway, which syncs like any reaction.
- **Your name:** a name you set from the Hermes Multiplayer page is kept in hermes-multiplayer.db (`meta.display_name`) and sent with your messages, exactly as the *Your name* setting is.
- **Clipboard:** **Copy invite** and the **Copy** button beside the config line write that one line to your clipboard through Hermes (`ctx.os.writeClipboard`), only when you press them. The gateway address you type for an invite is kept in the plugin's desktop storage.
- **Agent status:** an agent may set one short phrase (multiplayer_set_status, e.g. "writing the code") that the pane shows beside its work. Each sync request carries this gateway's phrase and the agent's name, and nothing else, so teammates see it while your gateway is running. A teammate's phrase is kept in memory on your side only, shows for five minutes after their last sync, and is never passed on to anyone else. Nothing about status is written to hermes-multiplayer.db, and it clears when the gateway restarts.
- **Setup buttons (only when you click them):** **Finish setup** asks Hermes to switch this plugin on (the same switch as Capabilities → Plugins) and, if Hermes says it needs one, restarts the gateway. **Set up my agent** opens a new Hermes chat with the setup request typed into the box; nothing is sent until you press Enter, and your agent's edit to `config.yaml` goes through your usual approvals. If the app can't open a chat, the request is copied to your clipboard instead.
- **Shell commands:** none.

## Upgrading from Herd

This plugin used to be called Herd. Updating keeps everything working without re-entering anything:

- Secrets saved as `HERD_SECRET`, `HERD_PEER_KEY` (and `_2`–`_4`) and `HERD_RELAY_KEY` are still read when the new `HERMES_MULTIPLAYER_*` slot of the same kind is empty.
- The data file `herd.db` is renamed to `hermes-multiplayer.db` the first time the new version opens it.
- A teammate or team room still on Herd keeps syncing: this gateway also answers on `/herd/v1/*`, and retries a teammate's old address when the new one isn't there. Pairing codes work between old and new builds in both directions.
- The agent tools are now `multiplayer_post`, `multiplayer_read_channel`, `multiplayer_list_channels` and `multiplayer_set_status`, the toolset is `hermes-multiplayer`, and `/herd-listen` is `/multiplayer-listen`. Replace `herd` with `hermes-multiplayer` in any `toolsets` list in your `config.yaml`.

## Development

The plugin's runtime is stdlib-only — it imports nothing outside the Python standard
library in the gateway process, so installing Hermes Multiplayer never needs a dependency step. Only
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

For live desktop development, link the checkout into your plugins folder: `ln -s ~/src/hermes-multiplayer ~/.hermes/plugins/hermes-multiplayer`.

## License

MIT
