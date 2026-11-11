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
export const KEYBINDS_AREA = 'keybinds'
export const SearchField = 'SearchField'
export const WorkspacePageHeaderControl = 'WorkspacePageHeaderControl'
export const STATUSBAR_AREAS = { left: 'statusBar.left', right: 'statusBar.right' }
export const PANES_AREA = 'panes'
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'nav'
export const atom = value => ({ value, set (next) { this.value = next }, get () { return this.value } })
export const host = { state: { activeSessionId: atom(null) }, navigate (path) { globalThis.__navigations.push(path) }, openWorkspace (id, opts) { globalThis.__workspaces.push({ id, opts }); return () => { globalThis.__closed.push(id) } } }
export const pluginSettingsHref = id => '/settings/plugins/' + id
export const queryClient = { invalidateQueries () {} }
export const relativeTime = ms => String(ms)
export const useMutation = () => ({ isPending: false, data: globalThis.__mintData, mutate: v => { globalThis.__mutations.push(v) }, reset () {} })
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
  `${exposed}\nexport { pluginDefault as probePlugin }\nexport { MessageRow as probeMessageRow, WakeBanner as probeWakeBanner, ReactionPicker as probeReactionPicker, reactionPicker as probePickerAtom, notifyIncoming as probeNotifyIncoming, UnreadCount as probeUnreadCount, ChannelButton as probeChannelButton, WorkLine as probeWorkLine, renderContent as probeRenderContent, Composer as probeComposer, TopicLine as probeTopicLine, NewChannelForm as probeNewChannelForm, insertAtCaret as probeInsertAtCaret, pickedMembers as probePickedMembers, emojiTray as probeEmojiTray, topicEditing as probeTopicEditing, composeRequest as probeComposeRequest, openThreadWorkspace as probeOpenThreadWorkspace, closeThreadWorkspace as probeCloseThreadWorkspace, threadTabs as probeThreadTabs, ThreadWorkspace as probeThreadWorkspace, ThreadPanel as probeThreadPanel, PairingPanel as probePairingPanel, pairingView as probePairingView, pairingResult as probePairingResult, SearchBar as probeSearchBar, SearchResults as probeSearchResults, snippetParts as probeSnippetParts, openHit as probeOpenHit, arriveAt as probeArriveAt, searchQuery as probeSearchQuery, scrollTarget as probeScrollTarget, selection as probeSelection, thread as probeThread, jumpNote as probeJumpNote, renderBody as probeRenderBody, followNewest as probeFollowNewest, followState as probeFollowState, continuesPrevious as probeContinues, messageRows as probeMessageRows, dayLabel as probeDayLabel, mentionCandidates as probeMentionCandidates, buildInvite as probeBuildInvite, inviteLine as probeInviteLine, PeopleList as probePeopleList, renaming as probeRenaming, PlusMenu as probePlusMenu, EditForm as probeEditForm, DeleteConfirm as probeDeleteConfirm, editingMessage as probeEditing, deletingMessage as probeDeleting, RoomPanel as probeRoomPanel, roomInvite as probeRoomInvite, isRoomLink as probeIsRoomLink, typingText as probeTypingText, pingTyping as probePingTyping, channelLabel as probeChannelLabel, NewDmPicker as probeNewDmPicker, AgentSetup as probeAgentSetup, keepPlace as probeKeepPlace, reactionMore as probeReactionMore, MessageView as probeMessageView, ChannelList as probeChannelList, PeerLine as probePeerLine, HISTORY_PAGE as probeHistoryPage }\n`)

globalThis.__mutations = []
globalThis.__navigations = []
globalThis.__notified = []
globalThis.__drafts = {}
globalThis.__workspaces = []
globalThis.__mintData = undefined
globalThis.__closed = []
globalThis.__opened = []
globalThis.__copied = []
globalThis.__api = []
// Node's FormData only takes real form elements; the plugin only needs getAll/get on a form-like object.
globalThis.FormData = class { constructor (f) { this.f = f } getAll (n) { return (this.f.__values && this.f.__values[n]) || [] } get (n) { return this.getAll(n)[0] ?? null } }
globalThis.__query = null
const { host: sdkHost } = await import(pathToFileURL(join(work, 'sdk.mjs')).href)
const {
  probeMessageRow: MessageRow, probeWakeBanner: WakeBanner, probeReactionPicker: ReactionPicker,
  probePickerAtom: pickerAtom, probeSearchBar: SearchBar, probeSnippetParts: snippetParts,
  probeOpenHit: openHit, probeArriveAt: arriveAt, probeSearchQuery: searchQuery, probeScrollTarget: scrollTarget,
  probeSelection: selection, probeThread: thread, probeJumpNote: jumpNote, probePlugin: plugin,
  probeNotifyIncoming: notifyIncoming, probeUnreadCount: UnreadCount, probeChannelButton: ChannelButton,
  probeWorkLine: WorkLine, probeRenderContent, probeComposer, probeTopicLine,
  probeNewChannelForm, probeInsertAtCaret, probePickedMembers,
  probeEmojiTray, probeTopicEditing, probeComposeRequest,
  probeOpenThreadWorkspace, probeCloseThreadWorkspace, probeThreadTabs, probeThreadWorkspace, probeThreadPanel,
  probePairingPanel, probePairingView, probePairingResult,
  probeRenderBody, probeFollowNewest, probeFollowState, probeContinues, probeMessageRows, probeDayLabel,
  probeMentionCandidates, probeBuildInvite, probeInviteLine, probePeopleList, probeRenaming,
  probeEditForm, probeDeleteConfirm, probeEditing, probeDeleting, probeRoomPanel, probeRoomInvite, probeIsRoomLink,
  probeTypingText, probePingTyping, probeChannelLabel, probeNewDmPicker, probeAgentSetup, probeKeepPlace,
  probeReactionMore, probeMessageView, probeChannelList, probePeerLine, probeHistoryPage
} = await import(pathToFileURL(join(work, 'plugin.mjs')).href)

