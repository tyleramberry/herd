// Herd — desktop half. Loaded uncompiled: plain ESM, jsx()/jsxs() calls, no JSX syntax.
// Imports are limited to '@hermes/plugin-sdk' and 'react/jsx-runtime' by design (catalog rule 8).
import {
  Badge,
  Button,
  Codicon,
  EmptyState,
  Input,
  KEYBINDS_AREA,
  PALETTE_AREA,
  PANES_AREA,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  STATUSBAR_AREAS,
  ScrollArea,
  SearchField,
  StatusDot,
  Textarea,
  WorkspacePageHeaderControl,
  atom,
  host,
  pluginSettingsHref,
  queryClient,
  relativeTime,
  useMutation,
  useQuery,
  useValue
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const PLUGIN_ID = 'herd'
const ROUTE_PATH = '/herd'
const REFRESH_MS = 3000 // re-read local data (events are the fast path; this is the fallback)
const SYNC_MS = 10000 // ask the backend to sync with the peer (the gateway also syncs on its own)

const KEYS = {
  all: [PLUGIN_ID],
  status: [PLUGIN_ID, 'status'],
  channels: [PLUGIN_ID, 'channels'],
  participants: [PLUGIN_ID, 'participants'],
  messages: channelId => [PLUGIN_ID, 'messages', channelId],
  task: id => [PLUGIN_ID, 'task', id],
  threads: [PLUGIN_ID, 'thread'],
  thread: messageId => [PLUGIN_ID, 'thread', messageId]
}

// Module-scope state; reset on every register() (hot reload / re-enable).
let rest = null
let ctx = null // the plugin context, set by register(); timers go through ctx.setTimeout (TC-1.7)
const selection = { page: atom(null), pane: atom(null) }
const composing = { page: atom(null), pane: atom(null) } // null | 'channel' | 'dm'
const plusMenu = { page: atom(false), pane: atom(false) } // is the '+' dropdown open
const thread = { page: atom(null), pane: atom(null) } // the open thread's root message id, or null
// Per-composer @-autocomplete: { page, pane } so the page and the pane never share
// (or ghost) one another's dropdown. null | { start, query, index }.
const sharing = { page: atom(false), pane: atom(false) } // is the DM's 'Share to a channel' form open (S-13)
const mentionState = { page: atom(null), pane: atom(null) }
// Which message's reaction picker is open (its id), or null. One picker at a time, shared by page and pane.
const reactionPicker = atom(null)
// Composer emoji tray per surface, and the channel whose topic is being edited (or null).
const emojiTray = { page: atom(false), pane: atom(false) }
const topicEditing = { page: atom(null), pane: atom(null) }
// Set by the "New Herd message" keybind: the composer that mounts next takes focus (see Composer).
const composeRequest = atom(0)
const COMPOSE_FOCUS_MS = 3000

function api(path, opts) {
  if (!rest) return Promise.reject(new Error('Herd is turned off.'))
  return rest(path, opts)
}

function errorText(error, fallback) {
  const msg = error && (error.detail || error.message)
  return typeof msg === 'string' && msg ? msg : fallback
}

function newMessageId() {
  const c = globalThis.crypto
  return c && typeof c.randomUUID === 'function' ? c.randomUUID() : undefined
}

function timeLabel(iso) {
  const ms = Date.parse(iso)
  return Number.isFinite(ms) ? relativeTime(ms) : ''
}

function openSettings() {
  host.navigate(pluginSettingsHref(PLUGIN_ID))
}

function refreshAll() {
  queryClient.invalidateQueries({ queryKey: KEYS.all })
}

function dmLabel(channel, selfId) {
  const members = Array.isArray(channel.members) ? channel.members : []
  const other = members.find(m => m && m.id !== selfId)
  return other ? other.name : channel.name
}

// ---------------------------------------------------------------------------
// Peer status
// ---------------------------------------------------------------------------

function useStatus() {
  return useQuery({ queryKey: KEYS.status, queryFn: () => api('/status') })
}

function incomingUnlinked(status) {
  const list = (status && status.incoming) || []
  return list.find(entry => entry && !entry.linked_back) || null
}

function refusedPeers(status) {
  const list = (status && status.refused) || []
  return list.filter(entry => entry && entry.reason)
}

function PeerLine({ status }) {
  const peers = (status && status.peers) || []
  // Only an explicit false: older/partial status payloads without the key render as before.
  if (status && status.herd_secret_set === false) {
    return jsxs('div', {
      className: 'flex min-w-0 items-center gap-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
      title: "Teammates can't sync with this gateway until it has a Herd secret.",
      children: [
        jsx(StatusDot, { tone: 'bad' }),
        jsx('span', {
          className: 'truncate',
          children: 'This gateway has no Herd secret set. Set one in Settings → Plugins → Herd.'
        })
      ]
    })
  }
  if (peers.length === 0) {
    const refused = refusedPeers(status)
    if (refused.length) {
      const first = refused[0]
      const who = first.name || first.url
      return jsxs('div', {
        className: 'flex min-w-0 items-center gap-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
        title: first.reason,
        children: [
          jsx(StatusDot, { tone: 'bad' }),
          jsx('span', { className: 'truncate', children: 'Refused ' + who + ' — ' + first.reason })
        ]
      })
    }
    const incoming = incomingUnlinked(status)
    if (incoming) {
      const who = incoming.name || 'A teammate'
      return jsxs('div', {
        className: 'flex min-w-0 items-center gap-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
        title: 'Add ' + who + ' back under Settings → Plugins → Herd to see link health here.',
        children: [jsx(StatusDot, { tone: 'good' }), jsx('span', { className: 'truncate', children: who + ' is connected' })]
      })
    }
    return jsxs('div', {
      className: 'flex items-center gap-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
      children: [
        jsx(StatusDot, { tone: 'muted' }),
        jsx('span', { className: 'truncate', children: 'No teammate connected' })
      ]
    })
  }
  // One line per teammate (spec §1.5): each one's own health, so a dead teammate never hides a live one.
  const lines = peers.map(peerLine).concat(refusedPeers(status).map(refusedLine))
  return lines.length === 1
    ? lines[0]
    : jsxs('div', { className: 'flex min-w-0 flex-col gap-0.5', children: lines })
}

function peerLine(peer) {
  const name = peer.remote_name || peer.name
  const tone = peer.connected ? 'good' : peer.last_attempt ? 'bad' : 'muted'
  const label = peer.connected
    ? 'Connected to ' + name
    : !peer.has_key
      ? 'Add ' + name + "'s Herd secret to connect"
      : peer.last_attempt
        ? "Can't reach " + name + ". Messages will send when they're back."
        : 'Connecting to ' + name + '…'
  return jsxs('div', {
    className: 'flex min-w-0 items-center gap-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
    title: peer.last_error || peer.url,
    children: [jsx(StatusDot, { tone }), jsx('span', { className: 'truncate', children: label })]
  })
}

// Desktop notifications for teammates' messages. The backend announces only rows new to this gateway, and only
// when the owner turned notify on. Here: one notification per channel per burst, a cooldown per channel, and a
// cap across channels. The host raises it only while Hermes is in the background (ctx.os.notify).
const NOTIFY_WINDOW_MS = 60000
const NOTIFY_MAX_PER_WINDOW = 4
const NOTIFY_CHANNEL_COOLDOWN_MS = 30000
const notifyState = { sent: [], lastByChannel: {} }

function notifyIncoming(payload, now = Date.now()) {
  const items = payload && Array.isArray(payload.items) ? payload.items : []
  if (!ctx || !ctx.os || typeof ctx.os.notify !== 'function') return 0
  const groups = new Map()
  for (const item of items) {
    if (!item || !item.channel_id) continue
    if (!groups.has(item.channel_id)) groups.set(item.channel_id, [])
    groups.get(item.channel_id).push(item)
  }
  notifyState.sent = notifyState.sent.filter(t => now - t < NOTIFY_WINDOW_MS)
  let fired = 0
  for (const [channelId, group] of groups) {
    const last = notifyState.lastByChannel[channelId]
    if (last !== undefined && now - last < NOTIFY_CHANNEL_COOLDOWN_MS) continue
    if (notifyState.sent.length >= NOTIFY_MAX_PER_WINDOW) break
    const first = group[0]
    const place = first.is_dm ? first.channel_name : '#' + first.channel_name
    const more = group.length - 1
    ctx.os.notify({
      title: first.mention ? 'Mentioned in ' + place : place,
      body: first.author_name + ': ' + first.preview + (more > 0 ? ' (+' + more + ' more)' : ''),
      activate: ROUTE_PATH
    })
    notifyState.sent.push(now)
    notifyState.lastByChannel[channelId] = now
    fired += 1
  }
  return fired
}

// The unread total for the status bar. Reads the same channels query as the page, so it never disagrees with it.
function UnreadCount() {
  const { data } = useQuery({
    queryKey: KEYS.channels,
    queryFn: () => api('/channels'),
    refetchInterval: REFRESH_MS
  })
  const total = Array.isArray(data) ? data.reduce((n, c) => n + ((c && c.unread) || 0), 0) : 0
  if (!total) return null
  return jsx('span', {
    className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
    title: 'Unread messages in Herd',
    children: 'Herd · ' + total + ' unread'
  })
}

function refusedLine(entry) {
  const who = entry.name || entry.url
  return jsxs('div', {
    className: 'flex min-w-0 items-center gap-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
    title: entry.reason,
    children: [jsx(StatusDot, { tone: 'bad' }), jsx('span', { className: 'truncate', children: 'Refused ' + who + ' — ' + entry.reason })]
  })
}

// ---------------------------------------------------------------------------
// New channel / new DM
// ---------------------------------------------------------------------------

// Up to four teammates besides you. A channel with no one ticked is open to the whole mesh; ticking people limits it
// to them. There is no private flag: a member list is the only restriction the backend has, and it is fixed at creation.
const MAX_PICKED_MEMBERS = 4

function NewChannelForm({ onDone }) {
  const { data: participants } = useQuery({ queryKey: KEYS.participants, queryFn: () => api('/participants') })
  const others = Array.isArray(participants) ? participants.filter(p => p && !p.is_self) : []
  const create = useMutation({
    mutationFn: ({ name, members }) => api('/channels', { method: 'POST', body: members.length ? { name, members } : { name } }),
    onSuccess: channel => {
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
      onDone(channel && channel.id)
    }
  })
  return jsxs('form', {
    className: 'flex flex-col gap-1.5',
    onSubmit: e => {
      e.preventDefault()
      const form = e.currentTarget
      const name = String(new FormData(form).get('name') || '').trim()
      const members = pickedMembers(form)
      if (name && !create.isPending) create.mutate({ name, members })
    },
    children: [
      others.length
        ? jsxs('fieldset', {
            className: 'flex flex-col gap-1 text-xs text-(--ui-text-secondary)',
            children: [
              jsx('legend', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: 'Only these people (optional, up to four)' }),
              others.map(p =>
                jsxs(
                  'label',
                  {
                    className: 'flex items-center gap-1.5',
                    children: [jsx('input', { type: 'checkbox', name: 'member', value: p.id }), jsx('span', { children: p.display_name })]
                  },
                  p.id
                )
              ),
              jsx('div', {
                className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
                children: 'Leave all unticked and everyone in the mesh receives it. The list is fixed once the channel exists. Private channels aren\u2019t supported yet.'
              })
            ]
          })
        : null,
      jsxs('div', {
        className: 'flex items-center gap-1.5',
        children: [
          jsx(Input, {
            name: 'name',
            placeholder: 'channel-name',
            autoComplete: 'off',
            autoFocus: true,
            'aria-label': 'Channel name',
            className: 'h-7 min-w-0 flex-1 text-xs'
          }),
          jsx(Button, { type: 'submit', size: 'xs', disabled: create.isPending, children: 'Create' }),
          jsx(Button, { type: 'button', size: 'xs', variant: 'secondary', onClick: () => onDone(null), children: 'Cancel' })
        ]
      }),
      create.isError
        ? jsx('div', {
            className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
            children: errorText(create.error, "Couldn't create the channel.")
          })
        : null
    ]
  })
}

