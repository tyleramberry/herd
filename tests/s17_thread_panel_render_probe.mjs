// S-17 thread panel render probe — imports the SHIPPED desktop/plugin.js with the plugin SDK stubbed, and calls
// its real HerdView(), ThreadPanel() and ThreadBody(), so the render contract is checked by running the pane code
// (spec §2):
//   * the route renders the channel column, the message column and, with a thread open, a right-hand panel
//     as three siblings in that order;
//   * the panel is 35–45% wide, labelled "Thread", and has a visible close control;
//   * the panel shows the thread root, then its replies, oldest first, and its own composer (threadParentId set);
//   * Esc closes the panel; a key the composer already handled (defaultPrevented) does not;
//   * the compact pane keeps the thread in its column (no side panel there);
//   * opening a thread leaves the channel column in place.
//
// The only edits to the source are rewriting the two import specifiers to local stubs and appending one export
// line; every function body is imported verbatim, never re-typed. No dynamic code evaluation, no npm dependencies.
//
//     node tests/s17_thread_panel_render_probe.mjs [path/to/plugin.js]
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pluginPath = process.argv[2] || resolve(here, '../desktop/plugin.js')
const source = readFileSync(pluginPath, 'utf8')

const work = mkdtempSync(join(tmpdir(), 's17-probe-'))
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
export const PANES_AREA = 'panes'
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'nav'
export const atom = value => ({ value, set (next) { this.value = next }, get () { return this.value } })
export const host = { navigate () {} }
export const pluginSettingsHref = id => '/settings/plugins/' + id
export const queryClient = { invalidateQueries () {} }
export const relativeTime = ms => String(ms)
export const useMutation = () => ({ mutate () {}, isPending: false })
export const queries = {}
export const useQuery = ({ queryKey }) => {
  const [kind, id] = queryKey.slice(1)
  if (kind === 'thread') return (queries.thread && queries.thread[id]) || { data: undefined }
  return queries[kind] || { data: undefined }
}
export const useValue = $a => $a.get()
`)
writeFileSync(join(work, 'jsx-runtime.mjs'), `
const typeName = type => (typeof type === 'function' ? type.name : type)
export const jsx = (type, props) => ({ type: typeName(type), props: props || {} })
export const jsxs = (type, props) => ({ type: typeName(type), props: props || {} })
`)

const rewired = source
  .replace("from '@hermes/plugin-sdk'", "from './sdk.mjs'")
  .replace("from 'react/jsx-runtime'", "from './jsx-runtime.mjs'")
if (rewired === source) throw new Error('import specifiers did not match — probe needs updating')
writeFileSync(join(work, 'plugin.mjs'),
  `${rewired}\nexport { HerdView as probeHerdView, ThreadPanel as probeThreadPanel, ThreadBody as probeThreadBody, thread as probeThread }\n`)

const { probeHerdView: HerdView, probeThreadPanel: ThreadPanel, probeThreadBody: ThreadBody,
  probeThread: thread } = await import(pathToFileURL(join(work, 'plugin.mjs')).href)
const { queries } = await import(pathToFileURL(join(work, 'sdk.mjs')).href)

const failures = []
const check = (name, actual, expected) => {
  const ok = JSON.stringify(actual) === JSON.stringify(expected)
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${name}${ok ? '' : ` -> ${JSON.stringify(actual)}`}`)
  if (!ok) failures.push(name)
}
const ok = (name, cond, detail = '') => {
  console.log(`${cond ? 'ok  ' : 'FAIL'}  ${name}${cond ? '' : ` (${detail})`}`)
  if (!cond) failures.push(name)
}
const textOf = node => {
  const out = []
  const walk = n => {
    if (n == null) return
    if (typeof n === 'string') out.push(n)
    else if (Array.isArray(n)) n.forEach(walk)
    else if (typeof n === 'object' && n.props) walk(n.props.children)
  }
  walk(node)
  return out.join('')
}
const findAll = (node, pred, out = []) => {
  if (node == null || typeof node !== 'object') return out
  if (Array.isArray(node)) {
    node.forEach(child => findAll(child, pred, out))
    return out
  }
  if (pred(node)) out.push(node)
  if (node.props) findAll(node.props.children, pred, out)
  return out
}
const byLabel = (node, label) => findAll(node, n => n.props && n.props['aria-label'] === label)[0] || null

// Fixtures: two teammates' messages in #general; one thread with a root and two replies.
const CH = { id: 'general', name: 'general', is_dm: false, members: [], topic: '', message_count: 3 }
const ROOT = { id: 'r1', channel_id: 'general', author_name: 'riley', author_type: 'human', content: 'root text',
  created_at: '2026-11-08T00:00:00.000+00:00', reactions: [], reply_count: 2 }
const REPLY_A = { id: 'a1', channel_id: 'general', author_name: 'ash', author_type: 'agent', content: 'first reply',
  created_at: '2026-11-08T00:01:00.000+00:00', reactions: [] }
