// Track 0 pane probe — imports the SHIPPED desktop/plugin.js with the plugin SDK stubbed and drives the
// real MessageRow (reaction affordance + picker + pills) and WakeBanner, so the behaviour is checked by
// running the pane code rather than by grepping its source. Same method as s15_pane_render_probe.mjs:
// only the two import specifiers are rewritten; no code is re-typed, no dynamic evaluation.
//
//     node tests/track0_pane_probe.mjs [path/to/plugin.js]
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
export const PANES_AREA = 'panes'
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'nav'
export const atom = value => ({ value, set (next) { this.value = next }, get () { return this.value } })
export const host = { state: { activeSessionId: atom(null) }, navigate () {} }
export const pluginSettingsHref = id => '/settings/plugins/' + id
export const queryClient = { invalidateQueries () {} }
export const relativeTime = ms => String(ms)
export const useMutation = () => ({ isPending: false, mutate: v => { globalThis.__mutations.push(v) } })
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
  `${rewired}\nexport { MessageRow as probeMessageRow, WakeBanner as probeWakeBanner, ReactionPicker as probeReactionPicker, reactionPicker as probePickerAtom }\n`)

globalThis.__mutations = []
const { host: sdkHost } = await import(pathToFileURL(join(work, 'sdk.mjs')).href)
const { probeMessageRow: MessageRow, probeWakeBanner: WakeBanner, probeReactionPicker: ReactionPicker,
  probePickerAtom: pickerAtom } = await import(pathToFileURL(join(work, 'plugin.mjs')).href)

const failures = []
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

console.log(failures.length ? `\n${failures.length} FAILED` : '\nall checks passed')
process.exit(failures.length ? 1 : 0)