const failures = []
// Register the plugin once, as the host does, so the timers have their context (ctx.setTimeout).
const fakeCtx = {
  items: [], handlers: {}, registerMany: list => fakeCtx.items.push(...list),
  onEvent: (name, fn) => { fakeCtx.handlers[name] = fn }, setInterval () {},
  storage: { get: (k, fb) => (k in globalThis.__drafts ? globalThis.__drafts[k] : fb), set: (k, v) => { globalThis.__drafts[k] = v }, remove: k => { delete globalThis.__drafts[k] } },
  setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms), onDispose () {},
  os: { notify: input => globalThis.__notified.push(input), openExternal: url => { globalThis.__opened.push(url) }, writeClipboard: text => { globalThis.__copied.push(text) } }
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
  check('picker lists the four quick reactions and More', emoji.length === 5 && emoji[4].props.children === 'More', String(emoji.length))
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
  check('ArrowLeft from the first emoji wraps to the last', focusLog.at(-1) === picks.at(-1).props.children, JSON.stringify(focusLog))
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
  check('injection banner shows the config line', code && code.props.children === 'allow_gateway_injection: true')
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
  check('the search box is the SDK search field', Boolean(find(idle, n => n.type === 'SearchField')))

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


// ---- composer, markdown, drafts, topics and keybinds (Track 3) ------------------------
const kinds = root => [...new Set(nodes(root).filter(n => typeof n.type === 'string').map(n => n.type))]
{
  const parts = probeRenderContent('a **bold** and *it* and `code`')
  const strong = nodes(parts).find(n => n.type === 'strong')
  const em = nodes(parts).find(n => n.type === 'em')
  const code = nodes(parts).find(n => n.type === 'code')
  check('bold renders as strong', strong && strong.props.children === 'bold')
  check('italic renders as em', em && em.props.children === 'it')
  check('code renders as code', code && code.props.children === 'code')
  check('snake_case words are left alone', kinds(probeRenderContent('snake_case_name here')).every(t => t !== 'em'))
  check('a sum with stars is left alone', kinds(probeRenderContent('2*3*4 = 24')).every(t => t !== 'em'))
  check('a mention still highlights inside plain text', nodes(probeRenderContent('hi @tyler there')).some(n => n.type === 'span' && n.props.children === '@tyler'))
  check('code keeps its asterisks literal', nodes(probeRenderContent('`**x**`')).find(n => n.type === 'code').props.children === '**x**')
  const hostile = ['<img src=x onerror=alert(1)>', '**<script>alert(1)</script>**', '[click](javascript:alert(1))',
    '<a href="javascript:alert(1)">x</a>', '`<svg onload=alert(1)>`', '*"><iframe src=evil>*', '**a** <b>bold?</b> _x_ &amp;']
  for (const h of hostile) {
    const allowed = ['span', 'strong', 'em', 'code']
    check('hostile markup stays text: ' + h.slice(0, 24), kinds(probeRenderContent(h)).every(t => allowed.includes(t)), JSON.stringify(kinds(probeRenderContent(h))))
  }
  const script = nodes(probeRenderContent('**<script>alert(1)</script>**')).find(n => n.type === 'strong')
  check('a script inside bold is a literal string', script && script.props.children === '<script>alert(1)</script>')
  const linked = probeRenderContent('see https://a.test/x_y_z?q=1). ok')
  const anchor = linked.find(n => n && n.type === 'a')
  check('a web address becomes a link', anchor && anchor.props.href === 'https://a.test/x_y_z?q=1', JSON.stringify(anchor && anchor.props.href))
  check('the sentence around it stays text', linked[0] === 'see ' && linked.at(-1) === '). ok', JSON.stringify(linked.map(n => (typeof n === 'string' ? n : n.type))))
  globalThis.__opened = []
  let stopped = 0
  anchor.props.onClick({ preventDefault () { stopped += 1 }, stopPropagation () {} })
  check('a click opens it in the system browser, never in the app', stopped === 1 && globalThis.__opened[0] === 'https://a.test/x_y_z?q=1', JSON.stringify(globalThis.__opened))
  check('only http(s) is ever a link', ['javascript:alert(1)', 'file:///etc/passwd', 'data:text/html,x', 'ftp://a.test/x'].every(t => kinds(probeRenderContent(t)).every(k => k !== 'a')))
  check('an address inside code stays code', kinds(probeRenderContent('`https://a.test`')).every(k => k !== 'a'))
  check('a mention beside a link still highlights', probeRenderContent('@riley https://a.test').some(n => n && n.type === 'span') )
}
{
  // Drafts: saved as you type, restored into the composer, cleared when empty.
  globalThis.__drafts = {}
  probeComposeRequest.set(0)
  const form = probeComposer({ channel: { id: 'general' }, compact: false, placeholderName: '#general' })
  const field = nodes(form).find(n => n.type === 'Textarea' || (n.props && n.props.name === 'content'))
  check('a composer starts from the saved draft', field && field.props.defaultValue === '')
  globalThis.__drafts['draft:channel:general'] = 'half a thought'
  const again = probeComposer({ channel: { id: 'general' }, compact: false, placeholderName: '#general' })
  const restored = nodes(again).find(n => n.props && n.props.name === 'content')
  check('a draft comes back into the composer', restored && restored.props.defaultValue === 'half a thought')
  restored.props.onChange({ currentTarget: { value: 'typed more', selectionStart: 0, selectionEnd: 0 } })
  check('typing saves the draft', globalThis.__drafts['draft:channel:general'] === 'typed more')
  restored.props.onChange({ currentTarget: { value: '   ', selectionStart: 0, selectionEnd: 0 } })
  check('a blank field clears the saved draft', !('draft:channel:general' in globalThis.__drafts))
  globalThis.__drafts['draft:channel:general'] = 'only for general'
  const other = nodes(probeComposer({ channel: { id: 'ops' }, compact: false, placeholderName: '#ops' })).find(n => n.props && n.props.name === 'content')
  check('drafts are per channel', other.props.defaultValue === '', JSON.stringify(other.props.defaultValue))
}
{
  // Caret insertion keeps the rest of the text and leaves the caret after the emoji.
  const field = { value: 'ab', selectionStart: 1, selectionEnd: 1, focus () { this.focused = true } }
  probeInsertAtCaret(field, '🎉')
  check('an emoji is inserted at the caret', field.value === 'a🎉b', field.value)
  check('the caret moves past the emoji', field.selectionStart === 1 + '🎉'.length)
  check('focus returns to the field', field.focused === true)
}
{
  // The emoji tray opens from the composer and inserts through the form's own field.
  probeEmojiTray.pane.set(true)
  const tray = nodes(probeComposer({ channel: { id: 'general' }, compact: true, placeholderName: '#general' }))
  const btn = tray.find(n => n.props['aria-label'] === 'Insert 🎉')
  check('the tray offers emoji when open', Boolean(btn))
  probeEmojiTray.pane.set(false)
  check('a closed tray is not rendered', !nodes(probeComposer({ channel: { id: 'general' }, compact: true, placeholderName: '#general' })).find(n => n.props['aria-label'] === 'Insert 🎉'))
  probeEmojiTray.pane.set(true)
  const inserting = nodes(probeComposer({ channel: { id: 'general' }, compact: true, placeholderName: '#general' })).find(n => n.props['aria-label'] === 'Insert 🎉')
  const fieldShim = { value: 'hi', selectionStart: 2, selectionEnd: 2, focus () {} }
  const fakeForm = { elements: { content: fieldShim } }
  inserting.props.onClick({ currentTarget: { form: fakeForm } })
  check('clicking an emoji puts it in the message', fieldShim.value === 'hi🎉')
  check('and closes the tray', probeEmojiTray.pane.get() === false)
  check('the emoji is saved as the draft', globalThis.__drafts['draft:channel:general'] === 'hi🎉')
}
{
  // The new-message keybind focuses the composer that mounts next, and only then.
  probeComposeRequest.set(Date.now())
  const fresh = nodes(probeComposer({ channel: { id: 'general' }, compact: false, placeholderName: '#general' })).find(n => n.props && n.props.name === 'content')
  check('a new-message request focuses the composer', fresh.props.autoFocus === true)
  probeComposeRequest.set(Date.now() - 60000)
  const stale = nodes(probeComposer({ channel: { id: 'general' }, compact: false, placeholderName: '#general' })).find(n => n.props && n.props.name === 'content')
  check('an old request does not steal focus later', stale.props.autoFocus === false)
  probeComposeRequest.set(0)
}
{
  const keybinds = fakeCtx.items.filter(i => i.area === 'keybinds')
  const open = keybinds.find(i => i.data.id === 'herd.open')
  const fresh = keybinds.find(i => i.data.id === 'herd.newMessage')
  check('open-Herd keybind is registered', Boolean(open) && open.data.defaults[0] === 'mod+alt+h')
  check('new-message keybind is registered', Boolean(fresh) && fresh.data.defaults[0] === 'mod+alt+n')
  globalThis.__navigations.length = 0
  fresh.data.run()
  check('the new-message keybind opens Herd', globalThis.__navigations.at(-1) === '/herd')
  check('and asks for the composer', probeComposeRequest.get() > 0)
  probeComposeRequest.set(0)
  open.data.run()
  check('the open keybind opens Herd', globalThis.__navigations.at(-1) === '/herd')
}
{
  // Topic: viewable, editable for a public channel, never shown for a DM.
  probeTopicEditing.page.set(null)
  check('a DM has no topic line', probeTopicLine({ channel: { id: 'dm:a+b', is_dm: true, topic: '' }, $editing: probeTopicEditing.page }) === null)
  const shown = probeTopicLine({ channel: { id: 'general', is_dm: false, topic: 'ship it' }, $editing: probeTopicEditing.page })
  check('the topic is shown with an edit control', texts(shown).includes('ship it') && Boolean(find(shown, n => n.type === 'button' && n.props.children === 'Edit topic')))
  const empty = probeTopicLine({ channel: { id: 'ops', is_dm: false, topic: '' }, $editing: probeTopicEditing.page })
  check('an empty topic offers to add one', Boolean(find(empty, n => n.type === 'button' && n.props.children === 'Add a topic')))
  find(shown, n => n.type === 'button' && n.props.children === 'Edit topic').props.onClick()
  check('editing opens the topic field', probeTopicEditing.page.get() === 'general')
  const editing = probeTopicLine({ channel: { id: 'general', is_dm: false, topic: 'ship it' }, $editing: probeTopicEditing.page })
  const field = find(editing, n => n.type === 'Input' && n.props.name === 'topic')
  check('the topic field is limited to 200 characters', field && field.props.maxLength === 200)
  probeTopicEditing.page.set(null)
}
{
  // The new-channel form: teammates to pick (not you), and the honest answer about private channels.
  globalThis.__query = { data: [{ id: 'me', display_name: 'Tyler', is_self: true }, { id: 'riley', display_name: 'Riley', is_self: false }] }
  const form = probeNewChannelForm({ onDone () {} })
  const box = find(form, n => n.type === 'input' && n.props.type === 'checkbox')
  check('the member picker offers teammates, not you', box && box.props.value === 'riley')
  check('the form says ticking people makes it private', texts(form).join(' ').includes('Make it private'))
  globalThis.__query = null
  const fakeForm = { __values: { name: ['ops'], member: ['riley'] } }
  globalThis.__mutations.length = 0
  form.props.onSubmit({ preventDefault () {}, currentTarget: fakeForm })
  check('creating sends the chosen members', JSON.stringify(globalThis.__mutations[0]) === JSON.stringify({ name: 'ops', members: ['riley'] }),
    JSON.stringify(globalThis.__mutations))
  globalThis.__mutations.length = 0
  form.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { name: ['everyone'] } } })
  check('creating with nobody ticked sends no member list', JSON.stringify(globalThis.__mutations[0]) === JSON.stringify({ name: 'everyone', members: [] }))
  check('picked members are capped at four', probePickedMembers({ __values: { member: ['a', 'b', 'c', 'd', 'e'] } }).length === 4)
}

