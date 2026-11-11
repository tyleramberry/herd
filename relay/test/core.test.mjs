import test from 'node:test'
import assert from 'node:assert/strict'
import { DatabaseSync } from 'node:sqlite'
import { Room, isReactionEmoji, route, bearer } from '../src/core.js'

function room() {
  const sqlite = new DatabaseSync(':memory:')
  const db = { all: (q, ...p) => (/^\s*SELECT/i.test(q) ? sqlite.prepare(q).all(...p) : (sqlite.prepare(q).run(...p), [])) }
  return new Room(db, 'testroom0001')
}
const from = (id, name) => ({ gateway_id: id, display_name: name, token: `token-for-${id}-0123456789` })
const msg = (id, gw, extra = {}) => ({ id, channel_id: 'general', author_type: 'human', author_name: gw, gateway_id: gw, content: 'hi ' + id, created_at: '2026-11-10T00:00:00.000+00:00', ...extra })
const general = { id: 'general', name: 'general', is_dm: false, members: [], created_at: '2026-11-10T00:00:00.000+00:00' }

test('the first key owns the room', async () => {
  const r = room()
  assert.equal(await r.authorize('k'.repeat(40)), true)
  assert.equal(await r.authorize('k'.repeat(40)), true)
  assert.equal(await r.authorize('z'.repeat(40)), false)
  assert.equal(await r.authorize('short'), false)
})

test('messages reach the others and never echo to their author', async () => {
  const r = room()
  await r.sync({ from: from('a1', 'A'), channels: [general], messages: [msg('m1', 'a1')] })
  const b = (await r.sync({ from: from('b1', 'B') })).body
  assert.deepEqual(b.messages.map(m => m.id), ['m1'])
  assert.equal(b.from.relay, true)
  const a = (await r.sync({ from: from('a1', 'A'), after_seq: 0 })).body
  assert.deepEqual(a.messages, [])
  assert.equal(a.next_seq, 1)
  assert.deepEqual(b.participants.map(p => p.display_name).sort(), ['A', 'B'])
})

test('a member id is bound to its first token', async () => {
  const r = room()
  await r.sync({ from: from('a1', 'A') })
  const out = await r.sync({ from: { gateway_id: 'a1', display_name: 'A', token: ['another', 'member', 'value', '0123456789'].join('-') } })
  assert.equal(out.status, 403)
  assert.equal((await r.sync({ from: { gateway_id: 'a1' } })).status, 401)
})

test('a DM goes only to its two people', async () => {
  const r = room()
  const dm = { id: 'dm:a1+b1', is_dm: true, members: [{ id: 'a1', name: 'A' }, { id: 'b1', name: 'B' }] }
  await r.sync({ from: from('a1', 'A'), channels: [dm], messages: [msg('d1', 'a1', { channel_id: 'dm:a1+b1' })] })
  assert.equal((await r.sync({ from: from('b1', 'B') })).body.messages.length, 1)
  const c = (await r.sync({ from: from('c1', 'C') })).body
  assert.equal(c.messages.length, 0)
  assert.equal(c.channels.length, 0)
  const forged = await r.sync({ from: from('c1', 'C'), messages: [msg('d2', 'c1', { channel_id: 'dm:a1+b1' })] })
  assert.equal(forged.body.dropped, 1)
})

test('edits: author only, newest wins, late joiners get the edited text', async () => {
  const r = room()
  await r.sync({ from: from('a1', 'A'), channels: [general], messages: [msg('m1', 'a1')] })
  const edit = (gw, text, at) => ({ message_id: 'm1', gateway_id: gw, content: text, deleted: 0, edited_at: at })
  await r.sync({ from: from('b1', 'B'), edits: [edit('b1', 'hijack', '2026-11-10T00:01:00Z')] })
  await r.sync({ from: from('a1', 'A'), edits: [edit('a1', 'second', '2026-11-10T00:02:00Z')] })
  await r.sync({ from: from('a1', 'A'), edits: [edit('a1', 'stale', '2026-11-10T00:01:30Z')] })
  const c = (await r.sync({ from: from('c1', 'C') })).body
  assert.equal(c.messages[0].content, 'second')
  assert.deepEqual(c.edits.map(e => e.content), ['second'])
})

test('wait reports changes and being alone', async () => {
  const r = room()
  await r.sync({ from: from('a1', 'A'), channels: [general] })
  const tokenA = from('a1').token
  const alone = await r.wait({ gateway: 'a1', after_seq: 0, ev: r.ev }, tokenA, 50)
  assert.equal(alone.body.alone, true)
  await r.sync({ from: from('b1', 'B') })
  const ev = r.ev
  const held = r.wait({ gateway: 'a1', after_seq: 0, after_rseq: 0, after_eseq: 0, ev }, tokenA, 2000)
  await new Promise(resolve => setTimeout(resolve, 20))
  await r.sync({ from: from('b1', 'B'), messages: [msg('m9', 'b1')] })
  assert.equal((await held).body.changed, true)
  assert.equal((await r.wait({ gateway: 'zz', ev: 0 }, 'x'.repeat(20), 10)).status, 403)
})

test('small helpers', () => {
  assert.equal(isReactionEmoji('🚀'), true)
  assert.equal(isReactionEmoji('lol'), false)
  assert.deepEqual(route('/r/abcdefgh1234/hermes-multiplayer/v1/sync'), { roomId: 'abcdefgh1234', action: 'sync' })
  assert.equal(route('/r/x/hermes-multiplayer/v1/sync'), null)
  assert.equal(bearer('Bearer abc'), 'abc')
})

test('people get pages; relay paths and the key never do', async () => {
  const { pageFor, INSTALL_DEEP_LINK } = await import('../src/pages.js')
  const install = pageFor('GET', '/install')
  assert.equal(install.status, 200)
  assert.match(install.html, /Install in Hermes/)
  assert.ok(install.html.includes(INSTALL_DEEP_LINK))
  const invite = pageFor('GET', '/r/0123456789abcdef0123')
  assert.match(invite.html, /invited/)
  assert.match(invite.headers['Content-Security-Policy'], /default-src 'none'/)
  assert.equal(invite.headers['Referrer-Policy'], 'no-referrer')
  assert.equal(pageFor('POST', '/r/0123456789abcdef0123'), null)
  assert.equal(pageFor('GET', '/r/0123456789abcdef0123/hermes-multiplayer/v1/wait'), null)
  assert.equal(pageFor('GET', '/r/short'), null)
  assert.equal(pageFor('GET', '/elsewhere'), null)
})
