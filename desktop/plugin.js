// Herd — desktop half. Loaded uncompiled: plain ESM, jsx()/jsxs() calls, no JSX syntax.
// Imports are limited to '@hermes/plugin-sdk' and 'react/jsx-runtime' by design.
import {
  Button,
  EmptyState,
  Input,
  PANES_AREA,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  ScrollArea,
  Textarea,
  host,
  queryClient,
  relativeTime,
  atom,
  useMutation,
  useQuery,
  useValue
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const PLUGIN_ID = 'herd'
const ROUTE_PATH = '/herd'
const POLL_MS = 5000

const KEYS = {
  all: [PLUGIN_ID],
  channels: [PLUGIN_ID, 'channels'],
  messages: channelId => [PLUGIN_ID, 'messages', channelId]
}

// Module-scope state; reset on every register() (hot reload / re-enable).
let rest = null
const selection = { page: atom(null), pane: atom(null) }

function api(path, opts) {
  if (!rest) return Promise.reject(new Error('Herd is not registered'))
  return rest(path, opts)
}

function newMessageId() {
  const c = globalThis.crypto
  return c && typeof c.randomUUID === 'function' ? c.randomUUID() : undefined
}

function authorName() {
  try {
    return host.state.profile.get() || 'me'
  } catch {
    return 'me'
  }
}

function timeLabel(iso) {
  const ms = Date.parse(iso)
  return Number.isFinite(ms) ? relativeTime(ms) : ''
}

// ---------------------------------------------------------------------------
// Create channel
// ---------------------------------------------------------------------------

function CreateChannelForm({ onCreated }) {
  const create = useMutation({
    mutationFn: ({ name }) => api('/channels', { method: 'POST', body: { name } }),
    onSuccess: (channel, { form }) => {
      form.reset()
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
      if (onCreated && channel && channel.id) onCreated(channel.id)
    }
  })
  return jsxs('form', {
    className: 'flex flex-col gap-1.5',
    onSubmit: e => {
      e.preventDefault()
      const form = e.currentTarget
      const name = String(new FormData(form).get('name') || '').trim()
      if (name && !create.isPending) create.mutate({ name, form })
    },
    children: [
      jsxs('div', {
        className: 'flex items-center gap-1.5',
        children: [
          jsx(Input, {
            name: 'name',
            placeholder: 'new-channel',
            autoComplete: 'off',
            'aria-label': 'Channel name',
            className: 'h-7 min-w-0 flex-1 text-xs'
          }),
          jsx(Button, {
            type: 'submit',
            size: 'xs',
            disabled: create.isPending,
            children: create.isPending ? 'Creating…' : 'Create'
          })
        ]
      }),
      create.isError
        ? jsx('div', {
            className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
            children: String((create.error && create.error.message) || 'Could not create channel')
          })
        : null
    ]
  })
}

// ---------------------------------------------------------------------------
// Channel list
// ---------------------------------------------------------------------------

function ChannelList({ channels, selectedId, onSelect, compact }) {
  return jsxs('div', {
    className: compact
      ? 'flex flex-col gap-2 border-b border-(--ui-stroke-secondary) p-2'
      : 'flex w-52 shrink-0 flex-col gap-2 border-r border-(--ui-stroke-secondary) p-2',
    children: [
      jsx('div', {
        className: 'px-1 text-[0.6875rem] font-medium uppercase tracking-wide text-(--ui-text-tertiary)',
        children: 'Channels'
      }),
      jsx('div', {
        className: compact ? 'flex flex-wrap gap-1' : 'flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto',
        children: channels.map(ch =>
          jsxs(
            'button',
            {
              type: 'button',
              onClick: () => onSelect(ch.id),
              title: ch.topic || ch.name,
              className:
                'flex items-center justify-between gap-2 rounded-[3px] px-1.5 py-1 text-left text-xs ' +
                (ch.id === selectedId
                  ? 'font-medium text-(--ui-accent)'
                  : 'text-(--ui-text-secondary) hover:text-(--ui-accent)'),
              children: [
                jsx('span', { className: 'truncate', children: '# ' + ch.name }),
                compact
                  ? null
                  : jsx('span', {
                      className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
                      children: ch.message_count ? String(ch.message_count) : ''
                    })
              ]
            },
            ch.id
          )
        )
      }),
      compact ? null : jsx(CreateChannelForm, { onCreated: onSelect })
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
        className: 'flex items-baseline gap-2 text-[0.6875rem]',
        children: [
          jsx('span', {
            className: 'font-medium ' + (isAgent ? 'text-(--ui-accent)' : 'text-(--ui-text-secondary)'),
            children: (message.author_name || (isAgent ? 'Hermes' : 'someone')) + (isAgent ? ' · agent' : '')
          }),
          jsx('span', { className: 'text-(--ui-text-quaternary)', children: timeLabel(message.created_at) }),
          message.gateway_id && message.gateway_id !== 'local'
            ? jsx('span', { className: 'text-(--ui-text-quaternary)', children: '@' + message.gateway_id })
            : null
        ]
      }),
      jsx('div', { className: 'whitespace-pre-wrap break-words text-sm', children: message.content })
    ]
  })
}