// ---- threads as a workspace page (Track 4) --------------------------------------------
{
  const chan = { id: 'general', name: 'general', is_dm: false }
  globalThis.__workspaces.length = 0
  globalThis.__closed.length = 0
  probeThreadTabs.clear()
  check('a thread opens as a workspace tab', probeOpenThreadWorkspace(chan, 'root1') === true)
  const tab = globalThis.__workspaces.at(-1)
  check('the tab is keyed by the thread', tab && tab.id === 'herd-thread:root1')
  check('the tab is titled with its channel', tab && tab.opts.title === 'Thread · #general')
  check('the tab renders the thread workspace', tab && tab.opts.render().type === probeThreadWorkspace)
  check('one open tab per thread', probeThreadTabs.size === 1)

  probeOpenThreadWorkspace(chan, 'root1')
  check('opening it again re-fronts the same tab', globalThis.__workspaces.at(-1).id === 'herd-thread:root1' && probeThreadTabs.size === 1)

  probeCloseThreadWorkspace('root1')
  check('closing the thread closes its tab', globalThis.__closed.includes('herd-thread:root1'))
  check('and forgets it', probeThreadTabs.size === 0)
  probeCloseThreadWorkspace('root1')
  check('closing twice is harmless', globalThis.__closed.filter(id => id === 'herd-thread:root1').length === 1)

  // rapid open and close: no leaked tabs, every close lands
  globalThis.__closed.length = 0
  for (let i = 0; i < 20; i++) {
    probeOpenThreadWorkspace(chan, 'root2')
    probeCloseThreadWorkspace('root2')
  }
  check('rapid open and close leaves no tab behind', probeThreadTabs.size === 0)
  check('and every close landed once', globalThis.__closed.length === 20, String(globalThis.__closed.length))
  for (let i = 0; i < 5; i++) probeOpenThreadWorkspace(chan, 'root3')
  check('repeated opens never stack tabs', probeThreadTabs.size === 1)
  probeCloseThreadWorkspace('root3')

  // Esc closes the tab, unless a composer already used the key
  probeOpenThreadWorkspace(chan, 'root4')
  const ws = probeThreadWorkspace({ channel: chan, rootId: 'root4' })
  ws.props.onKeyDown({ key: 'Escape', defaultPrevented: true, preventDefault () {} })
  check('Esc a composer handled leaves the tab open', probeThreadTabs.has('root4'))
  ws.props.onKeyDown({ key: 'Escape', defaultPrevented: false, preventDefault () {} })
  check('Esc closes the thread tab', !probeThreadTabs.has('root4') && globalThis.__closed.includes('herd-thread:root4'))
  probeThreadTabs.clear()

  // The route's thread panel keeps its own Esc, and offers the action only when the host can open tabs.
  thread.page.set('root5')
  const panel = probeThreadPanel({ channel: chan, rootId: 'root5', selfId: 'me', $thread: thread.page })
  panel.props.onKeyDown({ key: 'Escape', defaultPrevented: false, preventDefault () {} })
  check('the thread panel still closes on Esc', thread.page.get() === null)
  const withAction = nodes(probeThreadPanel({ channel: chan, rootId: 'root5', selfId: 'me', $thread: thread.page }))
  const openBtn = withAction.find(n => n.type === 'Button' && n.props.children === 'Open as page')
  check('the panel offers Open as page when tabs are available', Boolean(openBtn))
  globalThis.__workspaces.length = 0
  openBtn.props.onClick()
  check('Open as page docks the thread', globalThis.__workspaces.at(-1) && globalThis.__workspaces.at(-1).id === 'herd-thread:root5')
  probeCloseThreadWorkspace('root5')

  const savedOpen = sdkHost.openWorkspace
  sdkHost.openWorkspace = undefined
  check('without tabs the open action is absent', !nodes(probeThreadPanel({ channel: chan, rootId: 'root5', selfId: 'me', $thread: thread.page }))
    .find(n => n.type === 'Button' && n.props.children === 'Open as page'))
  check('and opening a tab quietly does nothing', probeOpenThreadWorkspace(chan, 'root6') === false && probeThreadTabs.size === 0)
  sdkHost.openWorkspace = savedOpen
  thread.page.set(null)
}