// The ticked teammates, in form order. FormData lists only checked boxes, whatever their number.
function pickedMembers(form) {
  return new FormData(form).getAll('member').map(String).slice(0, MAX_PICKED_MEMBERS)
}

function NewDmPicker({ onDone }) {
  const { data } = useQuery({ queryKey: KEYS.participants, queryFn: () => api('/participants') })
  const others = (Array.isArray(data) ? data : []).filter(p => !p.is_self)
  const open = useMutation({
    mutationFn: ({ id }) => api('/dms', { method: 'POST', body: { participant_id: id } }),
    onSuccess: channel => {
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
      onDone(channel && channel.id)
    }
  })
  return jsxs('div', {
    className: 'flex flex-col gap-1',
    children: [
      others.length === 0
        ? jsx('div', {
            className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
            children: 'Nobody here yet. Connect a teammate first.'
          })
        : others.map(p =>
            jsx(
              Button,
              {
                type: 'button',
                size: 'xs',
                variant: 'secondary',
                disabled: open.isPending,
                onClick: () => open.mutate({ id: p.id }),
                children: p.display_name
              },
              p.id
            )
          ),
      jsx(Button, { type: 'button', size: 'xs', variant: 'ghost', onClick: () => onDone(null), children: 'Cancel' }),
      open.isError
        ? jsx('div', {
            className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
            children: errorText(open.error, "Couldn't open the conversation.")
          })
        : null
    ]
  })
}

// ---------------------------------------------------------------------------
// Channel list
// ---------------------------------------------------------------------------

function SectionHeader({ label }) {
  return jsx('div', {
    className: 'flex items-center justify-between px-1 pt-1',
    children: jsx('span', {
      className: 'text-[0.6875rem] font-medium uppercase tracking-wide text-(--ui-text-tertiary)',
      children: label
    })
  })
}

// Single '+' affordance with a two-item dropdown. Outside-click closes via a transparent backdrop;
// Escape closes via the focused menu (the plugin lint forbids document/window listeners).
function PlusMenu({ $open, onPick }) {
  const open = useValue($open)
  const close = () => $open.set(false)
  const item = (label, mode) =>
    jsx('button', {
      type: 'button',
      onClick: () => {
        close()
        onPick(mode)
      },
      className: 'rounded-[3px] px-2 py-1 text-left text-xs text-(--ui-text-secondary) hover:text-(--ui-accent)',
      children: label
    })
  return jsxs('div', {
    className: 'relative flex justify-end px-1',
    children: [
      jsx('button', {
        type: 'button',
        'aria-label': 'New',
        onClick: () => $open.set(!open),
        className:
          'flex size-5 items-center justify-center rounded-[3px] text-sm leading-none text-(--ui-text-tertiary) hover:text-(--ui-accent)',
        children: '+'
      }),
      open ? jsx('div', { className: 'fixed inset-0 z-10', onMouseDown: close }) : null,
      open
        ? jsxs('div', {
            tabIndex: -1,
            autoFocus: true,
            onKeyDown: e => e.key === 'Escape' && close(),
            className:
              'absolute right-1 top-6 z-20 flex min-w-32 flex-col gap-0.5 rounded-[3px] border border-(--ui-stroke-secondary) bg-(--ui-bg-primary) p-1 outline-none',
            children: [
              item('New channel', 'channel'),
              item('New message', 'dm'),
              // Adding a teammate is always one click away, not only on the empty first-run page.
              item('Invite a teammate', 'invite'),
              item('Join with an invite', 'join')
            ]
          })
        : null
    ]
  })
}

function ChannelButton({ channel, label, selected, onSelect }) {
  return jsxs('button', {
    type: 'button',
    onClick: () => onSelect(channel.id),
    title: channel.topic || label,
    className:
      'flex items-center justify-between gap-2 rounded-[3px] px-1.5 py-1 text-left text-xs ' +
      (selected ? 'font-medium text-(--ui-accent)' : 'text-(--ui-text-secondary) hover:text-(--ui-accent)'),
    children: [
      jsx('span', { className: 'truncate', children: label }),
      channel.unread && !selected
        ? jsx('span', {
            className: 'shrink-0 text-[0.6875rem] font-semibold text-(--ui-accent)',
            'aria-label': channel.unread + ' unread',
            children: String(channel.unread)
          })
        : jsx('span', {
            className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
            children: channel.message_count ? String(channel.message_count) : ''
          })
    ]
  })
}

// Who is in the room. A green dot means that person's Hermes exchanged messages with this one in the last few
// seconds. Clicking a teammate opens your DM with them; your own row renames you, without a trip to Settings.
const renaming = atom(false)

function PeopleList({ status, onSelect }) {
  const { data } = useQuery({ queryKey: KEYS.participants, queryFn: () => api('/participants') })
  const people = Array.isArray(data) ? data.filter(p => p && p.id) : []
  const editing = useValue(renaming)
  const openDm = useMutation({
    mutationFn: ({ id }) => api('/dms', { method: 'POST', body: { participant_id: id } }),
    onSuccess: channel => {
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
      if (channel && channel.id) onSelect(channel.id)
    }
  })
  const rename = useMutation({
    mutationFn: name => api('/profile', { method: 'POST', body: { display_name: name } }),
    onSuccess: () => {
      renaming.set(false)
      refreshAll()
    }
  })
  const phrases = {}
  for (const entry of (status && Array.isArray(status.peer_status) ? status.peer_status : [])) {
    if (entry && entry.gateway_id && entry.phrase) phrases[entry.gateway_id] = entry.phrase
  }
  const mine = status && status.agent_status && status.agent_status.phrase
  if (!people.length) return null
  return jsxs('div', {
    className: 'flex flex-col gap-0.5',
    children: [
      jsx(SectionHeader, { label: 'People' }),
      ...people.map(p => {
        if (p.is_self && editing) {
          return jsxs(
            'form',
            {
              className: 'flex items-center gap-1 px-1',
              onSubmit: e => {
                e.preventDefault()
                if (!rename.isPending) rename.mutate(String(new FormData(e.currentTarget).get('display_name') || '').trim())
              },
              children: [
                jsx(Input, {
                  name: 'display_name',
                  defaultValue: p.display_name,
                  maxLength: 64,
                  autoFocus: true,
                  'aria-label': 'Your name',
                  className: 'h-7 min-w-0 flex-1 text-xs',
                  onKeyDown: e => {
                    if (e.key !== 'Escape') return
                    e.stopPropagation()
                    renaming.set(false)
                  }
                }),
                jsx(Button, { type: 'submit', size: 'xs', disabled: rename.isPending, children: 'Save' })
              ]
            },
            p.id
          )
        }
        const phrase = p.is_self ? mine : phrases[p.id]
        return jsxs(
          'button',
          {
            type: 'button',
            disabled: !p.is_self && openDm.isPending,
            title: p.is_self
              ? 'This is you. Click to change your name.'
              : (p.online ? p.display_name + ' is online' : p.display_name + ' is away') + '. Click to message.',
            onClick: () => (p.is_self ? renaming.set(true) : openDm.mutate({ id: p.id })),
            className: 'flex min-w-0 items-center gap-1.5 rounded-[3px] px-1.5 py-1 text-left text-xs text-(--ui-text-secondary) hover:text-(--ui-accent)',
            children: [
              jsx(StatusDot, { tone: p.online ? 'good' : 'muted' }),
              jsx('span', { className: 'truncate', children: p.display_name }),
              p.is_self ? jsx('span', { className: 'shrink-0 text-[0.6875rem] text-(--ui-text-quaternary)', children: 'you' }) : null,
              phrase ? jsx('span', { className: 'truncate text-[0.6875rem] text-(--ui-text-quaternary)', children: 'agent ' + phrase }) : null
            ]
          },
          p.id
        )
      }),
      rename.isError
        ? jsx('div', { className: 'px-1 text-[0.6875rem] text-(--ui-text-tertiary)', children: errorText(rename.error, "Couldn't change your name.") })
        : null
    ]
  })
}

function ChannelList({ channels, selfId, selectedId, onSelect, compact, $composing, $menu, status }) {
  const mode = useValue($composing)
  const setMode = value => {
    if (value === 'invite' || value === 'join') {
      inviteLine.set('')
      pairingView.set(value === 'invite' ? 'show' : 'enter')
      return
    }
    $composing.set(value)
  }
  const done = id => {
    setMode(null)
    if (id) onSelect(id)
  }
  const rooms = channels.filter(c => !c.is_dm)
  const dms = channels.filter(c => c.is_dm)
  return jsxs('div', {
    className: compact
      ? 'flex max-h-56 shrink-0 flex-col gap-1 overflow-y-auto border-b border-(--ui-stroke-secondary) p-2'
      : 'flex w-56 shrink-0 flex-col gap-1 overflow-y-auto border-r border-(--ui-stroke-secondary) p-2',
    children: [
      jsx(PlusMenu, { $open: $menu, onPick: setMode }),
      jsx(SectionHeader, { label: 'Channels' }),
      mode === 'channel' ? jsx(NewChannelForm, { onDone: done }) : null,
      ...rooms.map(ch =>
        jsx(ChannelButton, { channel: ch, label: '# ' + ch.name, selected: ch.id === selectedId, onSelect }, ch.id)
      ),
      jsx(SectionHeader, { label: 'Direct messages' }),
      mode === 'dm' ? jsx(NewDmPicker, { onDone: done }) : null,
      ...dms.map(ch =>
        jsx(ChannelButton, { channel: ch, label: dmLabel(ch, selfId), selected: ch.id === selectedId, onSelect }, ch.id)
      ),
      jsx(PeopleList, { status, onSelect })
    ]
  })
}

// ---------------------------------------------------------------------------
// Messages + composer
// ---------------------------------------------------------------------------

function snippet(text, max) {
  const line = String(text || '').replace(/\s+/g, ' ').trim()
  return line.length > max ? line.slice(0, max - 1) + '…' : line
}