function MessageView({ channel }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: KEYS.messages(channel.id),
    queryFn: () => api('/channels/' + encodeURIComponent(channel.id) + '/messages')
  })
  const messages = Array.isArray(data) ? data : []
  let body
  if (isLoading) {
    body = jsx('div', { className: 'p-3 text-xs text-(--ui-text-tertiary)', children: 'Loading…' })
  } else if (isError) {
    body = jsx(EmptyState, {
      title: 'Herd backend unavailable',
      description: 'Enable the herd agent plugin (plugins.enabled) and restart the gateway.'
    })
  } else if (messages.length === 0) {
    body = jsx(EmptyState, { title: 'No messages yet', description: 'Say hi in #' + channel.name + '.' })
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
        className: 'flex items-baseline gap-2 border-b border-(--ui-stroke-secondary) px-3 py-2',
        children: [
          jsx('span', { className: 'text-sm font-medium', children: '# ' + channel.name }),
          channel.topic
            ? jsx('span', { className: 'truncate text-xs text-(--ui-text-tertiary)', children: channel.topic })
            : null
        ]
      }),
      jsx(ScrollArea, { className: 'min-h-0 flex-1', children: body }),
      jsx(Composer, { channel })
    ]
  })
}

function Composer({ channel }) {
  const send = useMutation({
    mutationFn: ({ content }) =>
      api('/channels/' + encodeURIComponent(channel.id) + '/messages', {
        method: 'POST',
        body: { id: newMessageId(), content, author_name: authorName(), author_type: 'human' }
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
        placeholder: 'Message #' + channel.name + '  (Enter to send, Shift+Enter for newline)',
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
            children: send.isError ? String((send.error && send.error.message) || 'Send failed') : ''
          }),
          jsx(Button, {
            type: 'submit',
            size: 'xs',
            disabled: send.isPending,
            children: send.isPending ? 'Sending…' : 'Send'
          })
        ]
      })
    ]
  })
}

// ---------------------------------------------------------------------------
// Page / pane
// ---------------------------------------------------------------------------

function HerdView({ compact }) {
  const $selected = compact ? selection.pane : selection.page
  const selectedId = useValue($selected)
  const setSelectedId = id => $selected.set(id)
  const { data, isLoading, isError } = useQuery({
    queryKey: KEYS.channels,
    queryFn: () => api('/channels')
  })
  const channels = Array.isArray(data) ? data : []

  if (isLoading) {
    return jsx('div', { className: 'p-3 text-xs text-(--ui-text-tertiary)', children: 'Loading Herd…' })
  }
  if (isError) {
    return jsx(EmptyState, {
      title: 'Herd backend unavailable',
      description: 'Enable the herd agent plugin (plugins.enabled in config.yaml) and restart the gateway.'
    })
  }
  if (channels.length === 0) {
    return jsxs('div', {
      className: 'flex h-full flex-col items-center justify-center gap-3 p-4',
      children: [
        jsx(EmptyState, {
          title: 'No channels yet',
          description: 'Create a channel to start talking with your herd.',
          className: 'min-h-0'
        }),
        jsx('div', { className: 'w-full max-w-72', children: jsx(CreateChannelForm, { onCreated: setSelectedId }) })
      ]
    })
  }

  const selected =
    channels.find(c => c.id === selectedId) || channels.find(c => c.name === 'general') || channels[0]

  return jsxs('div', {
    className: compact ? 'flex h-full min-h-0 flex-col' : 'flex h-full min-h-0',
    children: [
      jsx(ChannelList, { channels, selectedId: selected.id, onSelect: setSelectedId, compact }),
      jsx(MessageView, { channel: selected }, selected.id)
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
        title: 'herd',
        data: { placement: 'right', width: '320px' },
        render: () => jsx(HerdPane, {})
      }
    ])

    // Live: the backend broadcasts plugin.herd.message.created on every insert.
    // Subscriptions made during register() are retired with the plugin.
    host.onEvent('plugin.herd.message.created', event => {
      const payload = (event && event.payload) || {}
      if (payload.channel_id) {
        queryClient.invalidateQueries({ queryKey: KEYS.messages(payload.channel_id) })
      } else {
        queryClient.invalidateQueries({ queryKey: [PLUGIN_ID, 'messages'] })
      }
      queryClient.invalidateQueries({ queryKey: KEYS.channels })
    })

    // Fallback: events can drop (and sockets no-op on OAuth remotes) — poll.
    ctx.setInterval(() => {
      queryClient.invalidateQueries({ queryKey: KEYS.all })
    }, POLL_MS)
  }
}
