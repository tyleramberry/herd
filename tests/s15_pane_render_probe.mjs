// S-15 pane render probe — imports the SHIPPED desktop/plugin.js with the plugin SDK stubbed and
// calls its real WorkLine(), so the two contract cases are checked by running the pane code:
//   * no status from the backend -> nothing is rendered (never a placeholder, default or guess)
//   * a status from the backend  -> exactly that phrase, once, verbatim
// It also calls the real MessageRow() (the author badge) and PeerLine() (the S-19 refusal line, which
// must say WHY a peer is refused instead of degrading into "No teammate connected").
//
// The only edit to the source is rewriting the two import specifiers to local stubs and appending
// one export of WorkLine; the function body itself is imported verbatim, never re-typed. No dynamic
// code evaluation anywhere, no npm dependencies.
//
//     node tests/s15_pane_render_probe.mjs [path/to/plugin.js]
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pluginPath = process.argv[2] || resolve(here, '../desktop/plugin.js')
const source = readFileSync(pluginPath, 'utf8')

const work = mkdtempSync(join(tmpdir(), 's15-probe-'))
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
export const host = { navigate () {} }
export const pluginSettingsHref = id => '/settings/plugins/' + id
export const queryClient = { invalidateQueries () {} }
export const relativeTime = ms => String(ms)
export const useMutation = () => ({})
export const useQuery = () => ({})
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
writeFileSync(join(work, 'plugin.mjs'),
  `${rewired}\nexport { WorkLine as probeWorkLine, MessageRow as probeMessageRow, PeerLine as probePeerLine }\n`)

const { probeWorkLine: WorkLine, probeMessageRow: MessageRow, probePeerLine: PeerLine } = await import(
  pathToFileURL(join(work, 'plugin.mjs')).href
)

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

// 1. Nothing from the backend renders nothing — the feature's stated contract (TC-11.2).
check('status undefined', WorkLine({ status: undefined }), null)
check('status null', WorkLine({ status: null }), null)
check('status {}', WorkLine({ status: {} }), null)
check('agent_status null (never set)', WorkLine({ status: { agent_status: null } }), null)
check('agent_status {} (no phrase)', WorkLine({ status: { agent_status: {} } }), null)
check('agent_status empty phrase', WorkLine({ status: { agent_status: { phrase: '' } } }), null)
check('status with no agent_status key', WorkLine({ status: { self: { display_name: 'tyler' } } }), null)

// 2. A phrase from the backend renders exactly that phrase, once, and invents nothing (TC-11.1).
for (const phrase of ['reading the code', 'writing the code', 'reviewing', 'done', 'idle']) {
  const node = WorkLine({ status: { agent_status: { phrase, agent: "tyler's Hermes" } } })
  check(`renders "${phrase}"`, rendered(node), [phrase])
  check(`title for "${phrase}"`, node.props.title, `tyler's Hermes: ${phrase}`)
}

// 3. Only agent-authored messages carry a badge, decided by author_type and never by the author name
//    (TC-11.6). Humans are the unbadged default (spec §3).
const badgeLabel = message => {
  const row = MessageRow({ message, channelId: 'general' })
  const header = row.props.children[1]
  const badge = header.props.children.find(child => child && child.type === 'Badge')
  return badge ? badge.props.children : null
}
const msg = extra => Object.assign(
  { id: 'm1', content: 'hi', created_at: '2026-11-06T00:00:00.000+00:00', reactions: [] }, extra)
check('human post -> no badge', badgeLabel(msg({ author_type: 'human', author_name: 'Tyler' })), null)
check('agent post -> agent badge', badgeLabel(msg({ author_type: 'agent', author_name: "Tyler's Hermes" })),
  'agent')
check('peer agent post -> agent badge', badgeLabel(msg({ author_type: 'agent', author_name: 'Riley' })), 'agent')
check('name is never the badge', badgeLabel(msg({ author_type: 'human', author_name: "Tyler's Hermes" })), null)

// 4. The peer line: a refused cleartext peer says why, and never reads as "no teammate connected"
//    (S-19). The positive control below is the plain connected/unconfigured behaviour, unchanged.
const peerLine = status => rendered(PeerLine({ status }))
const REFUSED_REASON =
  "peer_url is http:// on a non-loopback host — refused. Use https, a VPN/tailnet, " +
  "or turn on 'Send the peer key in cleartext (unsafe)'."
check('refused peer renders the reason, not a generic state',
  peerLine({ peers: [], refused: [{ name: 'brooklyn', url: 'http://brooklyn-mac.local:8642', reason: REFUSED_REASON }] }),
  ['Refused brooklyn — ' + REFUSED_REASON])
check('refused peer with no name falls back to its url',
  peerLine({ peers: [], refused: [{ url: 'http://brooklyn-mac.local:8642', reason: REFUSED_REASON }] }),
  ['Refused http://brooklyn-mac.local:8642 — ' + REFUSED_REASON])
check('a refused entry with no reason is ignored (never a blank line)',
  peerLine({ peers: [], refused: [{ name: 'brooklyn' }] }), ['No teammate connected'])
check('connected peer still renders the existing line',
  peerLine({ peers: [{ name: 'riley', remote_name: 'riley', connected: true, has_key: true }] }),
  ['Connected to riley'])
check('no peers and no refusal is unchanged',
  peerLine({ peers: [] }), ['No teammate connected'])
check('no status at all keeps the existing no-teammate line',
  rendered(PeerLine({ status: undefined })), ['No teammate connected'])

// 5. S-20: this gateway having no Herd secret is its own, distinct state — and it only renders when
//    the backend says so explicitly (older/partial payloads keep the old behaviour).
check('no herd secret set renders the settings prompt, not a link state',
  peerLine({ peers: [{ name: 'riley', remote_name: 'riley', connected: true, has_key: true }],
             herd_secret_set: false }),
  ['This gateway has no Herd secret set. Set one in Settings → Plugins → Herd.'])
check('herd_secret_set true is unchanged',
  peerLine({ peers: [{ name: 'riley', remote_name: 'riley', connected: true, has_key: true }],
             herd_secret_set: true }),
  ['Connected to riley'])
check('a status missing herd_secret_set is unchanged',
  peerLine({ peers: [{ name: 'riley', remote_name: 'riley', connected: true, has_key: true }] }),
  ['Connected to riley'])
check('peer with no stored secret asks for the Herd secret (not the gateway API key)',
  peerLine({ peers: [{ name: 'riley', connected: false, has_key: false, last_attempt: '' }],
             herd_secret_set: true }),
  ["Add riley's Herd secret to connect"])

// 6. One line per teammate (spec §1.5): a dead teammate never hides a live one, and a refusal still shows.
check('two teammates: one line each, in order',
  peerLine({ peers: [{ name: 'riley', remote_name: 'riley', connected: true, has_key: true },
                     { name: 'ash', connected: false, has_key: true, last_attempt: '2026-11-08T00:00:00Z' }] }),
  ['Connected to riley', "Can't reach ash. Messages will send when they're back."])
check('a refused teammate is listed beside a connected one',
  peerLine({ peers: [{ name: 'riley', remote_name: 'riley', connected: true, has_key: true }],
             refused: [{ name: 'kai', url: 'http://kai.local:8642', reason: 'Refused for test.' }] }),
  ['Connected to riley', 'Refused kai — Refused for test.'])

console.log(failures.length ? `\nPROBE FAIL (${failures.length}): ${failures.join(', ')}` : '\nPROBE OK')
process.exit(failures.length ? 1 : 0)