function ReplySummary({ message, onOpen }) {
  const count = message.reply_count
  const { data } = useQuery({
    queryKey: KEYS.thread(message.id),
    queryFn: () => api('/messages/' + encodeURIComponent(message.id) + '/thread')
  })
  const replies = data && Array.isArray(data.replies) ? data.replies : []
  const last = replies.length ? replies[replies.length - 1] : null
  return jsxs('button', {
    type: 'button',
    onClick: () => onOpen(message.id),
    title: 'Open thread',
    className:
      'flex min-w-0 items-center gap-2 rounded-[3px] py-0.5 text-left text-[0.6875rem] text-(--ui-text-tertiary) hover:text-(--ui-accent)',
    children: [
      jsx('span', { className: 'shrink-0 font-medium', children: count === 1 ? '1 reply' : count + ' replies' }),
      last
        ? jsx('span', {
            className: 'truncate text-(--ui-text-quaternary)',
            children: (last.author_name || 'someone') + ' · ' + timeLabel(last.created_at) + ' · ' + snippet(last.content, 80)
          })
        : jsx('span', { className: 'truncate text-(--ui-text-quaternary)', children: timeLabel(message.last_reply_at) })
    ]
  })
}

// ---------------------------------------------------------------------------
// @-mentions. Handle rules mirror dashboard/herd_store.py (mention_handles / mentions_me):
// a handle is the display name with runs of non-alphanumerics turned into '-', and
// `@handle` or `@handle-hermes` wakes that teammate's agent.
// ---------------------------------------------------------------------------

// Boundaries are Unicode-aware to mirror the Python side (`\w` is Unicode there):
// with an ASCII \w an "é@ty" or "K@ty" (U+212A) looked like a mention in JS but
// never woke anyone in Python. The token body stays ASCII because handles are
// ASCII slugs; the trigger body accepts any script so the menu stays open while
// the user is still typing the name.
const MENTION_TOKEN = /(?<![\p{L}\p{N}_@])@[A-Za-z0-9][A-Za-z0-9_-]*/gu
const MENTION_TRIGGER = /(?<![\p{L}\p{N}_@])@([\p{L}\p{N}_-]*)$/u

function mentionHandle(name) {
  // Lowercase BEFORE slugging, exactly like the Python `mention_handles`
  // (re.sub(r"[^a-z0-9]+", "-", display_name.lower())): "İlker" -> "i-lker",
  // "K" U+212A -> "k". Sluggling first kept the case and produced handles the
  // backend never matched.
  return String(name || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function mentionCandidates(participants, query) {
  const q = String(query || '').toLowerCase()
  const out = []
  ;(Array.isArray(participants) ? participants : []).forEach(p => {
    const handle = mentionHandle(p.display_name)
    if (p.is_self) {
      // Your own agent: tagging it from your own Herd wakes it (the backend's mentions_own_agent).
      out.push({ key: p.id + ':agent', handle: handle ? handle + '-hermes' : 'hermes', label: 'Your Hermes', agent: true })
      return
    }
    if (!handle) return
    out.push({ key: p.id + ':human', handle, label: p.display_name, agent: false })
    out.push({ key: p.id + ':agent', handle: handle + '-hermes', label: p.display_name + "'s Hermes", agent: true })
  })
  return out.filter(c => !q || c.handle.toLowerCase().includes(q) || c.label.toLowerCase().includes(q))
}

// The open @fragment ending at the caret, or null.
function mentionAtCaret(textarea) {
  const caret = textarea.selectionStart
  if (typeof caret !== 'number') return null
  const m = MENTION_TRIGGER.exec(textarea.value.slice(0, caret))
  return m ? { start: m.index, query: m[1], index: 0 } : null
}

function insertMention(textarea, state, handle, $mention) {
  const value = textarea.value
  const from = Math.max(textarea.selectionStart, state.start + 1)
  // Consume the rest of the word being typed. The @-fragment is anchored at the
  // caret, so picking with the caret mid-word would otherwise leave the tail
  // behind ("hey @peerXYZ" -> "hey @Peer-One XYZ"); QA F3.
  const tail = /^[A-Za-z0-9_-]*/.exec(value.slice(from))
  const end = from + (tail ? tail[0].length : 0)
  const token = '@' + handle + ' '
  textarea.value = value.slice(0, state.start) + token + value.slice(end)
  const caret = state.start + token.length
  textarea.focus()
  textarea.setSelectionRange(caret, caret)
  $mention.set(null)
}

// Plain strings + <span>s only (React escapes text), so message bodies stay XSS-safe.
// A safe markdown subset for message bodies: `code`, **bold** and *italic* (or _italic_). Built as React elements
// and text, never as HTML, so a message cannot inject markup. Underscores and asterisks inside a word don't count
// (snake_case_name stays as typed). Links are not rendered: their text is shown as typed.
const MARKUP_TOKEN = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|((?<![\p{L}\p{N}*])\*[^*\s][^*\n]*\*(?![\p{L}\p{N}*]))|((?<![\p{L}\p{N}_])_[^_\s][^_\n]*_(?![\p{L}\p{N}_]))/gu

function mentionParts(segment, offset) {
  const parts = []
  let last = 0
  for (const m of segment.matchAll(MENTION_TOKEN)) {
    if (m.index > last) parts.push(segment.slice(last, m.index))
    parts.push(jsx('span', { className: 'font-medium text-(--ui-accent)', children: m[0] }, 'm' + (offset + m.index)))
    last = m.index + m[0].length
  }
  if (last < segment.length) parts.push(segment.slice(last))
  return parts
}

function renderContent(text) {
  const str = String(text == null ? '' : text)
  const parts = []
  let last = 0
  for (const m of str.matchAll(MARKUP_TOKEN)) {
    if (m.index > last) parts.push(...mentionParts(str.slice(last, m.index), last))
    const raw = m[0]
    const key = 'f' + m.index
    if (raw.startsWith('`')) {
      parts.push(jsx('code', { className: 'rounded bg-(--ui-surface-secondary) px-1 font-mono text-[0.85em]', children: raw.slice(1, -1) }, key))
    } else if (raw.startsWith('**')) {
      parts.push(jsx('strong', { className: 'font-semibold', children: raw.slice(2, -2) }, key))
    } else {
      parts.push(jsx('em', { children: raw.slice(1, -1) }, key))
    }
    last = m.index + raw.length
  }
  if (last < str.length) parts.push(...mentionParts(str.slice(last), last))
  return parts
}

function MentionMenu({ items, index, onPick }) {
  return jsx('div', {
    role: 'listbox',
    'aria-label': 'Mention suggestions',
    className:
      'absolute bottom-full left-2 right-2 z-10 mb-1 flex max-h-48 flex-col overflow-y-auto rounded-md border border-(--ui-stroke-secondary) bg-(--ui-surface-primary) p-1 shadow-md',
    children: items.map((c, i) =>
      jsxs(
        'div',
        {
          role: 'option',
          'aria-selected': i === index,
          // mouseDown (not click) + preventDefault keeps focus in the textarea.
          onMouseDown: e => {
            e.preventDefault()
            onPick(e.currentTarget.closest('form'), c)
          },
          className:
            'flex cursor-pointer items-center justify-between gap-2 rounded px-2 py-1 text-xs ' +
            (i === index ? 'bg-(--ui-surface-secondary) text-(--ui-text-primary)' : 'text-(--ui-text-secondary)'),
          children: [
            jsx('span', { className: 'truncate', children: c.label }),
            jsx('span', { className: 'text-(--ui-text-tertiary)', children: '@' + c.handle })
          ]
        },
        c.key
      )
    )
  })
}

// Block-level markdown on top of renderContent's inline subset: fenced code, bullet and numbered lists, quotes
// and headings, which is what an agent's answer is made of. Still React elements and text only, never HTML.
const BLOCK_LINE = /^(?:(#{1,3})\s+(.+)|\s*([-*•])\s+(.+)|\s*(\d{1,3})[.)]\s+(.+)|>\s?(.*))$/
const HAS_BLOCKS = /(^|\n)(```|#{1,3}\s|\s*[-*•]\s|\s*\d{1,3}[.)]\s|>)/

const CODE_BLOCK_STYLE = {
  margin: '0.25rem 0',
  padding: '0.5rem',
  overflowX: 'auto',
  whiteSpace: 'pre',
  borderRadius: '4px',
  background: 'var(--ui-surface-secondary)',
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  fontSize: '0.75rem'
}
const LIST_ITEM_STYLE = { display: 'flex', gap: '0.375rem', paddingLeft: '0.25rem' }
const QUOTE_STYLE = { borderLeft: '2px solid var(--ui-stroke-secondary)', paddingLeft: '0.5rem', color: 'var(--ui-text-secondary)' }

function renderBody(text) {
  const str = String(text == null ? '' : text)
  if (!HAS_BLOCKS.test(str)) return renderContent(str) // plain messages render exactly as before
  const out = []
  let plain = []
  let code = null
  const flush = () => {
    if (!plain.length) return
    out.push(jsx('span', { children: renderContent(plain.join('\n')) }, 'p' + out.length))
    plain = []
  }
  // Inline styles, not utility classes: these shapes are new to the app, so no stylesheet is assumed to hold them.
  const block = (style, children) => {
    flush()
    out.push(jsx('div', { style, children }, 'b' + out.length))
  }
  const item = (marker, body) => [
    jsx('span', { style: { flexShrink: 0, color: 'var(--ui-text-tertiary)' }, children: marker }, 'd'),
    jsx('span', { style: { minWidth: 0 }, children: renderContent(body) }, 't')
  ]
  for (const line of str.split('\n')) {
    if (code) {
      if (line.trim() === '```') {
        block(CODE_BLOCK_STYLE, code.join('\n'))
        code = null
      } else code.push(line)
      continue
    }
    if (line.trimStart().startsWith('```')) {
      flush()
      code = []
      continue
    }
    const m = BLOCK_LINE.exec(line)
    if (!m) plain.push(line)
    else if (m[1]) block({ fontWeight: 600 }, renderContent(m[2]))
    else if (m[3]) block(LIST_ITEM_STYLE, item('•', m[4]))
    else if (m[5]) block(LIST_ITEM_STYLE, item(m[5] + '.', m[6]))
    else block(QUOTE_STYLE, renderContent(m[7] || ''))
  }
  if (code) block(CODE_BLOCK_STYLE, code.join('\n')) // an unclosed fence still reads as code
  flush()
  return out
}

// Exact local time for a timestamp's tooltip; the visible label stays relative.
function exactTime(iso) {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString()
}

function dayKey(iso) {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.getFullYear() + '-' + d.getMonth() + '-' + d.getDate()
}

function dayLabel(iso, now = new Date()) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const days = Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return d.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
}

// A message that continues the one above it (same author, same day, within five minutes) drops its header.
const GROUP_WINDOW_MS = 5 * 60 * 1000

