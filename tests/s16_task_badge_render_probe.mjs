// S-16 task badge render probe — imports the SHIPPED desktop/plugin.js with the plugin SDK stubbed
// and calls its real TaskBadge() / MessageRow(), so the contract is checked by running the pane code:
//   * no task id -> no badge (the pane never guesses one)
//   * an id with a title -> `<id>` then `· <title>`, once each
//   * an id without a title -> the id alone (nothing title-shaped is invented)
//   * clicking the badge opens the Kanban board
//
// The only edit to the source is rewriting the two import specifiers to local stubs and appending
// one export line; the function bodies are imported verbatim, never re-typed. No dynamic code
// evaluation anywhere, no npm dependencies.
//
//     node tests/s16_task_badge_render_probe.mjs [path/to/plugin.js]
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pluginPath = process.argv[2] || resolve(here, '../desktop/plugin.js')
const source = readFileSync(pluginPath, 'utf8')

const work = mkdtempSync(join(tmpdir(), 's16-probe-'))
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
export const navigations = []
export const host = { navigate (path) { navigations.push(path) } }
export const pluginSettingsHref = id => '/settings/plugins/' + id
export const queryClient = { invalidateQueries () {} }
export const relativeTime = ms => String(ms)
export const useMutation = () => ({})
export const queryState = { data: undefined }
export const useQuery = () => queryState
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
  `${rewired}\nexport { TaskBadge as probeTaskBadge, MessageRow as probeMessageRow }\n`)

const { probeTaskBadge: TaskBadge, probeMessageRow: MessageRow } = await import(
  pathToFileURL(join(work, 'plugin.mjs')).href
)
const { queryState, navigations } = await import(pathToFileURL(join(work, 'sdk.mjs')).href)

const failures = []
const check = (name, actual, expected) => {
  const ok = JSON.stringify(actual) === JSON.stringify(expected)
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${name}${ok ? '' : ` -> ${JSON.stringify(actual)}`}`)
  if (!ok) failures.push(name)
}
const rendered = node => {
  const out = []
  const walk = n => {
    if (n == null) return
    if (typeof n === 'string') out.push(n)
    else if (Array.isArray(n)) n.forEach(walk)
    else if (typeof n === 'object' && n.props) walk(n.props.children)
  }
  walk(node)
  return out
}
const find = (node, type) => {
  if (node == null || typeof node !== 'object') return null
  if (Array.isArray(node)) {
    for (const child of node) {
      const hit = find(child, type)
      if (hit) return hit
    }
    return null
  }
  if (node.type === type) return node
  return node.props ? find(node.props.children, type) : null
}

const ID = 't_e7741438'
const TITLE = 'S-16: Agent response links to the Kanban board'

// 1. No id, no badge — the pane never guesses one.
queryState.data = { title: TITLE }
check('no props', TaskBadge({}), null)
check('taskId null', TaskBadge({ taskId: null }), null)
check("taskId ''", TaskBadge({ taskId: '' }), null)
check("taskId '   '", TaskBadge({ taskId: '   ' }), null)

// 2. An id with a title renders the id, then the title, once each.
queryState.data = { title: TITLE }
const withTitle = TaskBadge({ taskId: ID })
check('id + title texts', rendered(withTitle), [ID, '· ' + TITLE])

// 3. No title means the id alone — nothing title-shaped is invented.
for (const [label, data] of [['undefined', undefined], ['{}', {}], ['title null', { title: null }],
  ['title blank', { title: '  ' }]]) {
  queryState.data = data
  check(`id only (${label})`, rendered(TaskBadge({ taskId: ID })), [ID])
}

// 4. Clicking opens the Kanban board, exactly once.
queryState.data = { title: TITLE }
const badge = TaskBadge({ taskId: ID })
navigations.length = 0
badge.props.onClick()
check('click navigates once to /kanban', navigations, ['/kanban'])

// 5. MessageRow shows a TaskBadge only when the message carries a task_id.
const msg = extra => Object.assign({ id: 'm1', content: 'hi', author_type: 'agent', author_name: 'Hermes',
  created_at: '2026-11-06T00:00:00.000+00:00', reactions: [] }, extra)
const tied = find(MessageRow({ message: msg({ task_id: ID }), channelId: 'general' }), 'TaskBadge')
check('MessageRow with task_id renders TaskBadge', Boolean(tied), true)
check('TaskBadge gets the id', tied && tied.props.taskId, ID)
check('MessageRow without task_id renders none',
  find(MessageRow({ message: msg({}), channelId: 'general' }), 'TaskBadge'), null)

console.log(failures.length ? `\nPROBE FAIL (${failures.length}): ${failures.join(', ')}` : '\nPROBE OK')
process.exit(failures.length ? 1 : 0)
