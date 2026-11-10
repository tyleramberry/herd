// Pane probe — imports the SHIPPED desktop/plugin.js with the plugin SDK stubbed and drives the
// real MessageRow (reaction affordance + picker + pills) and WakeBanner, so the behaviour is checked by
// running the pane code rather than by grepping its source. Same method as s15_pane_render_probe.mjs:
// only the two import specifiers are rewritten; no code is re-typed, no dynamic evaluation.
//
//     node tests/pane_probe.mjs [path/to/plugin.js]
// Exit code 0 when every check passes; each check prints one line.
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pluginPath = process.argv[2] || resolve(here, '../desktop/plugin.js')
const source = readFileSync(pluginPath, 'utf8')

const work = mkdtempSync(join(tmpdir(), 'track0-probe-'))
writeFileSync(join(work, 'sdk.mjs'), `
export const Badge = 'Badge'
export const Button = 'Button'
export const Codicon = 'Codicon'
export const EmptyState = 'EmptyState'
export const Input = 'Input'
export const ScrollArea = 'ScrollArea'
export const StatusDot = 'StatusDot'
export const Textarea = 'Textarea'
export const PALETTE_AREA = 'palette'
export const STATUSBAR_AREAS = { left: 'statusBar.left', right: 'statusBar.right' }
export const PANES_AREA = 'panes'
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'nav'
export const atom = value => ({ value, set (next) { this.value = next }, get () { return this.value } })
export const host = { state: { activeSessionId: atom(null) }, navigate (path) { globalThis.__navigations.push(path) } }
export const pluginSettingsHref = id => '/settings/plugins/' + id
export const queryClient = { invalidateQueries () {} }
export const relativeTime = ms => String(ms)
export const useMutation = () => ({ isPending: false, mutate: v => { globalThis.__mutations.push(v) } })
export const useQuery = () => globalThis.__query || {}
export const useValue = $a => $a.get()
`)
writeFileSync(join(work, 'jsx-runtime.mjs'), `
export const jsx = (type, props) => ({ type, props: props || {} })
export const jsxs = (type, props) => ({ type, props: props || {} })
`)

const rewired = source
  .replace("from '@hermes/plugin-sdk'", "from './sdk.mjs'")
  .replace("from 'react/jsx-runtime'", "from './jsx-runtime.mjs'")
if (rewired === source) throw new Error('import specifiers did not match — probe needs updating')
if (!rewired.includes('export default {')) throw new Error('default export not found — probe needs updating')
const exposed = rewired.replace('export default {', 'const pluginDefault = {')
writeFileSync(join(work, 'plugin.mjs'),
  `${exposed}\nexport { pluginDefault as probePlugin }\nexport { MessageRow as probeMessageRow, WakeBanner as probeWakeBanner, ReactionPicker as probeReactionPicker, reactionPicker as probePickerAtom, notifyIncoming as probeNotifyIncoming, UnreadCount as probeUnreadCount, ChannelButton as probeChannelButton, WorkLine as probeWorkLine, SearchBar as probeSearchBar, SearchResults as probeSearchResults, snippetParts as probeSnippetParts, openHit as probeOpenHit, arriveAt as probeArriveAt, searchQuery as probeSearchQuery, scrollTarget as probeScrollTarget, selection as probeSelection, thread as probeThread, jumpNote as probeJumpNote }\n`)

globalThis.__mutations = []
globalThis.__navigations = []
globalThis.__notified = []
globalThis.__query = null
const { host: sdkHost } = await import(pathToFileURL(join(work, 'sdk.mjs')).href)
const {
  probeMessageRow: MessageRow, probeWakeBanner: WakeBanner, probeReactionPicker: ReactionPicker,
  probePickerAtom: pickerAtom, probeSearchBar: SearchBar, probeSnippetParts: snippetParts,
  probeOpenHit: openHit, probeArriveAt: arriveAt, probeSearchQuery: searchQuery, probeScrollTarget: scrollTarget,
  probeSelection: selection, probeThread: thread, probeJumpNote: jumpNote, probePlugin: plugin,
  probeNotifyIncoming: notifyIncoming, probeUnreadCount: UnreadCount, probeChannelButton: ChannelButton,
  probeWorkLine: WorkLine
} = await import(pathToFileURL(join(work, 'plugin.mjs')).href)