function continuesPrevious(prev, m) {
  if (!prev || !m) return false
  if (prev.author_name !== m.author_name || prev.author_type !== m.author_type || prev.gateway_id !== m.gateway_id) return false
  if (m.task_id || dayKey(prev.created_at) !== dayKey(m.created_at)) return false
  const gap = Date.parse(m.created_at) - Date.parse(prev.created_at)
  return Number.isFinite(gap) && gap >= 0 && gap < GROUP_WINDOW_MS
}

const DIVIDER_LINE_STYLE = { height: '1px', flex: 1, background: 'var(--ui-stroke-secondary)' }

function DayDivider({ iso }) {
  const label = dayLabel(iso)
  if (!label) return null
  return jsxs('div', {
    role: 'separator',
    'aria-label': label,
    className: 'flex items-center gap-2 px-3 py-1.5 text-[0.6875rem] font-medium text-(--ui-text-tertiary)',
    children: [
      jsx('span', { style: DIVIDER_LINE_STYLE }),
      jsx('span', { children: label }),
      jsx('span', { style: DIVIDER_LINE_STYLE })
    ]
  })
}

// Keep the newest message in view, the way a chat does: when a list first appears, when you send, and when a new
// message lands while you are at (or near) the bottom. Scrolled up to read history, you are left where you are.
const NEAR_BOTTOM_PX = 240
const followState = { last: new Map(), nodes: new WeakSet() }

function scrollBox(node) {
  for (let el = node.parentElement; el; el = el.parentElement) {
    if (el.scrollHeight > el.clientHeight + 1) return el
  }
  return null
}

// Ref callback for the marker after the last row of a list. `listKey` names the list, `lastId` its newest row.
function followNewest(node, listKey, lastId, mine) {
  if (!node || !lastId) return false
  const fresh = !followState.nodes.has(node)
  followState.nodes.add(node)
  if (scrollTarget.get()) return false // a search jump owns the scroll position
  const prev = followState.last.get(listKey)
  followState.last.set(listKey, lastId)
  if (!fresh && prev === lastId) return false
  const box = scrollBox(node)
  const near = !box || box.scrollHeight - box.scrollTop - box.clientHeight < NEAR_BOTTOM_PX
  if (!(fresh || mine || near)) return false
  node.scrollIntoView({ block: 'end' })
  return true
}

function NewestMarker({ listKey, messages, selfId }) {
  const last = messages.length ? messages[messages.length - 1] : null
  return jsx('div', {
    'aria-hidden': 'true',
    style: { height: '1px' },
    ref: node => followNewest(node, listKey, last && last.id, Boolean(last && selfId && last.gateway_id === selfId))
  })
}

// Rows for a list of messages: a day divider where the date changes, and grouped rows under one header.
function messageRows(messages, rowProps) {
  const rows = []
  let prev = null
  for (const m of messages) {
    if (!prev || dayKey(prev.created_at) !== dayKey(m.created_at)) rows.push(jsx(DayDivider, { iso: m.created_at }, 'day:' + m.id))
    rows.push(jsx(MessageRow, { message: m, grouped: continuesPrevious(prev, m), ...rowProps }, m.id))
    prev = m
  }
  return rows
}

const REACTION_EMOJIS = ['👍', '❤️', '👀', '🎉']

// The reaction affordance. It is always in the row: faded in on hover and on keyboard focus (opacity, not
// display, so the trigger stays tabbable). The trigger opens a picker; arrow keys move between the emoji,
// Esc closes it and returns focus to the trigger, and leaving the picker closes it too.
function ReactionPicker({ message, react, onReply }) {
  const openId = useValue(reactionPicker)
  const open = openId === message.id
  const close = () => reactionPicker.set(null)
  const move = (e, delta) => {
    const items = Array.from(e.currentTarget.parentElement.querySelectorAll('[data-herd-emoji]'))
    items[(items.indexOf(e.currentTarget) + delta + items.length) % items.length].focus()
  }
  return jsxs('div', {
    className:
      'absolute -top-3 right-3 z-10 flex items-center gap-0.5 rounded-md border border-(--ui-stroke-secondary) bg-(--ui-surface-primary) px-1 py-0.5 ' +
      (open
        ? 'opacity-100'
        : 'pointer-events-none opacity-0 group-focus-within:pointer-events-auto group-focus-within:opacity-100 group-hover:pointer-events-auto group-hover:opacity-100'),
    onBlur: e => {
      if (open && !e.currentTarget.contains(e.relatedTarget)) close()
    },
    onKeyDown: e => {
      if (e.key !== 'Escape' || !open) return
      e.stopPropagation() // Esc closes the picker, not the thread panel behind it
      close()
      e.currentTarget.querySelector('[data-herd-react-trigger]').focus()
    },
    children: [
      jsx('button', {
        type: 'button',
        'data-herd-react-trigger': '',
        'aria-label': 'Add reaction',
        'aria-haspopup': 'true',
        'aria-expanded': String(open),
        title: 'Add reaction',
        disabled: react.isPending,
        className: 'rounded px-1 text-sm text-(--ui-text-tertiary) hover:bg-(--ui-surface-secondary)',
        onClick: () => reactionPicker.set(open ? null : message.id),
        children: '+'
      }),
      onReply && !open
        ? jsx('button', {
            type: 'button',
            'aria-label': 'Reply in thread',
            title: 'Reply in thread',
            className: 'rounded px-1 text-[0.6875rem] text-(--ui-text-tertiary) hover:bg-(--ui-surface-secondary)',
            onClick: () => onReply(message.id),
            children: 'Reply'
          })
        : null,
      open
        ? jsx('div', {
            role: 'group',
            'aria-label': 'Pick a reaction',
            className: 'flex gap-0.5',
            children: REACTION_EMOJIS.map((emoji, i) =>
              jsx(
                'button',
                {
                  type: 'button',
                  'data-herd-emoji': '',
                  autoFocus: i === 0,
                  title: 'React ' + emoji,
                  'aria-label': 'React ' + emoji,
                  disabled: react.isPending,
                  className: 'rounded px-1 text-sm hover:bg-(--ui-surface-secondary)',
                  onClick: () => {
                    close()
                    react.mutate(emoji)
                  },
                  onKeyDown: e => {
                    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') move(e, 1)
                    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') move(e, -1)
                    else return
                    e.preventDefault()
                  },
                  children: emoji
                },
                emoji
              )
            )
          })
        : null
    ]
  })
}

function MessageRow({ message, channelId: channelIdProp, onOpenThread, grouped }) {
  const channelId = channelIdProp || message.channel_id // thread panel rows carry their own channel
  useValue(scrollTarget) // re-render when a search jump is pending, so the ref below sees it
  // Only agent-authored messages carry a badge: humans read as the default, unbadged case (spec §3).
  const agent = message.author_type === 'agent'
  const reactions = Array.isArray(message.reactions) ? message.reactions : []
  const react = useMutation({
    mutationFn: emoji =>
      api(
        '/channels/' + encodeURIComponent(channelId) + '/messages/' + encodeURIComponent(message.id) + '/reactions',
        { method: 'POST', body: { emoji } }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.messages(channelId) })
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
    }
  })
  return jsxs('div', {
    className: 'group relative flex flex-col gap-0.5 px-3 ' + (grouped ? 'py-0.5' : 'py-1.5'),
    'data-herd-message-id': message.id,
    title: grouped ? exactTime(message.created_at) : undefined,
    ref: node => arriveAt(node, message.id),
    children: [
      jsx(ReactionPicker, { message, react, onReply: onOpenThread }),
      grouped ? null : jsxs('div', {
        className: 'flex items-center gap-2 text-[0.6875rem]',
        children: [
          jsx('span', { className: 'font-medium text-(--ui-text-secondary)', children: message.author_name || 'someone' }),
          agent ? jsx(Badge, { variant: 'muted', size: 'xs', children: 'agent' }) : null,
          jsx('span', { className: 'text-(--ui-text-quaternary)', title: exactTime(message.created_at), children: timeLabel(message.created_at) }),
          message.task_id ? jsx(TaskBadge, { taskId: message.task_id }) : null,
          onOpenThread
            ? jsx('button', {
                type: 'button',
                onClick: () => onOpenThread(message.id),
                className: 'text-(--ui-text-tertiary) hover:text-(--ui-accent)',
                children: 'Reply'
              })
            : null
        ]
      }),
      jsx('div', { className: 'whitespace-pre-wrap break-words text-sm', children: renderBody(message.content) }),
      message.wake_note
        ? jsx('div', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: message.wake_note })
        : null,
      reactions.length
        ? jsx('div', {
            className: 'mt-0.5 flex flex-wrap gap-1',
            children: reactions.map(r =>
              jsxs(
                'button',
                {
                  type: 'button',
                  disabled: react.isPending,
                  title: r.mine ? 'Remove your reaction' : 'React ' + r.emoji,
                  className:
                    'flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-xs ' +
                    (r.mine
                      ? 'border-(--ui-accent) bg-(--ui-surface-secondary) text-(--ui-text-primary)'
                      : 'border-(--ui-stroke-secondary) text-(--ui-text-secondary)'),
                  onClick: () => react.mutate(r.emoji),
                  children: [jsx('span', { children: r.emoji }), jsx('span', { children: String(r.count) })]
                },
                r.emoji
              )
            )
          })
        : null,
      onOpenThread && message.reply_count > 0 ? jsx(ReplySummary, { message, onOpen: onOpenThread }) : null
    ]
  })
}

// The channel's topic, with an inline editor for public channels. A DM has no topic, so it shows nothing here.
function TopicLine({ channel, $editing }) {
  const editingId = useValue($editing)
  const save = useMutation({
    mutationFn: topic => api('/channels/' + encodeURIComponent(channel.id) + '/topic', { method: 'POST', body: { topic } }),
    onSuccess: () => {
      $editing.set(null)
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
    }
  })
  if (channel.is_dm) return null
  if (editingId !== channel.id) {
    return jsxs('span', {
      className: 'flex min-w-0 items-baseline gap-1.5',
      children: [
        channel.topic ? jsx('span', { className: 'truncate text-xs text-(--ui-text-tertiary)', children: channel.topic }) : null,
        jsx('button', {
          type: 'button',
          className: 'shrink-0 text-[0.6875rem] text-(--ui-text-quaternary) hover:text-(--ui-accent)',
          onClick: () => $editing.set(channel.id),
          children: channel.topic ? 'Edit topic' : 'Add a topic'
        })
      ]
    })
  }
  return jsxs('form', {
    className: 'flex min-w-0 items-center gap-1',
    onSubmit: e => {
      e.preventDefault()
      save.mutate(String(new FormData(e.currentTarget).get('topic') || ''))
    },
    children: [
      jsx(Input, {
        name: 'topic',
        defaultValue: channel.topic || '',
        maxLength: 200,
        autoFocus: true,
        placeholder: 'What is this channel for?',
        'aria-label': 'Channel topic',
        className: 'h-7 min-w-0 w-64 text-xs',
        onKeyDown: e => {
          if (e.key !== 'Escape') return
          e.stopPropagation()
          $editing.set(null)
        }
      }),
      jsx(Button, { type: 'submit', size: 'xs', disabled: save.isPending, children: 'Save' }),
      jsx(Button, { type: 'button', size: 'xs', variant: 'secondary', onClick: () => $editing.set(null), children: 'Cancel' }),
      save.isError
        ? jsx('span', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: errorText(save.error, "Couldn't save the topic.") })
        : null
    ]
  })
}