// ---- pairing (Track 5) ---------------------------------------------------------------
{
  probePairingView.set(null)
  probePairingResult.set(null)
  globalThis.__mintData = undefined
  const start = nodes(probePairingPanel({}))
  check('pairing offers to show a code', Boolean(start.find(n => n.type === 'Button' && n.props.children === 'Show a pairing code')))
  check('pairing offers to join with an invite', Boolean(start.find(n => n.type === 'Button' && n.props.children === 'Join with an invite')))
  start.find(n => n.type === 'Button' && n.props.children === 'Join with an invite').props.onClick()
  check('entering opens the form', probePairingView.get() === 'enter')
  const form = probePairingPanel({})
  const fields = nodes(form).filter(n => n.type === 'Input').map(n => n.props.name)
  check('the form asks for the address and the code', fields.includes('url') && fields.includes('code'), JSON.stringify(fields))
  globalThis.__mutations.length = 0
  form.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { url: ['https://brooklyn-mac.tailnet.ts.net:8642'], code: ['ABCDE-FGHJK'] } } })
  check('pairing sends the address and the code', JSON.stringify(globalThis.__mutations[0]) === JSON.stringify({ url: 'https://brooklyn-mac.tailnet.ts.net:8642', code: 'ABCDE-FGHJK' }),
    JSON.stringify(globalThis.__mutations))

  probePairingView.set('show')
  globalThis.__mintData = { code: 'ABCDE-FGHJK', expires_in_s: 600 }
  const shown = nodes(probePairingPanel({}))
  check('a minted code is shown', shown.some(n => n.type === 'code' && n.props.children === 'ABCDE-FGHJK'))
  check('the code says it is single use and short-lived', texts(probePairingPanel({})).join(' ').includes('one use'))
  globalThis.__mintData = undefined

  probePairingView.set(null)
  probePairingResult.set({ name: 'brooklyn', url: 'https://brooklyn-mac.tailnet.ts.net:8642', herd_secret: ['SECRET', 'VALUE', '0123456789'].join('-') })
  const done = probePairingPanel({})
  check('a finished pairing names the teammate', texts(done).join(' ').includes('Paired with brooklyn'))
  check('the key is shown once, in a code element', nodes(done).some(n => n.type === 'code' && n.props.children === 'SECRET-VALUE-0123456789'))
  check('the key is never written to plugin storage', !Object.values(globalThis.__drafts).some(v => String(v).includes('SECRET-VALUE')))
  find(done, n => n.type === 'Button' && n.props.children === 'Hide key').props.onClick()
  check('hiding the key clears it', probePairingResult.get() === null)
  check('and it is gone from the pane', !nodes(probePairingPanel({})).some(n => n.type === 'code'))
}

