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
  messages: channelId => [PLUGIN_ID, 'messages', channelId]
}

// Module-scope state; reset on every register() (hot reload / re-enable).
let rest = null
const selection = { page: atom(null), pane: atom(null) }
const composing = { page: atom(null), pane: atom(null) } // null | 'channel' | 'dm'

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

function PeerLine({ status }) {
  const peers = (status && status.peers) || []
  if (peers.length === 0) {
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

function SectionHeader({ label, action, onAction }) {
  return jsxs('div', {
    className: 'flex items-center justify-between px-1 pt-1',
    children: [
      jsx('span', {
        className: 'text-[0.6875rem] font-medium uppercase tracking-wide text-(--ui-text-tertiary)',
        children: label
      }),
      jsx('button', {
        type: 'button',
        onClick: onAction,
        className: 'text-[0.6875rem] text-(--ui-text-tertiary) hover:text-(--ui-accent)',
        children: action
      })
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

function ChannelList({ channels, selfId, selectedId, onSelect, compact, $composing }) {
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
      jsx(SectionHeader, { label: 'Channels', action: 'New channel', onAction: () => setMode(mode === 'channel' ? null : 'channel') }),
      mode === 'channel' ? jsx(NewChannelForm, { onDone: done }) : null,
      ...rooms.map(ch =>
        jsx(ChannelButton, { channel: ch, label: '# ' + ch.name, selected: ch.id === selectedId, onSelect }, ch.id)
      ),
      jsx(SectionHeader, { label: 'Direct messages', action: 'New message', onAction: () => setMode(mode === 'dm' ? null : 'dm') }),
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

function MessageRow({ message }) {
  const isAgent = message.author_type === 'agent'
  return jsxs('div', {
    className: 'flex flex-col gap-0.5 px-3 py-1.5',
    children: [
      jsxs('div', {
        className: 'flex items-center gap-2 text-[0.6875rem]',
        children: [
          jsx('span', { className: 'font-medium text-(--ui-text-secondary)', children: message.author_name || 'someone' }),
          isAgent ? jsx(Badge, { variant: 'muted', size: 'xs', children: 'agent' }) : null,
          jsx('span', { className: 'text-(--ui-text-quaternary)', children: timeLabel(message.created_at) })
        ]
      }),
      jsx('div', { className: 'whitespace-pre-wrap break-words text-sm', children: message.content })
    ]
  })
}

function MessageView({ channel, selfId, status }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: KEYS.messages(channel.id),
    queryFn: () => api('/channels/' + encodeURIComponent(channel.id) + '/messages')
  })
  const messages = Array.isArray(data) ? data : []
  const title = channel.is_dm ? dmLabel(channel, selfId) : '# ' + channel.name
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
      children: messages.map(m => jsx(MessageRow, { message: m }, m.id))
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

function Composer({ channel, placeholderName }) {
  const send = useMutation({
    mutationFn: ({ content }) =>
      api('/channels/' + encodeURIComponent(channel.id) + '/messages', {
        method: 'POST',
        body: { id: newMessageId(), content }
      }),
    onSuccess: (_message, { form }) => {
      form.reset()
      queryClient.invalidateQueries({ queryKey: KEYS.messages(channel.id) })
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
        placeholder: 'Message ' + placeholderName,
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

function NoTeammate() {
  return jsxs('div', {
    className: 'flex flex-col items-center gap-2 border-b border-(--ui-stroke-secondary) px-3 py-3 text-center',
    children: [
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
  const selectedId = useValue($selected)
  const statusQuery = useStatus()
  const status = statusQuery.data
  const { data, isLoading, isError } = useQuery({ queryKey: KEYS.channels, queryFn: () => api('/channels') })
  const channels = Array.isArray(data) ? data : []
  const selfId = status && status.self ? status.self.gateway_id : null
  const hasPeer = Boolean(status && status.peers && status.peers.length)

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
      statusQuery.isSuccess && !hasPeer ? jsx(NoTeammate, {}) : null,
      jsxs('div', {
        className: compact ? 'flex min-h-0 flex-1 flex-col' : 'flex min-h-0 flex-1',
        children: [
          jsx(ChannelList, {
            channels,
            selfId,
            selectedId: selected ? selected.id : null,
            onSelect: id => $selected.set(id),
            compact,
            $composing
          }),
          selected
            ? jsx(MessageView, { channel: selected, selfId, status }, selected.id)
            : jsx(EmptyState, { title: 'No channels yet.', description: 'Create one with New channel.' })
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
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
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