function threadTitle(channel, selfId) {
  return channel.is_dm ? dmLabel(channel, selfId) : '# ' + channel.name
}

// The root message and its replies, oldest first. Shared by the side panel (route) and the in-column
// thread view (compact pane), so both read the same thread state through the same query.
function ThreadBody({ rootId }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: KEYS.thread(rootId),
    queryFn: () => api('/messages/' + encodeURIComponent(rootId) + '/thread')
  })
  const replies = data && Array.isArray(data.replies) ? data.replies : []
  if (isLoading) {
    return jsx('div', { className: 'p-3 text-xs text-(--ui-text-tertiary)', children: 'Loading…' })
  }
  if (isError || !data || !data.parent) {
    return jsx(EmptyState, { title: "Couldn't load this thread.", description: 'Herd will retry in a moment.' })
  }
  return jsxs('div', {
    className: 'flex flex-col py-1',
    children: [
      jsx(MessageRow, { message: data.parent }, data.parent.id),
      jsx('div', { className: 'mx-3 my-1 border-t border-(--ui-stroke-secondary)' }),
      replies.length === 0
        ? jsx('div', { className: 'px-3 py-1.5 text-xs text-(--ui-text-tertiary)', children: 'No replies yet.' })
        : null,
      ...messageRows(replies, {}),
      jsx(NewestMarker, { listKey: 'thread:' + rootId, messages: replies.length ? replies : [data.parent], selfId: null })
    ]
  })
}

// Compact pane: the thread replaces the message column (the 340px pane is too narrow for a side panel).
function ThreadView({ channel, rootId, selfId, status, $thread, compact }) {
  return jsxs('div', {
    className: 'flex min-h-0 min-w-0 flex-1 flex-col',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-3 border-b border-(--ui-stroke-secondary) px-3 py-2',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 items-baseline gap-2',
            children: [
              jsx('button', {
                type: 'button',
                onClick: () => $thread.set(null),
                className: 'shrink-0 text-xs text-(--ui-text-tertiary) hover:text-(--ui-accent)',
                children: '← Back to ' + threadTitle(channel, selfId)
              }),
              jsx('span', { className: 'truncate text-sm font-medium', children: 'Thread' })
            ]
          }),
          jsxs('div', {
            className: 'flex shrink-0 items-center gap-2',
            children: [
              canOpenWorkspace()
                ? jsx(Button, {
                    type: 'button',
                    size: 'xs',
                    variant: 'ghost',
                    title: 'Open this thread as a page',
                    onClick: () => openThreadWorkspace(channel, rootId),
                    children: 'Open as page'
                  })
                : null,
              jsx(PeerLine, { status })
            ]
          })
        ]
      }),
      jsx(WorkLine, { status }),
      jsx(ScrollArea, { className: 'min-h-0 flex-1', children: jsx(ThreadBody, { rootId }) }),
      jsx(Composer, { channel, compact, placeholderName: 'this thread', threadParentId: rootId })
    ]
  })
}

// Threads as a workspace page (Track 4). "Open as page" docks the thread as a main-area tab beside the chat; the
// 340px pane (or the route's thread panel) stays as the peek. Opening the same thread again fronts its tab.
const threadTabs = new Map() // root message id -> the close function of its open tab

function canOpenWorkspace() {
  return typeof host.openWorkspace === 'function'
}

function openThreadWorkspace(channel, rootId) {
  if (!canOpenWorkspace() || !rootId) return false
  const close = host.openWorkspace('herd-thread:' + rootId, {
    title: 'Thread · ' + (channel.is_dm ? channel.name : '#' + channel.name),
    minWidth: '22rem',
    render: () => jsx(ThreadWorkspace, { channel, rootId }),
    onClose: () => threadTabs.delete(rootId)
  })
  threadTabs.set(rootId, close)
  return true
}

function closeThreadWorkspace(rootId) {
  const close = threadTabs.get(rootId)
  threadTabs.delete(rootId)
  if (close) close()
}

function ThreadWorkspace({ channel, rootId }) {
  return jsxs('div', {
    className: 'flex h-full min-h-0 min-w-0 flex-col',
    onKeyDown: e => {
      // Esc closes the tab, as it closes the thread panel. A composer that used the key (the @-menu) keeps it.
      if (e.key !== 'Escape' || e.defaultPrevented) return
      e.preventDefault()
      closeThreadWorkspace(rootId)
    },
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-3 border-b border-(--ui-stroke-secondary) px-3 py-2',
        children: [
          jsx('span', { className: 'truncate text-sm font-medium', children: threadTitle(channel, null) }),
          jsx(WorkspacePageHeaderControl, {
            id: 'herd-thread-channel',
            children: jsx(Button, {
              type: 'button',
              size: 'xs',
              variant: 'ghost',
              onClick: () => {
                selection.page.set(channel.id)
                thread.page.set(rootId)
                host.navigate(ROUTE_PATH)
              },
              children: 'Open in Herd'
            })
          })
        ]
      }),
      jsx(ScrollArea, { className: 'min-h-0 flex-1', children: jsx(ThreadBody, { rootId }) }),
      jsx(Composer, { channel, compact: false, placeholderName: 'this thread', threadParentId: rootId })
    ]
  })
}

// Route: a right-hand panel beside the channel column (spec §2). Esc closes it. The composer takes focus when
// the panel opens, so Esc works straight away; a composer that consumed the key (the @-menu) keeps it.
function ThreadPanel({ channel, rootId, selfId, $thread }) {
  const close = () => $thread.set(null)
  return jsxs('section', {
    role: 'region',
    'aria-label': 'Thread',
    tabIndex: -1,
    onKeyDown: e => {
      if (e.key === 'Escape' && !e.defaultPrevented) {
        e.preventDefault()
        close()
      }
    },
    className:
      'flex min-h-0 w-[40%] min-w-64 max-w-[45%] shrink-0 flex-col border-l border-(--ui-stroke-secondary) bg-(--ui-bg-primary) outline-none',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-3 border-b border-(--ui-stroke-secondary) px-3 py-2',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 items-baseline gap-2',
            children: [
              jsx('span', { className: 'shrink-0 text-sm font-medium', children: 'Thread' }),
              jsx('span', { className: 'truncate text-xs text-(--ui-text-tertiary)', children: threadTitle(channel, selfId) })
            ]
          }),
          jsxs('div', {
            className: 'flex shrink-0 items-center gap-1',
            children: [
              canOpenWorkspace()
                ? jsx(Button, {
                    type: 'button',
                    size: 'xs',
                    variant: 'ghost',
                    title: 'Open this thread as a page',
                    onClick: () => openThreadWorkspace(channel, rootId),
                    children: 'Open as page'
                  })
                : null,
              jsx(Button, {
                type: 'button',
                size: 'xs',
                variant: 'ghost',
                'aria-label': 'Close thread',
                title: 'Close thread (Esc)',
                onClick: close,
                children: jsx(Codicon, { name: 'close', size: '0.8rem' })
              })
            ]
          })
        ]
      }),
      jsx(ScrollArea, { className: 'min-h-0 flex-1', children: jsx(ThreadBody, { rootId }) }),
      jsx(Composer, { channel, compact: false, placeholderName: 'this thread', threadParentId: rootId, autoFocus: true })
    ]
  })
}

function ShareDmForm({ channel, $sharing, onShared }) {
  const share = useMutation({
    mutationFn: ({ name }) =>
      api('/channels/' + encodeURIComponent(channel.id) + '/share', { method: 'POST', body: { name } }),
    onSuccess: created => {
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
      $sharing.set(false)
      if (created && created.id) onShared(created.id)
    }
  })
  return jsxs('form', {
    className: 'flex flex-col gap-1.5 border-b border-(--ui-stroke-secondary) px-3 py-2',
    onSubmit: e => {
      e.preventDefault()
      const name = String(new FormData(e.currentTarget).get('name') || '').trim()
      if (name && !share.isPending) share.mutate({ name })
    },
    children: [
      jsx('div', {
        className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
        children: 'Copies this conversation into a new channel. The direct message stays as it is.'
      }),
      jsxs('div', {
        className: 'flex items-center gap-1.5',
        children: [
          jsx(Input, {
            name: 'name',
            placeholder: 'new-channel-name',
            autoComplete: 'off',
            autoFocus: true,
            'aria-label': 'New channel name',
            className: 'h-7 min-w-0 flex-1 text-xs'
          }),
          jsx(Button, { type: 'submit', size: 'xs', disabled: share.isPending, children: 'Share' }),
          jsx(Button, { type: 'button', size: 'xs', variant: 'secondary', onClick: () => $sharing.set(false), children: 'Cancel' })
        ]
      }),
      share.isError
        ? jsx('div', {
            className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
            children: errorText(share.error, "Couldn't share this conversation.")
          })
        : null
    ]
  })
}

// The explicit tie an agent put on its own answer (F4): the task id it passed, plus the title read
// read-only from the local Kanban DB by our backend. No id means no badge — the pane never guesses
// one from the message text, and no title (missing DB / unknown id) means the id alone.
function TaskBadge({ taskId }) {
  const id = typeof taskId === 'string' ? taskId.trim() : ''
  const { data } = useQuery({
    queryKey: KEYS.task(id),
    enabled: Boolean(id),
    queryFn: () => api('/tasks/' + encodeURIComponent(id))
  })
  if (!id) return null
  const rawTitle = data && typeof data.title === 'string' ? data.title.trim() : ''
  return jsxs('button', {
    type: 'button',
    title: rawTitle ? id + ' — ' + rawTitle + ' · open the Kanban board' : id + ' · open the Kanban board',
    onClick: () => host.navigate('/kanban'),
    className: 'flex min-w-0 max-w-full items-center gap-1 rounded-full border border-(--ui-stroke-secondary) px-1.5 text-[0.6875rem] text-(--ui-text-secondary) hover:text-(--ui-accent)',
    children: [
      jsx(Codicon, { name: 'project', size: '0.7rem' }),
      jsx('span', { className: 'shrink-0', children: id }),
      rawTitle ? jsx('span', { className: 'truncate text-(--ui-text-quaternary)', children: '· ' + rawTitle }) : null
    ]
  })
}