// ---- agent answers read as written: code blocks, lists, quotes, headings ----------------
{
  check('a plain message renders exactly as before', JSON.stringify(probeRenderBody('hello **there**')) === JSON.stringify(probeRenderContent('hello **there**')))
  const body = probeRenderBody('Here you go:\n```js\nconst a = 1\n<b>x</b>\n```\n- first\n- **second**\n1. one\n> quoted\n# Title\nbye')
  const all = nodes(body)
  const code = all.find(n => n.type === 'div' && n.props.style && n.props.style.whiteSpace === 'pre')
  check('a fenced block is one code box with its text untouched', Boolean(code) && code.props.children === 'const a = 1\n<b>x</b>', JSON.stringify(code && code.props.children))
  check('markup inside a code block stays text', !all.some(n => n.type === 'b'))
  check('bullets render as list rows', all.filter(n => n.type === 'span' && n.props.children === '•').length === 2)
  check('inline markup still works inside a list row', all.some(n => n.type === 'strong' && n.props.children === 'second'))
  check('a numbered row keeps its number', all.some(n => n.type === 'span' && n.props.children === '1.'))
  check('a quote has a rule down its side', all.some(n => n.type === 'div' && n.props.style && String(n.props.style.borderLeft || '').includes('2px')))
  check('a heading is bold', all.some(n => n.type === 'div' && n.props.style && n.props.style.fontWeight === 600))
  const open = nodes(probeRenderBody('```\nstill code'))
  check('an unclosed fence still reads as code', open.some(n => n.type === 'div' && n.props.children === 'still code'))
  check('snake_case and a lone dash are not lists', JSON.stringify(probeRenderBody('a - b and snake_case')) === JSON.stringify(probeRenderContent('a - b and snake_case')))
}

// ---- the list follows the newest message ------------------------------------------------
{
  const box = { scrollHeight: 1000, scrollTop: 0, clientHeight: 300, parentElement: null }
  const mk = () => { const n = { parentElement: box, scrolled: 0, scrollIntoView () { n.scrolled += 1 } }; return n }
  probeFollowState.last.clear()
  const first = mk()
  probeFollowNewest(first, 'channel:x', 'm1', false)
  check('a list opens at its newest message', first.scrolled === 1)
  probeFollowNewest(first, 'channel:x', 'm1', false)
  check('a re-render with nothing new leaves the scroll alone', first.scrolled === 1)
  probeFollowNewest(first, 'channel:x', 'm2', false)
  check('reading history, a teammate\'s new message does not yank the view', first.scrolled === 1)
  probeFollowNewest(first, 'channel:x', 'm3', true)
  check('your own message always comes into view', first.scrolled === 2)
  box.scrollTop = 650
  probeFollowNewest(first, 'channel:x', 'm4', false)
  check('near the bottom, a new message is followed', first.scrolled === 3)
  const again = mk()
  probeFollowNewest(again, 'channel:x', 'm4', false)
  check('coming back to a channel opens at the newest again', again.scrolled === 1)
  scrollTarget.set({ id: 'hit' })
  const jumping = mk()
  probeFollowNewest(jumping, 'channel:y', 'm9', true)
  check('a search jump keeps the scroll', jumping.scrolled === 0)
  scrollTarget.set(null)
  check('no rows, no scroll', probeFollowNewest(mk(), 'channel:z', null, false) === false)
}

// ---- grouping and day dividers ----------------------------------------------------------
{
  const a = message({ id: 'a', gateway_id: 'g1', created_at: '2026-11-05T10:00:00Z' })
  const b = message({ id: 'b', gateway_id: 'g1', created_at: '2026-11-05T10:02:00Z' })
  const late = message({ id: 'c', gateway_id: 'g1', created_at: '2026-11-05T10:30:00Z' })
  const other = message({ id: 'd', gateway_id: 'g2', author_name: 'Ash', created_at: '2026-11-05T10:30:30Z' })
  const agentRow = message({ id: 'e', gateway_id: 'g2', author_name: 'Ash', author_type: 'agent', created_at: '2026-11-05T10:30:40Z' })
  check('a quick follow-up joins the message above', probeContinues(a, b) === true)
  check('a long gap starts a new header', probeContinues(b, late) === false)
  check('another person starts a new header', probeContinues(late, other) === false)
  check('an agent never hides under a person\'s header', probeContinues(other, agentRow) === false)
  const rows = probeMessageRows([a, b, late], { onOpenThread () {} })
  check('one day divider for one day', rows.filter(r => r.type.name === 'DayDivider').length === 1)
  const grouped = MessageRow(rows[2].props)
  check('a grouped row has no author header', !texts(grouped).includes('Brooklyn'))
  check('a grouped row still offers Reply on hover', nodes(grouped).some(n => n.type === 'button' && n.props['aria-label'] === 'Reply in thread'))
  const headed = MessageRow(rows[1].props)
  check('the first row of a group names its author', texts(headed).includes('Brooklyn'))
  const now = new Date(2026, 10, 10, 12)
  check('today reads Today', probeDayLabel(new Date(2026, 10, 10, 9).toISOString(), now) === 'Today')
  check('yesterday reads Yesterday', probeDayLabel(new Date(2026, 10, 9, 23).toISOString(), now) === 'Yesterday')
}

