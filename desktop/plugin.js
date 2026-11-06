// Herd — desktop half. Loaded uncompiled: plain ESM, jsx()/jsxs() calls, no JSX syntax.
// Imports are limited to '@hermes/plugin-sdk' and 'react/jsx-runtime' by design (catalog rule 8).
import {
  Badge,
  Button,
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
  threads: [PLUGIN_ID, 'thread'],
  thread: messageId => [PLUGIN_ID, 'thread', messageId]
}

// Module-scope state; reset on every register() (hot reload / re-enable).
let rest = null
const selection = { page: atom(null), pane: atom(null) }
const composing = { page: atom(null), pane: atom(null) } // null | 'channel' | 'dm'
const plusMenu = { page: atom(false), pane: atom(false) } // is the '+' dropdown open
const thread = { page: atom(null), pane: atom(null) } // the open thread's root message id, or null

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

function PeerLine({ status }) {
  const peers = (status && status.peers) || []
  if (peers.length === 0) {
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
      ? 'Add ' + name + "'s key to connect"
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

const REACTION_EMOJIS = ['👍', '❤️', '👁️', '🎉']

function MessageRow({ message, channelId: channelIdProp, onOpenThread }) {
  const channelId = channelIdProp || message.channel_id // thread panel rows carry their own channel
  const isAgent = message.author_type === 'agent'
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
          isAgent ? jsx(Badge, { variant: 'muted', size: 'xs', children: 'agent' }) : null,
          jsx('span', { className: 'text-(--ui-text-quaternary)', children: timeLabel(message.created_at) }),
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
      jsx('div', { className: 'whitespace-pre-wrap break-words text-sm', children: message.content }),
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

function ThreadView({ channel, rootId, selfId, status, $thread }) {
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
      jsx(ScrollArea, { className: 'min-h-0 flex-1', children: body }),
      jsx(Composer, { channel, placeholderName: 'this thread', threadParentId: rootId })
    ]
  })
}

function MessageView({ channel, selfId, status, $thread }) {
  const openThreadId = useValue($thread)
  const { data, isLoading, isError } = useQuery({
    queryKey: KEYS.messages(channel.id),
    queryFn: () => api('/channels/' + encodeURIComponent(channel.id) + '/messages')
  })
  const messages = Array.isArray(data) ? data : []
  const title = threadTitle(channel, selfId)
  if (openThreadId) {
    return jsx(ThreadView, { channel, rootId: openThreadId, selfId, status, $thread }, openThreadId)
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
          jsx(PeerLine, { status })
        ]
      }),
      jsx(ScrollArea, { className: 'min-h-0 flex-1', children: body }),
      jsx(Composer, { channel, placeholderName: channel.is_dm ? dmLabel(channel, selfId) : '#' + channel.name })
    ]
  })
}

function Composer({ channel, placeholderName, threadParentId }) {
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
    className: 'flex flex-col gap-1.5 border-t border-(--ui-stroke-secondary) p-2',
    onSubmit: e => {
      e.preventDefault()
      const form = e.currentTarget
      const content = String(new FormData(form).get('content') || '')
      if (content.trim() && !send.isPending) send.mutate({ content, form })
    },
    children: [
      jsx(Textarea, {
        name: 'content',
        rows: 2,
        placeholder: threadParentId ? 'Reply in thread' : 'Message ' + placeholderName,
        'aria-label': 'Message',
        onKeyDown: e => {
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
              "Settings → Plugins → Herd → Teammate's name, gateway URL (e.g. http://tyler-mac.local:8642) and API key (their API_SERVER_KEY)."
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
  const hasPeer = Boolean(status && status.peers && status.peers.length)
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
            ? jsx(MessageView, { channel: selected, selfId, status, $thread }, selected.id)
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