// One plain-English phrase from the backend's fixed vocabulary, shown exactly as sent.
// No status from the backend means nothing is rendered: the pane never guesses or defaults.
// What each agent is doing: this gateway's own phrase first, then every teammate's (their last sync's phrase).
function WorkLine({ status }) {
  const work = status && status.agent_status
  const peers = status && Array.isArray(status.peer_status) ? status.peer_status : []
  const lines = []
  if (work && work.phrase) lines.push({ text: work.phrase, title: work.agent ? work.agent + ': ' + work.phrase : work.phrase })
  for (const peer of peers) {
    if (!peer || !peer.phrase) continue
    const who = peer.name || 'Teammate'
    lines.push({ text: who + "'s agent: " + peer.phrase, title: (peer.agent ? peer.agent + ' on ' : '') + who + ': ' + peer.phrase })
  }
  if (!lines.length) return null
  if (lines.length === 1) {
    return jsxs('div', {
      className:
        'flex items-center gap-1.5 border-b border-(--ui-stroke-secondary) px-3 py-1 text-[0.6875rem] text-(--ui-text-tertiary)',
      title: lines[0].title,
      children: [jsx(StatusDot, { tone: 'good' }), jsx('span', { className: 'truncate', children: lines[0].text })]
    })
  }
  return jsx('div', {
    className: 'flex flex-col border-b border-(--ui-stroke-secondary)',
    children: lines.map((line, i) =>
      jsxs(
        'div',
        {
          className: 'flex items-center gap-1.5 px-3 py-1 text-[0.6875rem] text-(--ui-text-tertiary)',
          title: line.title,
          children: [jsx(StatusDot, { tone: 'good' }), jsx('span', { className: 'truncate', children: line.text })]
        },
        i
      )
    )
  })
}

function MessageView({ channel, selfId, status, $thread, $selected, compact }) {
  const openThreadId = useValue($thread)
  const $sharing = compact ? sharing.pane : sharing.page
  const isSharing = useValue($sharing) && channel.is_dm
  const { data, isLoading, isError } = useQuery({
    queryKey: KEYS.messages(channel.id),
    queryFn: () =>
      api('/channels/' + encodeURIComponent(channel.id) + '/messages').then(rows => {
        // The channel is on screen, so it is read: move this gateway's cursor, then refresh the unread counts.
        api('/channels/' + encodeURIComponent(channel.id) + '/read', { method: 'POST' })
          .then(() => queryClient.invalidateQueries({ queryKey: KEYS.channels }))
          .catch(() => {})
        return rows
      })
  })
  const messages = Array.isArray(data) ? data : []
  const title = threadTitle(channel, selfId)
  if (openThreadId && compact) {
    return jsx(ThreadView, { channel, rootId: openThreadId, selfId, status, $thread, compact }, openThreadId)
  }
  const openThread = id => $thread.set(id)
  let body
  if (isLoading) {
    body = jsx('div', { className: 'p-3 text-xs text-(--ui-text-tertiary)', children: 'Loading…' })
  } else if (isError) {
    body = jsx(EmptyState, { title: "Couldn't load messages.", description: 'Herd will retry in a moment.' })
  } else if (messages.length === 0) {
    body = jsx(EmptyState, { title: 'No messages yet.', description: 'Say hi, or type @hermes to ask your own agent here.' })
  } else {
    body = jsx('div', {
      className: 'flex flex-col py-1',
      children: messageRows(messages, { channelId: channel.id, onOpenThread: openThread }).concat(
        jsx(NewestMarker, { listKey: 'channel:' + channel.id, messages, selfId }, 'newest')
      )
    })
  }
  return jsxs('div', {
    className: 'flex min-h-0 min-w-0 flex-1 flex-col',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-3 border-b border-(--ui-stroke-secondary) px-3 py-2',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 items-baseline gap-2',
            children: [
              jsx('span', { className: 'truncate text-sm font-medium', children: title }),
              jsx(TopicLine, { channel, $editing: compact ? topicEditing.pane : topicEditing.page })
            ]
          }),
          jsxs('div', {
            className: 'flex shrink-0 items-center gap-2',
            children: [
              channel.is_dm && messages.length > 0
                ? jsx(Button, {
                    type: 'button',
                    size: 'xs',
                    variant: 'secondary',
                    onClick: () => $sharing.set(!isSharing),
                    children: 'Share to a channel'
                  })
                : null,
              jsx(PeerLine, { status })
            ]
          })
        ]
      }),
      isSharing
        ? jsx(ShareDmForm, { channel, $sharing, onShared: id => { $thread.set(null); $selected.set(id) } })
        : null,
      jsx(WorkLine, { status }),
      jsx(ScrollArea, { className: 'min-h-0 flex-1', children: body }),
      jsx(Composer, { channel, compact, placeholderName: channel.is_dm ? dmLabel(channel, selfId) : '#' + channel.name })
    ]
  })
}

// Drafts live in the plugin's own storage, per channel (or per thread), so switching channels keeps what you typed.
function draftKey(channel, threadParentId) {
  return threadParentId ? 'draft:thread:' + threadParentId : 'draft:channel:' + channel.id
}

function readDraft(key) {
  return ctx ? String(ctx.storage.get(key, '') || '') : ''
}

function writeDraft(key, value) {
  if (!ctx) return
  if (value.trim()) ctx.storage.set(key, value)
  else ctx.storage.remove(key)
}

const EMOJI_TRAY = ['😀', '😂', '🙂', '😅', '🤔', '😎', '🥳', '😢', '👍', '👎', '👏', '🙌', '🙏', '👀', '💯', '🔥', '🎉', '✅', '❌', '⚠️', '🚀', '💡', '📌', '☕']

// Insert at the caret of a plain (uncontrolled) textarea and leave the caret after it.
function insertAtCaret(textarea, text) {
  const start = textarea.selectionStart == null ? textarea.value.length : textarea.selectionStart
  const end = textarea.selectionEnd == null ? start : textarea.selectionEnd
  textarea.value = textarea.value.slice(0, start) + text + textarea.value.slice(end)
  textarea.selectionStart = textarea.selectionEnd = start + text.length
  textarea.focus()
  return textarea.value
}

function Composer({ channel, compact, placeholderName, threadParentId, autoFocus }) {
  const focusAsked = useValue(composeRequest)
  const key = draftKey(channel, threadParentId)
  const $emoji = compact ? emojiTray.pane : emojiTray.page
  const trayOpen = useValue($emoji)
  const { data: participants } = useQuery({ queryKey: KEYS.participants, queryFn: () => api('/participants') })
  // Each composer keys its own autocomplete, so a dropdown opened in the pane can
  // never render (or mangle a draft) in the page — or the other way round.
  const $mention = compact ? mentionState.pane : mentionState.page
  const mention = useValue($mention)
  const items = mention ? mentionCandidates(participants, mention.query) : []
  const menuOpen = items.length > 0
  const activeIndex = mention ? Math.min(mention.index, items.length - 1) : 0
  const pick = (form, item) => {
    const textarea = form && form.elements.content
    if (textarea && mention) insertMention(textarea, mention, item.handle, $mention)
  }
  const send = useMutation({
    mutationFn: ({ content }) =>
      api('/channels/' + encodeURIComponent(channel.id) + '/messages', {
        method: 'POST',
        body: threadParentId
          ? { id: newMessageId(), content, thread_parent_id: threadParentId }
          : { id: newMessageId(), content }
      }),
    onSuccess: (_message, { form, draft }) => {
      // Clear the field and its saved draft. form.reset() would bring the draft back, since it resets to the default.
      if (form && form.elements.content) form.elements.content.value = ''
      writeDraft(draft, '')
      queryClient.invalidateQueries({ queryKey: KEYS.messages(channel.id) })
      queryClient.invalidateQueries({ queryKey: KEYS.threads })
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
    }
  })
  return jsxs('form', {
    className: 'relative flex flex-col gap-1.5 border-t border-(--ui-stroke-secondary) p-2',
    onSubmit: e => {
      e.preventDefault()
      const form = e.currentTarget
      const content = String(new FormData(form).get('content') || '')
      if (content.trim() && !send.isPending) send.mutate({ content, form, draft: key })
    },
    children: [
      menuOpen ? jsx(MentionMenu, { items, index: activeIndex, onPick: pick }) : null,
      trayOpen
        ? jsx('div', {
            role: 'group',
            'aria-label': 'Insert an emoji',
            className: 'flex flex-wrap gap-0.5 rounded-md border border-(--ui-stroke-secondary) bg-(--ui-surface-primary) p-1',
            children: EMOJI_TRAY.map(emoji =>
              jsx(
                'button',
                {
                  type: 'button',
                  title: emoji,
                  'aria-label': 'Insert ' + emoji,
                  className: 'rounded px-1 text-sm hover:bg-(--ui-surface-secondary)',
                  onClick: e => {
                    const form = e.currentTarget.form
                    const field = form && form.elements.content
                    if (!field) return
                    writeDraft(key, insertAtCaret(field, emoji))
                    $emoji.set(false)
                  },
                  children: emoji
                },
                emoji
              )
            )
          })
        : null,
      jsx(Textarea, {
        name: 'content',
        rows: 2,
        defaultValue: readDraft(key),
        autoFocus: Boolean(autoFocus) || (!compact && Date.now() - focusAsked < COMPOSE_FOCUS_MS),
        placeholder: threadParentId ? 'Reply in thread' : 'Message ' + placeholderName,
        'aria-label': 'Message',
        onChange: e => {
          writeDraft(key, e.currentTarget.value)
          $mention.set(mentionAtCaret(e.currentTarget))
        },
        onClick: e => $mention.set(mentionAtCaret(e.currentTarget)),
        onBlur: () => $mention.set(null),
        onKeyUp: e => {
          if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) $mention.set(mentionAtCaret(e.currentTarget))
        },
        onKeyDown: e => {
          if (menuOpen && !e.nativeEvent.isComposing) {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
              e.preventDefault()
              const next = e.key === 'ArrowDown' ? Math.min(items.length - 1, activeIndex + 1) : Math.max(0, activeIndex - 1)
              $mention.set({ ...mention, index: next })
              return
            }
            // Shift+Enter means "newline" even with the menu open (the submit path
            // below already guards it); without the guard it picked a mention. QA F4.
            if ((e.key === 'Enter' && !e.shiftKey) || e.key === 'Tab') {
              e.preventDefault()
              pick(e.currentTarget.form, items[activeIndex])
              return
            }
            if (e.key === 'Escape') {
              e.preventDefault()
              $mention.set(null)
              return
            }
          }
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            const form = e.currentTarget.form
            if (form) form.requestSubmit()
          }
        },
        className: 'min-h-0 resize-none text-sm'
      }, key),
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('span', {
            className: 'truncate text-[0.6875rem] text-(--ui-text-tertiary)',
            children: send.isError ? errorText(send.error, "Couldn't send. Try again.") : ''
          }),
          jsxs('div', {
            className: 'flex shrink-0 items-center gap-1.5',
            children: [
              jsx(Button, {
                type: 'button',
                size: 'xs',
                variant: 'secondary',
                'aria-expanded': String(trayOpen),
                onClick: () => $emoji.set(!trayOpen),
                children: 'Emoji'
              }),
              jsx(Button, { type: 'submit', size: 'xs', disabled: send.isPending, children: send.isPending ? 'Sending…' : 'Send' })
            ]
          })
        ]
      })
    ]
  })
}