// ---- your own agent is in the mention menu ----------------------------------------------
{
  const list = probeMentionCandidates([{ id: 'me', display_name: 'Tyler', is_self: true }, { id: 'b', display_name: 'Brooklyn', is_self: false }], '')
  check('your own agent can be tagged', list.some(c => c.handle === 'tyler-hermes' && c.label === 'Your Hermes'))
  check('you are not offered yourself', !list.some(c => c.handle === 'tyler'))
  check('teammates and their agents are still offered', list.some(c => c.handle === 'brooklyn') && list.some(c => c.handle === 'brooklyn-hermes'))
  const odd = probeMentionCandidates([{ id: 'me', display_name: '田中', is_self: true }], '')
  check('a name with no latin letters falls back to @hermes', odd.length === 1 && odd[0].handle === 'hermes')
}

// ---- one-line invite --------------------------------------------------------------------
{
  check('an invite is address#code', probeBuildInvite('https://my-mac.ts.net:8642/', 'ABCDE-FGHJK') === 'https://my-mac.ts.net:8642#ABCDE-FGHJK')
  check('no address, no invite', probeBuildInvite('  ', 'ABCDE-FGHJK') === '')
  probePairingResult.set(null)
  probePairingView.set('show')
  probeInviteLine.set('')
  globalThis.__mintData = { code: 'ABCDE-FGHJK', expires_in_s: 600 }
  const shown = probePairingPanel({})
  const form = find(shown, n => n.type === 'form')
  form.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { address: ['https://my-mac.ts.net:8642'] } } })
  check('making an invite remembers the address', globalThis.__drafts.gatewayAddress === 'https://my-mac.ts.net:8642')
  check('the invite is shown as one line', nodes(probePairingPanel({})).some(n => n.type === 'code' && n.props.children === 'https://my-mac.ts.net:8642#ABCDE-FGHJK'))
  globalThis.__mintData = undefined
  probePairingView.set('enter')
  globalThis.__mutations.length = 0
  const enter = probePairingPanel({})
  enter.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { url: ['https://my-mac.ts.net:8642#ABCDE-FGHJK'], code: [] } } })
  check('a pasted invite needs no separate code', globalThis.__mutations.length === 1 && globalThis.__mutations[0].url === 'https://my-mac.ts.net:8642#ABCDE-FGHJK')
  globalThis.__mutations.length = 0
  enter.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { url: ['https://my-mac.ts.net:8642'], code: [] } } })
  check('an address alone is not sent', globalThis.__mutations.length === 0)
  probePairingView.set(null)
  probeInviteLine.set('')
}

// ---- people list ------------------------------------------------------------------------
{
  globalThis.__query = { data: [
    { id: 'me', display_name: 'Tyler', is_self: true, online: true },
    { id: 'b', display_name: 'Brooklyn', is_self: false, online: true },
    { id: 'c', display_name: 'Ash', is_self: false, online: false }
  ] }
  probeRenaming.set(false)
  const picked = []
  const status = { agent_status: null, peer_status: [{ gateway_id: 'b', phrase: 'writing the code' }] }
  const list = probePeopleList({ status, onSelect: id => picked.push(id) })
  const dots = findAll(list, n => n.type === 'StatusDot').map(n => n.props.tone)
  check('online teammates get a green dot, away ones a muted one', JSON.stringify(dots) === JSON.stringify(['good', 'good', 'muted']), JSON.stringify(dots))
  check('a working agent shows beside its person', texts(list).includes('agent writing the code'))
  globalThis.__mutations.length = 0
  findAll(list, n => n.type === 'button')[1].props.onClick()
  check('clicking a teammate opens the DM', JSON.stringify(globalThis.__mutations[0]) === JSON.stringify({ id: 'b' }))
  findAll(list, n => n.type === 'button')[0].props.onClick()
  check('clicking yourself starts a rename', probeRenaming.get() === true)
  const editing = probePeopleList({ status, onSelect () {} })
  globalThis.__mutations.length = 0
  find(editing, n => n.type === 'form').props.onSubmit({ preventDefault () {}, currentTarget: { __values: { display_name: ['Ty'] } } })
  check('saving sends the new name', globalThis.__mutations[0] === 'Ty')
  probeRenaming.set(false)
  globalThis.__query = null
  check('no people, no section', probePeopleList({ status: null, onSelect () {} }) === null)
}