const REPLY_B = { id: 'b1', channel_id: 'general', author_name: 'kai', author_type: 'human', content: 'second reply',
  created_at: '2026-11-08T00:02:00.000+00:00', reactions: [] }
queries.thread = { r1: { data: { parent: ROOT, replies: [REPLY_A, REPLY_B] }, isLoading: false, isError: false } }
queries.channels = { data: [CH], isLoading: false, isError: false }
queries.status = { data: { self: { gateway_id: 'me', display_name: 'tyler' }, peers: [], refused: [],
  incoming: [], herd_secret_set: true }, isLoading: false, isError: false, isSuccess: true }
queries.participants = { data: [], isLoading: false, isError: false }

// 1. The route with a thread open: channel column, message column, then the panel, in that order.
thread.page.set('r1')
const route = HerdView({ compact: false })
const row = findAll(route, n => Array.isArray(n.props.children) && n.props.children.some(c => c && c.type === 'ChannelList'))[0]
const kinds = row ? row.props.children.filter(Boolean).map(c => c.type) : []
check('route row: ChannelList, MessageView, ThreadPanel in order', kinds, ['ChannelList', 'MessageView', 'ThreadPanel'])
const panelNode = row ? row.props.children.find(c => c && c.type === 'ThreadPanel') : null
check('panel is keyed to the open root', panelNode && panelNode.props.rootId, 'r1')
check('panel is given the selected channel', panelNode && panelNode.props.channel.id, 'general')
const messageColumn = row ? row.props.children.find(c => c && c.type === 'MessageView') : null
check('channel column stays in the route', Boolean(row && row.props.children[0].type === 'ChannelList'), true)
check('message column keeps the channel open (not replaced by the thread)', messageColumn && messageColumn.props.channel.id, 'general')

// 2. The panel itself: width, label, close control, composer, Esc.
const panel = ThreadPanel({ channel: CH, rootId: 'r1', selfId: 'me', $thread: thread.page })
check('panel is a labelled region', [panel.type, panel.props.role, panel.props['aria-label']],
  ['section', 'region', 'Thread'])
ok('panel is 35–45% of the row', /(^|\s)w-\[(3[5-9]|4[0-5])%\](\s|$)/.test(panel.props.className),
  panel.props.className)
const close = byLabel(panel, 'Close thread')
ok('a visible close control with an accessible name', close && close.props.onClick, 'no Close thread control')
thread.page.set('r1')
close.props.onClick()
check('the close control closes the thread', thread.page.get(), null)

thread.page.set('r1')
const pAgain = ThreadPanel({ channel: CH, rootId: 'r1', selfId: 'me', $thread: thread.page })
const noop = { key: 'Escape', defaultPrevented: true, preventDefault () {} }
pAgain.props.onKeyDown(noop)
check('Esc the composer already handled does not close the panel', thread.page.get(), 'r1')
pAgain.props.onKeyDown({ key: 'Enter', defaultPrevented: false, preventDefault () {} })
check('other keys do not close the panel', thread.page.get(), 'r1')
pAgain.props.onKeyDown({ key: 'Escape', defaultPrevented: false, preventDefault () {} })
check('Esc closes the panel', thread.page.get(), null)

const composer = findAll(panel, n => n.type === 'Composer')[0]
check('panel has its own composer, replying in this thread', composer && [composer.props.threadParentId, composer.props.autoFocus],
  ['r1', true])

// 3. The panel body: root first, then replies oldest first (a ThreadBody row per message).
const body = ThreadBody({ rootId: 'r1' })
const rows = (Array.isArray(body) ? body : body.props.children).filter(c => c && c.type === 'MessageRow')
check('thread body: root, then replies in order', rows.map(r => r.props.message.id), ['r1', 'a1', 'b1'])
check('thread body: root message is the parent', rows[0] && rows[0].props.message.content, 'root text')

// 4. The compact pane keeps the thread in its column: no side panel there, and the column becomes the thread.
thread.pane.set('r1')
const pane = HerdView({ compact: true })
check('compact pane renders no side panel', findAll(pane, n => n.type === 'ThreadPanel').length, 0)
const paneRow = findAll(pane, n => Array.isArray(n.props.children) && n.props.children.some(c => c && c.type === 'ChannelList'))[0]
const paneMessage = paneRow && paneRow.props.children.find(c => c && c.type === 'MessageView')
check('compact pane swaps the column for the thread view', paneMessage && paneMessage.props.compact, true)
thread.pane.set(null)

// 5. No open thread: the route has no panel at all.
thread.page.set(null)
const plain = HerdView({ compact: false })
check('no open thread, no panel', findAll(plain, n => n.type === 'ThreadPanel').length, 0)

console.log(failures.length ? `\nPROBE FAIL (${failures.length}): ${failures.join(', ')}` : '\nPROBE OK')
process.exit(failures.length ? 1 : 0)