// ---------------------------------------------------------------------------
// Page / pane
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Search: the ⌘K palette entry and the search box on the Herd page
// ---------------------------------------------------------------------------

const searchQuery = atom('') // what the page's search box holds; '' means no search
const jumpNote = atom(null) // one line after a jump whose message isn't in the loaded history, or null

// The backend's snippet marks each match as "[word]". Split it into text and <mark> parts; never HTML.
function snippetParts(snippet) {
  return String(snippet || '')
    .split(/(\[[^\]]*\])/)
    .filter(Boolean)
    .map((part, i) =>
      part.startsWith('[') && part.endsWith(']')
        ? jsx('mark', {
            key: i,
            className: 'rounded-sm bg-(--ui-surface-secondary) px-0.5 text-(--ui-text-primary)',
            children: part.slice(1, -1)
          })
        : part
    )
}

// A search hit waiting for its message row to render: { id } or null. Rows subscribe to it (MessageRow).
const scrollTarget = atom(null)

// Open a search hit: its channel (or its thread, for a reply). The row scrolls itself into view when it renders.
function openHit(hit) {
  jumpNote.set(null)
  searchQuery.set('')
  selection.page.set(hit.channel_id)
  thread.page.set(hit.thread_parent_id || null)
  scrollTarget.set({ id: hit.id })
  // The row may not be loaded yet, or may be older than the loaded history: give up after a short wait.
  ctx.setTimeout(() => {
    const pending = scrollTarget.get()
    if (pending && pending.id === hit.id) {
      scrollTarget.set(null)
      jumpNote.set('Opened ' + hit.channel_name + '. That message is older than the loaded history.')
    }
  }, 2500)
}

// Ref callback for a message row: if it is the pending search hit, bring it into view and flash it.
function arriveAt(node, id) {
  const pending = scrollTarget.get()
  if (!node || !pending || pending.id !== id) return
  scrollTarget.set(null)
  node.scrollIntoView({ block: 'center' })
  node.style.outline = '2px solid var(--ui-accent)'
  ctx.setTimeout(() => {
    node.style.outline = ''
  }, 1500)
}

function SearchResults({ term, results, failed }) {
  if (failed) {
    return jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: "Search couldn't run right now." })
  }
  if (results.length === 0) {
    return jsx('div', { className: 'text-xs text-(--ui-text-tertiary)', children: 'No messages match “' + term + '”.' })
  }
  return jsx('div', {
    role: 'list',
    'aria-label': 'Search results',
    className: 'flex max-h-64 flex-col overflow-y-auto',
    children: results.map(hit =>
      jsxs(
        'button',
        {
          type: 'button',
          role: 'listitem',
          onClick: () => openHit(hit),
          className: 'flex min-w-0 flex-col items-start gap-0.5 rounded px-2 py-1 text-left hover:bg-(--ui-surface-secondary)',
          children: [
            jsxs('div', {
              className: 'flex w-full min-w-0 items-center gap-2 text-[0.6875rem] text-(--ui-text-tertiary)',
              children: [
                jsx('span', {
                  className: 'truncate font-medium text-(--ui-text-secondary)',
                  children: hit.type === 'dm' ? hit.channel_name : '#' + hit.channel_name
                }),
                jsx('span', { className: 'truncate', children: hit.author_name }),
                jsx('span', { className: 'shrink-0', children: timeLabel(hit.created_at) }),
                hit.thread_parent_id ? jsx('span', { className: 'shrink-0', children: 'in thread' }) : null
              ]
            }),
            jsx('div', { className: 'w-full min-w-0 truncate text-xs', children: snippetParts(hit.snippet) })
          ]
        },
        hit.id
      )
    )
  })
}

function SearchBar() {
  const q = useValue(searchQuery)
  const note = useValue(jumpNote)
  const term = q.trim()
  const { data, isError } = useQuery({
    queryKey: [PLUGIN_ID, 'search', term],
    queryFn: () => (term ? api('/search?q=' + encodeURIComponent(term) + '&limit=25') : Promise.resolve({ results: [] }))
  })
  const results = data && Array.isArray(data.results) ? data.results : []
  return jsxs('div', {
    className: 'flex flex-col gap-1 border-b border-(--ui-stroke-secondary) px-3 py-2',
    children: [
      jsx(SearchField, {
        value: q,
        placeholder: 'Search messages…',
        inputClassName: 'h-7 text-xs',
        onChange: value => searchQuery.set(value),
        onKeyDown: e => {
          if (e.key !== 'Escape' || !q) return
          e.stopPropagation()
          searchQuery.set('')
        }
      }),
      note
        ? jsxs('div', {
            className: 'flex items-center justify-between gap-2 text-[0.6875rem] text-(--ui-text-tertiary)',
            children: [
              jsx('span', { children: note }),
              jsx('button', {
                type: 'button',
                className: 'hover:text-(--ui-accent)',
                onClick: () => jumpNote.set(null),
                children: 'Dismiss'
              })
            ]
          })
        : null,
      term ? jsx(SearchResults, { term, results, failed: Boolean(isError) }) : null
    ]
  })
}

// Pairing (Track 5): a one-time code instead of a long key. "Show" mints a code on this gateway; "Enter" exchanges a
// teammate's code for their Herd secret. The secret is kept only in this atom and shown once, for the owner to paste
// into Settings: Herd has no way to write Hermes's secret store, so it does not save the key for you.
const pairingView = atom(null) // null | 'show' | 'enter'
const pairingResult = atom(null) // { name, url, herd_secret } after a successful enter, until hidden
// The inviter's own gateway address, typed once and remembered, so a code can go out as one line: address#code.
const inviteLine = atom('')
const ADDRESS_KEY = 'gatewayAddress'

function buildInvite(address, code) {
  const clean = String(address || '').trim().replace(/\/+$/, '')
  return clean && code ? clean + '#' + code : ''
}

function PairingPanel() {
  const view = useValue(pairingView)
  const result = useValue(pairingResult)
  const invite = useValue(inviteLine)
  const mint = useMutation({
    mutationFn: () => api('/pairing-code', { method: 'POST' })
  })
  const redeem = useMutation({
    mutationFn: ({ url, code }) => api('/pair', { method: 'POST', body: { url, code } }),
    onSuccess: r => pairingResult.set(r)
  })
  const btn = (label, onClick) => jsx(Button, { type: 'button', size: 'xs', variant: 'secondary', onClick, children: label })
  if (result) {
    return jsxs('div', {
      className: 'flex flex-col gap-1.5 text-xs text-(--ui-text-secondary)',
      children: [
        jsx('div', { children: 'Paired with ' + result.name + '. Copy this key once, then paste it into Settings → Plugins → Herd → Teammate’s Herd secret, with the gateway address ' + result.url + '.' }),
        jsx('code', { className: 'break-all rounded bg-(--ui-surface-secondary) px-1.5 py-1 font-mono', children: result.herd_secret }),
        jsx('div', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: 'Herd can’t save this for you yet. Hide it once you have pasted it.' }),
        btn('Hide key', () => pairingResult.set(null))
      ]
    })
  }
  if (view === 'show') {
    const minted = mint.data
    return jsxs('div', {
      className: 'flex flex-col items-center gap-1.5 text-center text-xs text-(--ui-text-secondary)',
      children: [
        minted
          ? jsx('code', { className: 'font-mono text-base tracking-wider', children: minted.code })
          : jsx('div', { className: 'text-(--ui-text-tertiary)', children: mint.isPending ? 'Making a code…' : 'Make a code for your teammate.' }),
        minted
          ? jsx('div', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: 'Valid for ten minutes and for one use. Your teammate also needs this gateway’s address.' })
          : null,
        minted
          ? jsxs('form', {
              className: 'flex w-full flex-col gap-1.5',
              onSubmit: e => {
                e.preventDefault()
                const address = String(new FormData(e.currentTarget).get('address') || '').trim()
                if (ctx) ctx.storage.set(ADDRESS_KEY, address)
                const made = buildInvite(address, minted.code)
                inviteLine.set(made)
                if (made) copyText(made)
              },
              children: [
                jsx(Input, {
                  name: 'address',
                  defaultValue: ctx ? String(ctx.storage.get(ADDRESS_KEY, '') || '') : '',
                  placeholder: 'This gateway’s address, e.g. https://my-mac.tailnet-name.ts.net:8642',
                  'aria-label': 'This gateway’s address',
                  autoComplete: 'off',
                  className: 'h-7 text-xs'
                }),
                jsx(Button, { type: 'submit', size: 'xs', children: canCopy() ? 'Copy invite' : 'Make invite' }),
                invite
                  ? jsx('code', { className: 'break-all rounded bg-(--ui-surface-secondary) px-1.5 py-1 font-mono', children: invite })
                  : null,
                invite
                  ? jsx('div', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: 'Send this one line to your teammate. They paste it under “Enter a pairing code”.' })
                  : null
              ]
            })
          : null,
        mint.isError ? jsx('div', { children: errorText(mint.error, "Couldn't make a code.") }) : null,
        btn(minted ? 'Make a new code' : 'Make a code', () => {
          inviteLine.set('')
          mint.mutate()
        }),
        btn('Close', () => pairingView.set(null))
      ]
    })
  }
  if (view === 'enter') {
    return jsxs('form', {
      className: 'flex w-full flex-col gap-1.5',
      onSubmit: e => {
        e.preventDefault()
        const form = e.currentTarget
        const url = String(new FormData(form).get('url') || '').trim()
        const code = String(new FormData(form).get('code') || '').trim()
        // One pasted invite (address#code) is enough; the address and the code typed separately still work.
        if (url && (code || url.includes('#') || /\s/.test(url)) && !redeem.isPending) redeem.mutate({ url, code })
      },
      children: [
        jsx(Input, { name: 'url', placeholder: 'Paste the invite, or https://teammate.tailnet-name.ts.net:8642', 'aria-label': 'Invite, or teammate’s gateway address', autoComplete: 'off', className: 'h-7 text-xs' }),
        jsx(Input, { name: 'code', placeholder: 'Code (not needed with an invite)', 'aria-label': 'Pairing code', autoComplete: 'off', className: 'h-7 font-mono text-xs' }),
        jsxs('div', {
          className: 'flex items-center gap-1.5',
          children: [
            jsx(Button, { type: 'submit', size: 'xs', disabled: redeem.isPending, children: redeem.isPending ? 'Pairing…' : 'Pair' }),
            btn('Cancel', () => pairingView.set(null))
          ]
        }),
        redeem.isError ? jsx('div', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: errorText(redeem.error, "Couldn't pair.") }) : null
      ]
    })
  }
  return jsxs('div', {
    className: 'flex flex-wrap items-center justify-center gap-2',
    children: [
      btn('Show a pairing code', () => {
        mint.reset && mint.reset()
        pairingView.set('show')
      }),
      btn('Enter a pairing code', () => pairingView.set('enter'))
    ]
  })
}

// One honest line about @mention wake: whether the agent answers in a chat, or exactly what is missing. The
// one-click target comes from the pane's active session (host.state.activeSessionId), so no slash command.
function canCopy() {
  return Boolean(ctx && ctx.os && typeof ctx.os.writeClipboard === 'function')
}

