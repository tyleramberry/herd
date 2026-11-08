// Herd — desktop half. Loaded uncompiled: plain ESM, jsx()/jsxs() calls, no JSX syntax.
// Imports are limited to '@hermes/plugin-sdk' and 'react/jsx-runtime' by design (catalog rule 8).
import {
  Badge,
  Button,
  Codicon,
  EmptyState,
  Input,
  PANES_AREA,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  ScrollArea,
  StatusDot,
  Textarea,
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
const selection = { page: atom(null), pane: atom(null) }
const composing = { page: atom(null), pane: atom(null) } // null | 'channel' | 'dm'
const plusMenu = { page: atom(false), pane: atom(false) } // is the '+' dropdown open
const thread = { page: atom(null), pane: atom(null) } // the open thread's root message id, or null
// Per-composer @-autocomplete: { page, pane } so the page and the pane never share
// (or ghost) one another's dropdown. null | { start, query, index }.
const sharing = { page: atom(false), pane: atom(false) } // is the DM's 'Share to a channel' form open (S-13)
const mentionState = { page: atom(null), pane: atom(null) }

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
  const peer = peers[0]
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

// ---------------------------------------------------------------------------
// New channel / new DM
// ---------------------------------------------------------------------------

function NewChannelForm({ onDone }) {
  const create = useMutation({
    mutationFn: ({ name }) => api('/channels', { method: 'POST', body: { name } }),
    onSuccess: channel => {
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
      onDone(channel && channel.id)
    }
  })
  return jsxs('form', {
    className: 'flex flex-col gap-1.5',
    onSubmit: e => {
      e.preventDefault()
      const name = String(new FormData(e.currentTarget).get('name') || '').trim()
      if (name && !create.isPending) create.mutate({ name })
    },
    children: [
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
            children: [item('New channel', 'channel'), item('New message', 'dm')]
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
      jsx('span', {
        className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
        children: channel.message_count ? String(channel.message_count) : ''
      })
    ]
  })
}

function ChannelList({ channels, selfId, selectedId, onSelect, compact, $composing, $menu }) {
  const mode = useValue($composing)
  const setMode = value => $composing.set(value)
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
      )
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
    if (p.is_self || !handle) return
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
function renderContent(text) {
  const str = String(text == null ? '' : text)
  const parts = []
  let last = 0
  for (const m of str.matchAll(MENTION_TOKEN)) {
    if (m.index > last) parts.push(str.slice(last, m.index))
    parts.push(jsx('span', { className: 'font-medium text-(--ui-accent)', children: m[0] }, 'm' + m.index))
    last = m.index + m[0].length
  }
  if (last < str.length) parts.push(str.slice(last))
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

const REACTION_EMOJIS = ['👍', '❤️', '👁️', '🎉']

function MessageRow({ message, channelId: channelIdProp, onOpenThread }) {
  const channelId = channelIdProp || message.channel_id // thread panel rows carry their own channel
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
    className: 'group relative flex flex-col gap-0.5 px-3 py-1.5',
    children: [
      jsx('div', {
        className:
          'absolute -top-3 right-3 hidden gap-0.5 rounded-md border border-(--ui-stroke-secondary) bg-(--ui-surface-primary) px-1 py-0.5 group-hover:flex',
        children: REACTION_EMOJIS.map(emoji =>
          jsx(
            'button',
            {
              type: 'button',
              title: 'React ' + emoji,
              disabled: react.isPending,
              className: 'rounded px-1 text-sm hover:bg-(--ui-surface-secondary)',
              onClick: () => react.mutate(emoji),
              children: emoji
            },
            emoji
          )
        )
      }),
      jsxs('div', {
        className: 'flex items-center gap-2 text-[0.6875rem]',
        children: [
          jsx('span', { className: 'font-medium text-(--ui-text-secondary)', children: message.author_name || 'someone' }),
          agent ? jsx(Badge, { variant: 'muted', size: 'xs', children: 'agent' }) : null,
          jsx('span', { className: 'text-(--ui-text-quaternary)', children: timeLabel(message.created_at) }),
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
      jsx('div', { className: 'whitespace-pre-wrap break-words text-sm', children: renderContent(message.content) }),
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

function threadTitle(channel, selfId) {
  return channel.is_dm ? dmLabel(channel, selfId) : '# ' + channel.name
}

function ThreadView({ channel, rootId, selfId, status, $thread, compact }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: KEYS.thread(rootId),
    queryFn: () => api('/messages/' + encodeURIComponent(rootId) + '/thread')
  })
  const replies = data && Array.isArray(data.replies) ? data.replies : []
  let body
  if (isLoading) {
    body = jsx('div', { className: 'p-3 text-xs text-(--ui-text-tertiary)', children: 'Loading…' })
  } else if (isError || !data || !data.parent) {
    body = jsx(EmptyState, { title: "Couldn't load this thread.", description: 'Herd will retry in a moment.' })
  } else {
    body = jsxs('div', {
      className: 'flex flex-col py-1',
      children: [
        jsx(MessageRow, { message: data.parent }, data.parent.id),
        jsx('div', { className: 'mx-3 my-1 border-t border-(--ui-stroke-secondary)' }),
        replies.length === 0
          ? jsx('div', { className: 'px-3 py-1.5 text-xs text-(--ui-text-tertiary)', children: 'No replies yet.' })
          : null,
        ...replies.map(m => jsx(MessageRow, { message: m }, m.id))
      ]
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
              jsx('button', {
                type: 'button',
                onClick: () => $thread.set(null),
                className: 'shrink-0 text-xs text-(--ui-text-tertiary) hover:text-(--ui-accent)',
                children: '← Back to ' + threadTitle(channel, selfId)
              }),
              jsx('span', { className: 'truncate text-sm font-medium', children: 'Thread' })
            ]
          }),
          jsx(PeerLine, { status })
        ]
      }),
      jsx(WorkLine, { status }),
      jsx(ScrollArea, { className: 'min-h-0 flex-1', children: body }),
      jsx(Composer, { channel, compact, placeholderName: 'this thread', threadParentId: rootId })
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
function WorkLine({ status }) {
  const work = status && status.agent_status
  if (!work || !work.phrase) return null
  return jsxs('div', {
    className:
      'flex items-center gap-1.5 border-b border-(--ui-stroke-secondary) px-3 py-1 text-[0.6875rem] text-(--ui-text-tertiary)',
    title: work.agent ? work.agent + ': ' + work.phrase : work.phrase,
    children: [jsx(StatusDot, { tone: 'good' }), jsx('span', { className: 'truncate', children: work.phrase })]
  })
}

function MessageView({ channel, selfId, status, $thread, $selected, compact }) {
  const openThreadId = useValue($thread)
  const $sharing = compact ? sharing.pane : sharing.page
  const isSharing = useValue($sharing) && channel.is_dm
  const { data, isLoading, isError } = useQuery({
    queryKey: KEYS.messages(channel.id),
    queryFn: () => api('/channels/' + encodeURIComponent(channel.id) + '/messages')
  })
  const messages = Array.isArray(data) ? data : []
  const title = threadTitle(channel, selfId)
  if (openThreadId) {
    return jsx(ThreadView, { channel, rootId: openThreadId, selfId, status, $thread, compact }, openThreadId)
  }
  const openThread = id => $thread.set(id)
  let body
  if (isLoading) {
    body = jsx('div', { className: 'p-3 text-xs text-(--ui-text-tertiary)', children: 'Loading…' })
  } else if (isError) {
    body = jsx(EmptyState, { title: "Couldn't load messages.", description: 'Herd will retry in a moment.' })
  } else if (messages.length === 0) {
    body = jsx(EmptyState, { title: 'No messages yet.', description: 'Say hi, or ask your agent to post here.' })
  } else {
    body = jsx('div', {
      className: 'flex flex-col py-1',
      children: messages.map(m => jsx(MessageRow, { message: m, channelId: channel.id, onOpenThread: openThread }, m.id))
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
              channel.topic
                ? jsx('span', { className: 'truncate text-xs text-(--ui-text-tertiary)', children: channel.topic })
                : null
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

function Composer({ channel, compact, placeholderName, threadParentId }) {
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
    onSuccess: (_message, { form }) => {
      form.reset()
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
      if (content.trim() && !send.isPending) send.mutate({ content, form })
    },
    children: [
      menuOpen ? jsx(MentionMenu, { items, index: activeIndex, onPick: pick }) : null,
      jsx(Textarea, {
        name: 'content',
        rows: 2,
        placeholder: threadParentId ? 'Reply in thread' : 'Message ' + placeholderName,
        'aria-label': 'Message',
        onChange: e => $mention.set(mentionAtCaret(e.currentTarget)),
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
      }),
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('span', {
            className: 'truncate text-[0.6875rem] text-(--ui-text-tertiary)',
            children: send.isError ? errorText(send.error, "Couldn't send. Try again.") : ''
          }),
          jsx(Button, { type: 'submit', size: 'xs', disabled: send.isPending, children: send.isPending ? 'Sending…' : 'Send' })
        ]
      })
    ]
  })
}

// ---------------------------------------------------------------------------
// Page / pane
// ---------------------------------------------------------------------------

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
  const statusQuery = useStatus()
  const status = statusQuery.data
  const { data, isLoading, isError } = useQuery({ queryKey: KEYS.channels, queryFn: () => api('/channels') })
  const channels = Array.isArray(data) ? data : []
  const selfId = status && status.self ? status.self.gateway_id : null
  const hasPeer = Boolean(status && ((status.peers && status.peers.length) || refusedPeers(status).length))
  const incoming = incomingUnlinked(status)

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

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col',
    children: [
      statusQuery.isSuccess && !hasPeer ? jsx(NoTeammate, { incoming }) : null,
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
            $menu
          }),
          selected
            ? jsx(MessageView, { channel: selected, selfId, status, $thread, $selected, compact }, selected.id)
            : jsx(EmptyState, { title: 'No channels yet.', description: 'Create one with the + button.' })
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

  register(ctx) {
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
    ctx.onDispose(() => {
      rest = null
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