// ---- edit and delete ----------------------------------------------------------------------
{
  probeEditing.set(null)
  probeDeleting.set(null)
  pickerAtom.set(null)
  const mine = message({ id: 'mine1', gateway_id: 'me', content: 'frist' })
  const theirs = message({ id: 'theirs1', gateway_id: 'b' })
  const labels = row => findAll(row, n => n.type === 'button').map(n => n.props.children)
  check('your own message offers Edit and Delete', ['Edit', 'Delete'].every(l => labels(MessageRow({ message: mine, selfId: 'me' })).includes(l)))
  check('a teammate\'s message offers neither', !labels(MessageRow({ message: theirs, selfId: 'me' })).some(l => l === 'Edit' || l === 'Delete'))
  find(MessageRow({ message: mine, selfId: 'me' }), n => n.type === 'button' && n.props.children === 'Edit').props.onClick()
  check('Edit opens the editor on that message', probeEditing.get() === 'mine1')
  const editingRow = MessageRow({ message: mine, selfId: 'me' })
  const field = find(editingRow, n => n.type === 'Textarea')
  check('the editor starts with the message text', field && field.props.defaultValue === 'frist')
  const form = find(editingRow, n => n.type === 'form')
  globalThis.__mutations.length = 0
  form.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { edited: ['first'] } } })
  check('saving sends the new text', globalThis.__mutations[0] === 'first', JSON.stringify(globalThis.__mutations))
  globalThis.__mutations.length = 0
  form.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { edited: ['   '] } } })
  check('an empty edit is not sent', globalThis.__mutations.length === 0)
  form.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { edited: ['frist'] } } })
  check('an unchanged edit just closes the editor', globalThis.__mutations.length === 0 && probeEditing.get() === null)
  probeEditing.set('mine1')
  let escStopped = 0
  find(MessageRow({ message: mine, selfId: 'me' }), n => n.type === 'Textarea').props.onKeyDown({ key: 'Escape', preventDefault () {}, stopPropagation () { escStopped += 1 } })
  check('Esc cancels the edit without closing the thread around it', probeEditing.get() === null && escStopped === 1)

  find(MessageRow({ message: mine, selfId: 'me' }), n => n.type === 'button' && n.props.children === 'Delete').props.onClick()
  check('Delete asks first', probeDeleting.get() === 'mine1' && globalThis.__mutations.length === 0)
  const asking = MessageRow({ message: mine, selfId: 'me' })
  check('the question is in the row', texts(asking).includes('Delete this message for everyone?'))
  find(asking, n => n.type === 'Button' && n.props.children === 'Cancel').props.onClick()
  check('Cancel keeps the message', probeDeleting.get() === null)
  probeDeleting.set('mine1')
  find(MessageRow({ message: mine, selfId: 'me' }), n => n.type === 'Button' && n.props.children === 'Delete').props.onClick()
  check('confirming deletes it', globalThis.__mutations.length === 1)
  probeDeleting.set(null)

  const edited = MessageRow({ message: message({ edited_at: '2026-11-05T00:05:00Z' }), selfId: 'me' })
  check('an edited message says so', texts(edited).includes('(edited)'))
  check('a grouped edited message says so too', texts(MessageRow({ message: message({ edited_at: '2026-11-05T00:05:00Z' }), grouped: true })).includes('(edited)'))
  const gone = MessageRow({ message: message({ deleted: 1, content: '', reply_count: 2, gateway_id: 'me' }), selfId: 'me', onOpenThread () {} })
  check('a deleted message with replies keeps its place', texts(gone).includes('This message was deleted.'))
  check('and can no longer be reacted to or edited', !find(gone, n => n.props['data-herd-react-trigger'] !== undefined) && !labels(gone).includes('Edit'))
}

// ---- more reactions -------------------------------------------------------------------------
{
  pickerAtom.set('m1')
  probeReactionMore.set(false)
  const sent = []
  const react = { isPending: false, mutate: v => sent.push(v) }
  const quick = ReactionPicker({ message: message(), react })
  find(quick, n => n.props.children === 'More').props.onClick()
  check('More opens the full tray', probeReactionMore.get() === true)
  const tray = findAll(ReactionPicker({ message: message(), react }), n => n.props['data-herd-emoji'] !== undefined)
  check('the tray offers many emoji', tray.length >= 20, String(tray.length))
  tray.find(n => n.props.children === '🚀').props.onClick()
  check('picking one reacts with it and closes the tray', sent[0] === '🚀' && pickerAtom.get() === null && probeReactionMore.get() === false)
}

// ---- load older, typing, labels ------------------------------------------------------------
{
  const many = Array.from({ length: probeHistoryPage + 1 }, (_, i) => message({ id: 'h' + i, created_at: new Date(Date.UTC(2026, 10, 5, 0, 0, i)).toISOString() }))
  const channel = { id: 'general', name: 'general', is_dm: false, members: [] }
  const view = args => probeMessageView({ channel, selfId: 'me', status: args.status || {}, $thread: thread.page, $selected: selection.page, compact: false })
  globalThis.__query = { data: many }
  const full = view({})
  const older = find(full, n => n.type === 'Button' && n.props.children === 'Load older messages')
  check('a channel with more history offers Load older messages', Boolean(older))
  check('the extra row that proved it is not shown', !find(full, n => n.props['data-herd-message-id'] === 'h0') && Boolean(find(full, n => n.props['data-herd-message-id'] === 'h1')))
  older.props.onClick()
  globalThis.__query = { data: many.concat([message({ id: 'older-a', created_at: '2026-11-04T00:00:00Z' })]).sort((a, b) => a.created_at.localeCompare(b.created_at)) }
  const grown = view({})
  check('after loading, the older rows are there and the button is gone', Boolean(find(grown, n => n.props['data-herd-message-id'] === 'older-a')) && !find(grown, n => n.type === 'Button' && n.props.children === 'Load older messages'))
  let scrolled = null
  check('the reader stays on the message they were at', probeKeepPlace({ scrollIntoView: o => { scrolled = o } }, 'h1') === true && scrolled.block === 'start')
  check('and only once', probeKeepPlace({ scrollIntoView () {} }, 'h1') === false)
  globalThis.__query = { data: many.slice(0, 5) }
  check('a short channel has no Load older button', !find(view({}), n => n.type === 'Button' && n.props.children === 'Load older messages'))

  const typing = [{ gateway_id: 'b', name: 'Riley', channel_id: 'general' }, { gateway_id: 'c', name: 'Sam', channel_id: 'general' }, { gateway_id: 'd', name: 'Ash', channel_id: 'ops' }]
  check('one person typing', probeTypingText({ typing: typing.slice(0, 1) }, 'general') === 'Riley is typing…')
  check('two people typing', probeTypingText({ typing }, 'general') === 'Riley and Sam are typing…')
  check('typing elsewhere is not shown here', probeTypingText({ typing }, 'random') === '')
  check('the line appears above the composer', texts(view({ status: { typing } })).includes('Riley and Sam are typing…'))
  globalThis.__query = null

  check('typing is announced once per burst', probePingTyping('burst', 'h') === true && probePingTyping('burst', 'he') === false)
  check('an empty box announces nothing', probePingTyping('ops', '   ') === false)
  check('switching channel announces again', probePingTyping('ops', 'x') === true)

  const members = [{ id: 'me', name: 'Tyler' }, { id: 'b', name: 'Riley' }, { id: 'c', name: 'Sam' }]
  check('a group is named after the others in it', probeChannelLabel({ id: 'gdm-1', name: 'gdm-1', is_group: true, members }, 'me') === 'Riley, Sam')
  check('a private channel shows a lock', probeChannelLabel({ id: 'founders', name: 'founders', is_private: true, members }, 'me') === '🔒 founders')
  check('an open channel shows a hash', probeChannelLabel({ id: 'general', name: 'general', members: [] }, 'me') === '# general')

  globalThis.__query = { data: [{ id: 'me', display_name: 'Tyler', is_self: true }, { id: 'b', display_name: 'Riley', is_self: false }, { id: 'c', display_name: 'Sam', is_self: false }] }
  const picker = probeNewDmPicker({ onDone () {} })
  globalThis.__mutations.length = 0
  picker.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { member: ['b', 'c'] } } })
  check('ticking two people opens a group', JSON.stringify(globalThis.__mutations[0]) === JSON.stringify({ ids: ['b', 'c'] }))
  picker.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { member: [] } } })
  check('ticking nobody opens nothing', globalThis.__mutations.length === 1)
  const everyone = probeMentionCandidates(globalThis.__query.data, 'chan')
  check('@channel is offered', everyone.length === 1 && everyone[0].handle === 'channel')
  globalThis.__query = null
}