function copyText(text) {
  if (!canCopy()) return
  try {
    const done = ctx.os.writeClipboard(String(text))
    if (done && typeof done.catch === 'function') done.catch(() => {})
  } catch (_err) {
    // the text is on screen either way
  }
}

function WakeBanner({ status }) {
  const activeSession = useValue(host.state.activeSessionId)
  const wake = status.wake
  const setTarget = useMutation({
    mutationFn: sessionKey =>
      api('/wake-target', { method: 'POST', body: { session_key: sessionKey, label: 'this chat' } }),
    onSuccess: refreshAll
  })
  const line = (tone, text, extra) =>
    jsxs('div', {
      className:
        'flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 border-b border-(--ui-stroke-secondary) px-3 py-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
      children: [jsx(StatusDot, { tone }), jsx('span', { className: 'min-w-0', children: text })].concat(extra || [])
    })
  if (!wake.enabled) {
    return line('muted', 'Your agent doesn’t answer @mentions. Turn on “Let my agent answer @mentions” in Settings.', [
      jsx(Button, { type: 'button', size: 'xs', onClick: openSettings, children: 'Settings' })
    ])
  }
  if (wake.blocked_reason === 'no_target') {
    return line('muted', 'Your agent isn’t answering @mentions yet.', [
      jsx(Button, {
        type: 'button',
        size: 'xs',
        disabled: !activeSession || setTarget.isPending,
        title: activeSession ? 'Answer @mentions in the chat you have open' : 'Open the chat your agent should answer in first',
        onClick: () => setTarget.mutate(activeSession),
        children: 'Answer @mentions here'
      })
    ])
  }
  if (wake.blocked_reason === 'injection_not_allowed') {
    return line('bad', wake.blocked_message, [
      jsx('code', { className: 'rounded bg-(--ui-surface-secondary) px-1 font-mono', children: wake.config_line }),
      canCopy()
        ? jsx(Button, { type: 'button', size: 'xs', variant: 'secondary', onClick: () => copyText(wake.config_line), children: 'Copy' })
        : null
    ])
  }
  if (wake.blocked_reason) return line('bad', wake.blocked_message)
  return line('good', 'Your agent answers @mentions in ' + wake.target_label + '.', [
    jsx(Button, {
      type: 'button',
      size: 'xs',
      disabled: setTarget.isPending,
      onClick: () => setTarget.mutate(''),
      children: 'Stop'
    })
  ])
}

function NoTeammate({ incoming }) {
  const who = incoming ? incoming.name || 'A teammate' : ''
  return jsxs('div', {
    className: 'flex flex-col items-center gap-2 border-b border-(--ui-stroke-secondary) px-3 py-3 text-center',
    children: incoming
      ? [
          jsx('div', { className: 'text-sm font-medium', children: who + ' is connected.' }),
          jsx('div', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children:
              who + ' connected to you. You can chat right now — add ' + who + ' back to see link health on this side too.'
          }),
          jsx(Button, { type: 'button', size: 'xs', onClick: openSettings, children: 'Add ' + who + ' back' }),
          jsx('div', {
            className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
            children:
              "Settings → Plugins → Herd → Teammate's name, gateway URL (e.g. http://tyler-mac.local:8642) and Teammate's Herd secret (the HERD_SECRET they set — not their API key)."
          })
        ]
      : [
          jsx('div', { className: 'text-sm font-medium', children: 'Nobody here yet.' }),
          jsx('div', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children: "Connect a teammate's Hermes to start a channel together."
          }),
          jsx(Button, { type: 'button', size: 'xs', onClick: openSettings, children: 'Connect a teammate' })
        ]
  })
}

function HerdView({ compact }) {
  const $selected = compact ? selection.pane : selection.page
  const $composing = compact ? composing.pane : composing.page
  const $menu = compact ? plusMenu.pane : plusMenu.page
  const $thread = compact ? thread.pane : thread.page
  const selectedId = useValue($selected)
  const threadId = useValue($thread)
  const statusQuery = useStatus()
  const status = statusQuery.data
  const { data, isLoading, isError } = useQuery({ queryKey: KEYS.channels, queryFn: () => api('/channels') })
  const channels = Array.isArray(data) ? data : []
  const selfId = status && status.self ? status.self.gateway_id : null
  const hasPeer = Boolean(status && ((status.peers && status.peers.length) || refusedPeers(status).length))
  const incoming = incomingUnlinked(status)
  const pairingOpen = useValue(pairingView)
  const pairingDone = useValue(pairingResult)

  if (isLoading) {
    return jsx('div', { className: 'p-3 text-xs text-(--ui-text-tertiary)', children: 'Loading Herd…' })
  }
  if (isError) {
    return jsx(EmptyState, {
      title: 'Herd is installed but its backend is off.',
      description: 'Enable the herd plugin for this profile (Capabilities → Plugins), then restart the gateway.'
    })
  }
  const selected =
    channels.find(c => c.id === selectedId) || channels.find(c => c.id === 'general') || channels[0] || null
  // The route's thread panel is a column of its own, so the channel column and the messages stay in view.
  const panel =
    !compact && threadId && selected
      ? jsx(ThreadPanel, { channel: selected, rootId: threadId, selfId, $thread }, threadId)
      : null

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col',
    children: [
      statusQuery.isSuccess && !hasPeer ? jsx(NoTeammate, { incoming }) : null,
      statusQuery.isSuccess && (!hasPeer || pairingOpen || pairingDone)
        ? jsx('div', { className: 'border-b border-(--ui-stroke-secondary) px-3 py-2', children: jsx(PairingPanel) })
        : null,
      statusQuery.isSuccess && status && status.wake ? jsx(WakeBanner, { status }) : null,
      compact ? null : jsx(SearchBar),
      jsxs('div', {
        className: compact ? 'flex min-h-0 flex-1 flex-col' : 'flex min-h-0 flex-1',
        children: [
          jsx(ChannelList, {
            channels,
            selfId,
            selectedId: selected ? selected.id : null,
            onSelect: id => {
              $thread.set(null) // switching channels closes any open thread
              $selected.set(id)
            },
            compact,
            $composing,
            $menu,
            status
          }),
          selected
            ? jsx(MessageView, { channel: selected, selfId, status, $thread, $selected, compact }, selected.id)
            : jsx(EmptyState, { title: 'No channels yet.', description: 'Create one with the + button.' }),
          panel
        ]
      })
    ]
  })
}

function HerdPage() {
  return jsx(HerdView, { compact: false })
}

function HerdPane() {
  return jsx(HerdView, { compact: true })
}

// ---------------------------------------------------------------------------
// Plugin
// ---------------------------------------------------------------------------

export default {
  id: PLUGIN_ID,
  name: 'Herd',
  defaultEnabled: false,

  register(hostCtx) {
    ctx = hostCtx
    rest = ctx.rest
    selection.page.set(null)
    selection.pane.set(null)
    composing.page.set(null)
    composing.pane.set(null)
    plusMenu.page.set(false)
    plusMenu.pane.set(false)
    thread.page.set(null)
    thread.pane.set(null)
    sharing.page.set(false)
    sharing.pane.set(false)
    mentionState.page.set(null)
    mentionState.pane.set(null)
    reactionPicker.set(null)
    searchQuery.set('')
    jumpNote.set(null)
    notifyState.sent = []
    notifyState.lastByChannel = {}
    composeRequest.set(0)
    pairingView.set(null)
    pairingResult.set(null)
    inviteLine.set('')
    renaming.set(false)
    followState.last.clear()
    emojiTray.page.set(false)
    emojiTray.pane.set(false)
    topicEditing.page.set(null)
    topicEditing.pane.set(null)
    threadTabs.clear()
    ctx.onDispose(() => {
      rest = null
      ctx = null
      pairingResult.set(null) // a pairing key never outlives the panel that showed it
    })

    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: ROUTE_PATH },
        render: () => jsx(HerdPage, {})
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        data: { path: ROUTE_PATH, label: 'Herd', codicon: 'comment-discussion' }
      },
      {
        id: 'open',
        area: KEYBINDS_AREA,
        data: {
          id: 'herd.open',
          category: 'navigation',
          defaults: ['mod+alt+h'],
          label: 'Open Herd',
          run: () => host.navigate(ROUTE_PATH)
        }
      },
      {
        id: 'new-message',
        area: KEYBINDS_AREA,
        data: {
          id: 'herd.newMessage',
          category: 'composer',
          defaults: ['mod+alt+n'],
          label: 'New Herd message',
          run: () => {
            composeRequest.set(Date.now())
            host.navigate(ROUTE_PATH)
          }
        }
      },
      {
        id: 'unread',
        area: STATUSBAR_AREAS.right,
        order: 70,
        render: () => jsx(UnreadCount, {})
      },
      {
        id: 'search',
        area: PALETTE_AREA,
        data: {
          id: 'herd.search',
          label: 'Search Herd messages',
          keywords: ['herd', 'search', 'find', 'messages', 'history'],
          run: () => {
            searchQuery.set('')
            host.navigate(ROUTE_PATH)
          }
        }
      },
      {
        id: 'pane',
        area: PANES_AREA,
        title: 'Herd',
        data: { placement: 'right', width: '340px' },
        render: () => jsx(HerdPane, {})
      }
    ])

    // Fast path: the backend broadcasts on every local post and every message pulled from the peer.
    ctx.onEvent('plugin.herd.message.created', event => {
      const payload = (event && event.payload) || {}
      if (payload.channel_id) queryClient.invalidateQueries({ queryKey: KEYS.messages(payload.channel_id) })
      queryClient.invalidateQueries({ queryKey: KEYS.threads }) // any open thread (and reply previews) may have grown
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
    })
    ctx.onEvent('plugin.herd.reactions.changed', event => {
      const payload = (event && event.payload) || {}
      if (payload.channel_id) queryClient.invalidateQueries({ queryKey: KEYS.messages(payload.channel_id) })
    })
    ctx.onEvent('plugin.herd.incoming.messages', event => {
      notifyIncoming(event && event.payload)
    })
    ctx.onEvent('plugin.herd.channels.changed', () => {
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
      queryClient.invalidateQueries({ queryKey: KEYS.participants })
    })
    // Accelerator only: the phrase itself always arrives via the /status query (polled every 3 s).
    ctx.onEvent('plugin.herd.status.changed', () => {
      queryClient.invalidateQueries({ queryKey: KEYS.status })
    })
    ctx.onEvent('plugin.herd.settings.changed', () => {
      api('/sync', { method: 'POST' }).catch(() => {}).finally(refreshAll)
    })

    // Fallback: events can drop (and sockets no-op on OAuth remotes), so poll too.
    ctx.setInterval(refreshAll, REFRESH_MS)
    ctx.setInterval(() => {
      api('/sync', { method: 'POST' })
        .then(() => queryClient.invalidateQueries({ queryKey: KEYS.status }))
        .catch(() => {})
    }, SYNC_MS)
  }
}