const failures = []
// Register the plugin once, as the host does, so the timers have their context (ctx.setTimeout).
const fakeCtx = {
  items: [], handlers: {}, registerMany: list => fakeCtx.items.push(...list),
  onEvent: (name, fn) => { fakeCtx.handlers[name] = fn }, setInterval () {},
  setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms), onDispose () {},
  os: { notify: input => globalThis.__notified.push(input) }
}
plugin.register(fakeCtx)
const check = (name, ok, detail = '') => {
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${name}${ok || !detail ? '' : ` -> ${detail}`}`)
  if (!ok) failures.push(name)
}

// Every element in a rendered tree, depth-first.
const nodes = root => {
  const out = []
  const walk = n => {
    if (n == null || typeof n !== 'object') return
    if (Array.isArray(n)) return n.forEach(walk)
    if (!n.props) return
    out.push(n)
    // a component element renders its own tree, as React would
    if (typeof n.type === 'function') return walk(n.type(n.props))
    walk(n.props.children)
  }
  walk(root)
  return out
}
const texts = root => nodes(root).flatMap(n => (typeof n.props.children === 'string' ? [n.props.children] : []))
const find = (root, pred) => nodes(root).find(pred)
const findAll = (root, pred) => nodes(root).filter(pred)

const message = (extra = {}) => ({
  id: 'm1', channel_id: 'general', author_name: 'Brooklyn', author_type: 'human', content: 'hello',
  created_at: '2026-11-05T00:00:00Z', reactions: [], reply_count: 0, ...extra
})

// ---- reaction affordance -------------------------------------------------------------
pickerAtom.set(null)
{
  const row = MessageRow({ message: message() })
  const trigger = find(row, n => n.props['data-herd-react-trigger'] !== undefined)
  check('no-reaction message still has an add-reaction trigger', Boolean(trigger))
  check('trigger is a labelled button', trigger && trigger.type === 'button' && trigger.props['aria-label'] === 'Add reaction')
  check('picker closed by default', !find(row, n => n.props.role === 'group'))
  check('trigger reports aria-expanded=false', trigger && trigger.props['aria-expanded'] === 'false')

  trigger.props.onClick()
  check('click opens the picker (atom holds this message id)', pickerAtom.get() === 'm1', String(pickerAtom.get()))

  const opened = ReactionPicker({ message: message(), react: { isPending: false, mutate: v => globalThis.__mutations.push(v) } })
  const group = find(opened, n => n.props.role === 'group')
  const emoji = group ? findAll(group, n => n.props['data-herd-emoji'] !== undefined) : []
  check('picker lists the four reactions', emoji.length === 4, String(emoji.length))
  check('first emoji takes focus on open', emoji[0] && emoji[0].props.autoFocus === true)
  check('trigger reports aria-expanded=true once open',
    find(opened, n => n.props['data-herd-react-trigger'] !== undefined).props['aria-expanded'] === 'true')

  // Clicking an emoji sends exactly that reaction and closes the picker.
  globalThis.__mutations.length = 0
  emoji[2].props.onClick()
  check('picking an emoji calls the mutation with it', globalThis.__mutations[0] === emoji[2].props.children,
    JSON.stringify(globalThis.__mutations))
  check('picking an emoji closes the picker', pickerAtom.get() === null)

  // Esc closes an open picker and does not bubble to the thread panel.
  pickerAtom.set('m1')
  const wrap = ReactionPicker({ message: message(), react: { isPending: false, mutate () {} } })
  let stopped = false
  let refocused = false
  wrap.props.onKeyDown({ key: 'Escape', stopPropagation () { stopped = true },
    currentTarget: { querySelector: () => ({ focus () { refocused = true } }) } })
  check('Esc closes the picker', pickerAtom.get() === null)
  check('Esc stops propagation (thread panel stays open)', stopped)
  check('Esc returns focus to the trigger', refocused)

  // Arrow keys move focus between the emoji (wrapping) and never pick one.
  pickerAtom.set('m1')
  const withPicker = ReactionPicker({ message: message(), react: { isPending: false, mutate () {} } })
  const picks = findAll(withPicker, n => n.props['data-herd-emoji'] !== undefined)
  const focusLog = []
  const items = picks.map(p => ({ label: p.props.children, focus () { focusLog.push(this.label) } }))
  const press = (idx, key) => {
    let prevented = false
    const target = items[idx]
    target.parentElement = { querySelectorAll: () => items }
    picks[idx].props.onKeyDown({ key, preventDefault () { prevented = true }, currentTarget: target })
    return prevented
  }
  const prevented = press(0, 'ArrowRight')
  check('ArrowRight moves focus to the next emoji', focusLog.at(-1) === picks[1].props.children, JSON.stringify(focusLog))
  press(0, 'ArrowLeft')
  check('ArrowLeft from the first emoji wraps to the last', focusLog.at(-1) === picks[3].props.children, JSON.stringify(focusLog))
  check('arrow keys prevent the default scroll', prevented)
  check('arrow keys do not pick a reaction', globalThis.__mutations.length === 1)
  pickerAtom.set(null)
}

// Blurring out of the picker closes it; focus staying inside does not.
{
  pickerAtom.set('m2')
  const p = ReactionPicker({ message: message({ id: 'm2' }), react: { isPending: false, mutate () {} } })
  p.props.onBlur({ currentTarget: { contains: () => false }, relatedTarget: null })
  check('focus leaving the picker closes it', pickerAtom.get() === null)
  pickerAtom.set('m2')
  p.props.onBlur({ currentTarget: { contains: () => true }, relatedTarget: {} })
  check('focus moving inside the picker keeps it open', pickerAtom.get() === 'm2')
  pickerAtom.set(null)
}

// Existing reaction pills keep toggling their own reaction.
{
  globalThis.__mutations.length = 0
  const row = MessageRow({ message: message({ reactions: [{ emoji: '👍', count: 2, mine: true }] }) })
  const pill = find(row, n => n.props.title === 'Remove your reaction')
  check('a reaction pill is still rendered', Boolean(pill))
  pill.props.onClick()
  check('a pill toggles its reaction', globalThis.__mutations[0] === '👍', JSON.stringify(globalThis.__mutations))
}

// ---- wake banner ---------------------------------------------------------------------
const banner = (wake, active = null) => {
  sdkHost.state.activeSessionId.set(active)
  return WakeBanner({ status: { wake } })
}
const base = { enabled: true, target_set: false, target_label: '', blocked_reason: '', blocked_message: '', blocked_at: null, config_line: '' }

{
  const off = banner({ ...base, enabled: false })
  check('wake off says the agent does not answer', texts(off).join(' ').includes('doesn’t answer @mentions'))
  check('wake off offers Settings', Boolean(find(off, n => n.type === 'Button' && n.props.children === 'Settings')))
}
{
  const none = banner({ ...base, blocked_reason: 'no_target' }, null)
  const btn = find(none, n => n.type === 'Button' && n.props.children === 'Answer @mentions here')
  check('no target shows the one-click button', Boolean(btn))
  check('the button is disabled with no active chat', btn && btn.props.disabled === true)
}
{
  globalThis.__mutations.length = 0
  const none = banner({ ...base, blocked_reason: 'no_target' }, 'ses_active_9')
  const btn = find(none, n => n.type === 'Button' && n.props.children === 'Answer @mentions here')
  check('the button is enabled with an active chat', btn && btn.props.disabled === false)
  btn.props.onClick()
  check('the button sends the active session key', globalThis.__mutations[0] === 'ses_active_9',
    JSON.stringify(globalThis.__mutations))
}
{
  const inj = banner({ ...base, blocked_reason: 'injection_not_allowed', blocked_message: 'needs injection',
    config_line: 'allow_gateway_injection: true' })
  const code = find(inj, n => n.type === 'code')
  check('injection banner shows the copyable config line', code && code.props.children === 'allow_gateway_injection: true')
}
{
  const ok = banner({ ...base, target_set: true, target_label: 'this chat' })
  check('answering shows the target in one line',
    texts(ok).join(' ').includes('Your agent answers @mentions in this chat.'), JSON.stringify(texts(ok)))
  check('answering offers a Stop button', Boolean(find(ok, n => n.type === 'Button' && n.props.children === 'Stop')))
}
{
  globalThis.__mutations.length = 0
  const ok = banner({ ...base, target_set: true, target_label: 'this chat' })
  find(ok, n => n.type === 'Button' && n.props.children === 'Stop').props.onClick()
  check('Stop clears the target (empty session key)', globalThis.__mutations[0] === '', JSON.stringify(globalThis.__mutations))
}

// ---- search (Track 1) ----------------------------------------------------------------
const flat = root => nodes(root).filter(n => typeof n.type === 'string')
{
  const parts = snippetParts('a [b] c')
  const mark = parts.find(p => p && p.type === 'mark')
  check('snippet highlights the bracketed match as a mark', mark && mark.props.children === 'b', JSON.stringify(parts))
  check('snippet keeps the text around the match', parts.includes('a ') && parts.includes(' c'))
  const hostile = snippetParts('<img src=x onerror=alert(1)> [<b>]')
  const types = hostile.filter(p => p && typeof p === 'object').map(p => p.type)
  check('snippet never builds markup from message text', types.every(t => t === 'mark'), JSON.stringify(types))
  check('snippet of nothing renders nothing', snippetParts(null).length === 0)
}
{
  searchQuery.set('')
  globalThis.__query = null
  const idle = SearchBar({})
  check('empty search box shows no results list', !find(idle, n => n.props.role === 'list'))
  check('search box is labelled', Boolean(find(idle, n => n.props['aria-label'] === 'Search messages')))

  searchQuery.set('deploy')
  globalThis.__query = { data: { results: [{
    id: 'h1', channel_id: 'general', channel_name: 'general', is_dm: 0, author_name: 'Brooklyn',
    created_at: '2026-11-05T00:00:00Z', snippet: 'the [deploy] failed', thread_parent_id: null
  }] } }
  const hits = SearchBar({})
  const list = find(hits, n => n.props.role === 'list')
  const item = list && findAll(list, n => n.props.role === 'listitem')[0]
  check('a hit lists its channel', item && texts(item).includes('#general'), JSON.stringify(texts(item || {})))
  check('a hit lists its author', item && texts(item).includes('Brooklyn'))
  check('a hit shows its snippet', item && Boolean(find(item, n => n.type === 'mark')))

  globalThis.__query = { data: { results: [] } }
  check('no hits says so, in the query', texts(SearchBar({})).some(t => typeof t === 'string' && t.includes('No messages match')))

  globalThis.__query = { isError: true, data: undefined }
  check('a failed search says so instead of a blank list', texts(SearchBar({})).some(t => typeof t === 'string' && t.includes("couldn't run")))
  globalThis.__query = null
  searchQuery.set('')
}
{
  // Clicking a hit opens its channel (or thread) and clears the search, then waits for its row to scroll to.
  searchQuery.set('x')
  selection.pane.set(null)
  selection.page.set(null)
  thread.page.set(null)
  openHit({ id: 'h2', channel_id: 'general', channel_name: 'general', thread_parent_id: 'root9' })
  check('open hit selects its channel', selection.page.get() === 'general')
  check('open hit opens the thread a reply belongs to', thread.page.get() === 'root9')
  check('open hit clears the search box', searchQuery.get() === '')
  check('open hit arms the scroll for its row', scrollTarget.get() && scrollTarget.get().id === 'h2')
}
{
  // A message row scrolls itself into view when it is the pending hit, and only then.
  const scrolled = []
  const node = { scrollIntoView: opts => scrolled.push(opts), style: {} }
  scrollTarget.set({ id: 'other' })
  arriveAt(node, 'h2')
  check('a different row does not scroll', scrolled.length === 0 && scrollTarget.get().id === 'other')
  scrollTarget.set({ id: 'h2' })
  arriveAt(node, 'h2')
  check('the pending row scrolls into view, once', scrolled.length === 1 && scrollTarget.get() === null)
  arriveAt(node, 'h2')
  check('it does not scroll again on the next render', scrolled.length === 1)
  const row = MessageRow({ message: message({ id: 'rowid' }) })
  check('message rows carry their id for the jump', row.props['data-herd-message-id'] === 'rowid')
  check('message rows get the scroll ref', typeof row.props.ref === 'function')
}
{
  // The palette entry is registered and opens the Herd page with an empty search.
  const items = fakeCtx.items
  const entry = items.find(i => i.area === 'palette')
  check('a ⌘K palette entry is registered', Boolean(entry) && entry.data.id === 'herd.search')
  check('the palette entry is labelled', entry && entry.data.label === 'Search Herd messages')
  searchQuery.set('leftover')
  entry.data.run()
  check('running it opens the Herd page', globalThis.__navigations.at(-1) === '/herd')
  check('running it starts with an empty search', searchQuery.get() === '')
}

// ---- presence, unread and notifications (Track 2) ------------------------------------
const item = (channel, author, preview, extra = {}) => ({
  id: preview, channel_id: channel, channel_name: channel === 'c-dm' ? 'Tyler & Riley' : channel,
  is_dm: channel === 'c-dm', author_name: author, mention: false, preview, ...extra
})
{
  globalThis.__notified.length = 0
  const first = notifyIncoming({ count: 2, items: [item('general', 'riley', 'build is green'), item('general', 'riley', 'and tests')] }, 1000)
  check('one notification per channel burst', first === 1 && globalThis.__notified.length === 1, String(first))
  check('the notification names the channel', globalThis.__notified[0].title === '#general', JSON.stringify(globalThis.__notified[0]))
  check('the body names the author and counts the rest', globalThis.__notified[0].body === 'riley: build is green (+1 more)', globalThis.__notified[0].body)
  check('the notification opens Herd when clicked', globalThis.__notified[0].activate === '/herd')

  check('the same channel within 30s is quiet', notifyIncoming({ count: 1, items: [item('general', 'riley', 'again')] }, 2000) === 0)
  const burst = ['c2', 'c3', 'c4', 'c5', 'c6', 'c7'].map(c => item(c, 'riley', 'hi ' + c))
  check('a burst across channels is capped at four a minute', notifyIncoming({ count: 6, items: burst }, 3000) === 3)
  check('the cap resets after the window', notifyIncoming({ count: 1, items: [item('c9', 'riley', 'later')] }, 70000) === 1)
  globalThis.__notified.length = 0
  const mention = notifyIncoming({ count: 1, items: [item('c10', 'riley', 'you there?', { mention: true })] }, 200000)
  check('a mention says so in the title', mention === 1 && globalThis.__notified[0].title === 'Mentioned in #c10')
  check('a DM names the people, not a hash', notifyIncoming({ count: 1, items: [item('c-dm', 'riley', 'hey')] }, 300000) === 1
    && globalThis.__notified.at(-1).title === 'Tyler & Riley')

  const saved = fakeCtx.os
  fakeCtx.os = undefined
  check('no OS door means no notification and no error', notifyIncoming({ count: 1, items: [item('c11', 'r', 'x')] }, 400000) === 0)
  fakeCtx.os = saved

  globalThis.__notified.length = 0
  fakeCtx.handlers['plugin.herd.incoming.messages']({ payload: { count: 1, items: [item('c12', 'riley', 'routed')] } })
  check('the incoming event reaches the notifier', globalThis.__notified.length === 1 && globalThis.__notified[0].body.includes('routed'))
}
{
  globalThis.__query = { data: [{ unread: 2 }, { unread: 3 }, { unread: 0 }] }
  const bar = UnreadCount({})
  check('the status bar totals unread messages', texts(bar).includes('Herd · 5 unread'), JSON.stringify(texts(bar)))
  globalThis.__query = { data: [{ unread: 0 }] }
  check('the status bar is empty when nothing is unread', UnreadCount({}) === null)
  globalThis.__query = null
}
{
  const unread = ChannelButton({ channel: { id: 'general', name: 'general', unread: 4, message_count: 9 }, label: '#general', selected: false, onSelect () {} })
  const badge = findAll(unread, n => n.props['aria-label'] === '4 unread')
  check('an unread channel shows its count', badge.length === 1 && texts(badge[0]).includes('4'))
  const open = ChannelButton({ channel: { id: 'general', name: 'general', unread: 4, message_count: 9 }, label: '#general', selected: true, onSelect () {} })
  check('the open channel shows no unread count', findAll(open, n => n.props['aria-label'] !== undefined).length === 0)
}
{
  const both = WorkLine({ status: { agent_status: { phrase: 'writing the code', agent: 'tyler' },
    peer_status: [{ name: 'Riley', agent: 'riley', phrase: 'reviewing' }] } })
  const all = texts(both).join(' | ')
  check("a teammate's phrase sits under this agent's", all.includes('writing the code') && all.includes("Riley's agent: reviewing"), all)
  const peerOnly = WorkLine({ status: { agent_status: null, peer_status: [{ name: 'Riley', phrase: 'reviewing' }] } })
  check('a teammate alone still shows their phrase', texts(peerOnly).join(' ').includes("Riley's agent: reviewing"))
  check('no phrases means no work line', WorkLine({ status: { agent_status: null, peer_status: [] } }) === null)
}


console.log(failures.length ? `\n${failures.length} FAILED` : '\nall checks passed')
process.exit(failures.length ? 1 : 0)