// ---- team room -------------------------------------------------------------------------------
{
  const link = 'https://herd-relay.example.workers.dev/r/0123456789abcdef0123#' + 'k'.repeat(43)
  check('a room link is recognised', probeIsRoomLink(link) && probeIsRoomLink('  ' + link + ' '))
  check('a pairing invite is not a room link', !probeIsRoomLink('https://riley.ts.net:8642#ABCDE-FGHJK') && !probeIsRoomLink('hello'))

  probePairingResult.set(null)
  probePairingView.set(null)
  const start = nodes(probePairingPanel({ status: { room: { joined: false } } }))
  check('first run leads with starting a team room', start.find(n => n.type === 'Button').props.children === 'Start a team room')
  start.find(n => n.type === 'Button' && n.props.children === 'Start a team room').props.onClick()
  check('which opens the room form', probePairingView.get() === 'room')
  const form = probePairingPanel({ status: { room: { joined: false, relay_default: 'https://relay.default.example' } } })
  const roomForm = find(form, n => n.type === 'form')
  check('the form offers the default relay', find(form, n => n.type === 'Input').props.defaultValue === 'https://relay.default.example')
  globalThis.__mutations.length = 0
  roomForm.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { relay: ['https://relay.mine.example'] } } })
  check('starting a room sends the relay address', globalThis.__mutations[0] === 'https://relay.mine.example')

  probePairingView.set('enter')
  const enter = probePairingPanel({ status: {} })
  globalThis.__mutations.length = 0
  enter.props.onSubmit({ preventDefault () {}, currentTarget: { __values: { url: [link], code: [] } } })
  check('pasting a room link joins the room in one step', globalThis.__mutations.length === 1 && globalThis.__mutations[0] === link)

  probePairingView.set('room-invite')
  probeRoomInvite.set(link)
  globalThis.__copied.length = 0
  const invite = probePairingPanel({ status: { room: { joined: true, source: 'joined', can_invite: true } } })
  check('the invite panel shows the link', nodes(invite).some(n => n.type === 'code' && n.props.children === link))
  find(invite, n => n.type === 'Button' && n.props.children === 'Copy invite link').props.onClick()
  check('one button copies it', globalThis.__copied[0] === link)
  check('it warns the link is a key', texts(invite).join(' ').includes('share it like a password'))
  find(invite, n => n.type === 'Button' && n.props.children === 'Close').props.onClick()
  check('closing the panel forgets the link', probeRoomInvite.get() === '' && probePairingView.get() === null)

  const dot = line => find(line, n => n.type === 'StatusDot').props.tone
  const good = probePeerLine({ status: { peers: [], room: { joined: true, connected: true, url: 'https://r' } } })
  check('a connected room says so', texts(good).includes('Team room connected') && dot(good) === 'good')
  const bad = probePeerLine({ status: { peers: [], room: { joined: true, connected: false, last_error: 'Couldn\'t reach the team room. It will be tried again.' } } })
  check('an unreachable room says why', texts(bad).join(' ').includes("Couldn't reach the team room") && dot(bad) === 'bad')
}

// ---- agent setup -----------------------------------------------------------------------------
{
  const wake = { ...base, blocked_reason: 'injection_not_allowed', blocked_message: 'needs injection', config_line: 'allow_gateway_injection: true', config_snippet: 'plugins:\n  entries:\n    herd:\n      allow_gateway_injection: true', setup_prompt: 'Please finish setting up the Herd plugin' }
  const setup = banner(wake)
  const all = texts(setup).join(' ')
  check('agent setup is three numbered steps', ['1.', '2.', '3.'].every(n => texts(setup).includes(n)))
  check('it says what the step is for', all.includes('One step left before your agent can answer @mentions'))
  const copyButtons = findAll(setup, n => n.type === 'Button' && String(n.props.children).startsWith('Cop'))
  check('there is exactly one copy button', copyButtons.length === 1 && copyButtons[0].props.children === 'Copy setup prompt', JSON.stringify(copyButtons.map(b => b.props.children)))
  globalThis.__copied.length = 0
  copyButtons[0].props.onClick()
  check('it copies the prompt for your agent', globalThis.__copied[0] === 'Please finish setting up the Herd plugin')
  check('and confirms', findAll(banner(wake), n => n.type === 'Button').some(b => b.props.children === 'Copied'))
  check('no restart button when the app has none', !findAll(setup, n => n.type === 'Button').some(b => b.props.children === 'Restart gateway'))
  let restarted = 0
  sdkHost.restartGateway = () => { restarted += 1 }
  find(banner(wake), n => n.type === 'Button' && n.props.children === 'Restart gateway').props.onClick()
  check('Restart gateway restarts it', restarted === 1)
  delete sdkHost.restartGateway
}

console.log(failures.length ? `\n${failures.length} FAILED` : '\nall checks passed')
process.exit(failures.length ? 1 : 0)
