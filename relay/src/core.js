// Hermes Multiplayer team room: the logic of the relay, with no dependency on where it runs.
//
// A room speaks the same sync exchange a Hermes Multiplayer gateway does (dashboard/multiplayer_store.py, handle_peer_sync): a
// member POSTs what it wrote plus its cursors, and gets back what the others wrote. The room keeps every row,
// so members never need to reach each other, and a message written while a teammate is offline waits here.
//
// `db` is a tiny adapter over SQLite: `db.all(sql, ...params)` returns an array of row objects. The Cloudflare
// Durable Object (worker.js) and the node server (../server.mjs) each supply one.

export const PROTOCOL_VERSION = 2
export const BATCH_LIMIT = 200
export const MAX_CONTENT = 20000
export const MAX_MEMBERS = 50
export const MAX_CHANNEL_MEMBERS = 5
export const ONLINE_MS = 60000
export const STATUS_TTL_MS = 300000
export const TYPING_TTL_MS = 8000
export const WAIT_HOLD_MS = 25000
export const MAX_BODY_BYTES = 4 * 1024 * 1024

const ID_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/
const CHANNEL_RE = /^[a-z0-9][a-z0-9_-]{0,47}$/
const ROOM_RE = /^[A-Za-z0-9_-]{8,64}$/
const KEY_RE = /^[A-Za-z0-9_-]{16,128}$/
const STATUS_PHRASES = ['reading the code', 'writing the code', 'reviewing', 'done', 'idle']

export const validRoomId = id => typeof id === 'string' && ROOM_RE.test(id)
export const validKey = key => typeof key === 'string' && KEY_RE.test(key)

export async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(String(text))
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('')
}

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS room (k TEXT PRIMARY KEY, v TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS members (
     gateway_id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL, last_seen INTEGER NOT NULL,
     status TEXT NOT NULL DEFAULT '', status_at INTEGER NOT NULL DEFAULT 0,
     typing TEXT NOT NULL DEFAULT '', typing_at INTEGER NOT NULL DEFAULT 0)`,
  `CREATE TABLE IF NOT EXISTS channels (
     id TEXT PRIMARY KEY, name TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '', is_dm INTEGER NOT NULL DEFAULT 0,
     members TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, topic_at TEXT NOT NULL DEFAULT '')`,
  `CREATE TABLE IF NOT EXISTS messages (
     seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, channel_id TEXT NOT NULL,
     gateway_id TEXT NOT NULL, history INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS reactions (
     rseq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, message_id TEXT NOT NULL,
     channel_id TEXT NOT NULL, emoji TEXT NOT NULL, gateway_id TEXT NOT NULL, active INTEGER NOT NULL,
     created_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS edits (
     eseq INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT NOT NULL UNIQUE, channel_id TEXT NOT NULL DEFAULT '',
     content TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, edited_at TEXT NOT NULL, gateway_id TEXT NOT NULL)`,
]

const cleanName = (value, fallback) => {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim().slice(0, 64)
  return text || fallback
}
const str = (value, max) => String(value ?? '').slice(0, max)
const stamp = value => {
  const ms = Date.parse(String(value ?? ''))
  return Number.isNaN(ms) ? null : ms
}
const cursor = value => {
  const n = Number(value)
  return Number.isInteger(n) && n > 0 ? n : 0
}
const dmMembers = id => (String(id).startsWith('dm:') ? String(id).slice(3).split('+').filter(Boolean) : [])
const parseJson = (text, fallback) => {
  try {
    return JSON.parse(text)
  } catch {
    return fallback
  }
}

// One short emoji, never text: the same rule the gateway applies (is_reaction_emoji).
export function isReactionEmoji(value) {
  if (typeof value !== 'string' || !value) return false
  const points = Array.from(value)
  if (value.length > 16) return false
  let pictograph = false
  for (const ch of points) {
    const c = ch.codePointAt(0)
    if (c === 0x200d || c === 0xfe0f || c === 0x20e3 || (c >= 0x1f3fb && c <= 0x1f3ff) || (c >= 0xe0020 && c <= 0xe007f)) continue
    if (
      (c >= 0x1f000 && c <= 0x1faff) || (c >= 0x2600 && c <= 0x27bf) || (c >= 0x2b00 && c <= 0x2bff) ||
      (c >= 0x2190 && c <= 0x21ff) || (c >= 0x2300 && c <= 0x23ff) || (c >= 0x25a0 && c <= 0x25ff) ||
      (c >= 0x2900 && c <= 0x297f) ||
      [0xa9, 0xae, 0x203c, 0x2049, 0x2122, 0x2139, 0x3030, 0x303d, 0x3297, 0x3299].includes(c)
    ) {
      pictograph = true
      continue
    }
    return false
  }
  return pictograph
}

/** Lets a held `wait` request return the moment anything in the room changes. */
export class Hub {
  constructor() {
    this.waiters = new Set()
  }
  notify() {
    const all = [...this.waiters]
    this.waiters.clear()
    for (const wake of all) wake()
  }
  wait(ms) {
    return new Promise(resolve => {
      let timer = null
      const wake = () => {
        if (timer !== null) clearTimeout(timer)
        this.waiters.delete(wake)
        resolve()
      }
      timer = setTimeout(wake, ms)
      this.waiters.add(wake)
    })
  }
}

export class Room {
  constructor(db, roomId, now = () => Date.now()) {
    this.db = db
    this.roomId = roomId
    this.now = now
    this.hub = new Hub()
    for (const statement of SCHEMA) db.all(statement)
  }

  meta(key, fallback = '') {
    const row = this.db.all('SELECT v FROM room WHERE k = ?', key)[0]
    return row ? row.v : fallback
  }

  setMeta(key, value) {
    this.db.all('INSERT INTO room(k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v', key, String(value))
  }

  get ev() {
    return Number(this.meta('ev', '0')) || 0
  }

  bump() {
    this.setMeta('ev', this.ev + 1)
    this.dirty = true
  }

  /** Wake every held wait if anything changed since the last time. */
  flush() {
    if (!this.dirty) return
    this.dirty = false
    this.hub.notify()
  }

  /** The room belongs to the first key that reaches it; after that, only that key opens it. */
  async authorize(key) {
    if (!validKey(key)) return false
    const hash = await sha256Hex(`hermes-multiplayer-room:${this.roomId}:${key}`)
    const known = this.meta('key_hash')
    if (!known) {
      this.setMeta('key_hash', hash)
      this.setMeta('created_at', new Date(this.now()).toISOString())
      return true
    }
    return known === hash
  }

  /** Recognise a member by gateway id and its own token. Returns an HTTP status (200 = fine). */
  async admit(gatewayId, name, token, create) {
    if (!ID_RE.test(String(gatewayId || ''))) return 422
    if (typeof token !== 'string' || token.length < 16 || token.length > 200) return 401
    const hash = await sha256Hex(`hermes-multiplayer-member:${gatewayId}:${token}`)
    const row = this.db.all('SELECT name, token_hash, last_seen FROM members WHERE gateway_id = ?', gatewayId)[0]
    const now = this.now()
    if (!row) {
      if (!create) return 403
      if (this.db.all('SELECT COUNT(*) AS n FROM members')[0].n >= MAX_MEMBERS) return 429
      this.db.all('INSERT INTO members(gateway_id, name, token_hash, last_seen) VALUES (?, ?, ?, ?)',
        gatewayId, cleanName(name, 'teammate'), hash, now)
      this.bump()
      return 200
    }
    if (row.token_hash !== hash) return 403
    const fresh = name === undefined ? row.name : cleanName(name, row.name)
    if (now - row.last_seen >= ONLINE_MS || fresh !== row.name) this.bump() // back online, or renamed
    this.db.all('UPDATE members SET name = ?, last_seen = ? WHERE gateway_id = ?', fresh, now, gatewayId)
    return 200
  }

  channel(id) {
    const row = this.db.all('SELECT * FROM channels WHERE id = ?', id)[0]
    if (!row) return null
    return { ...row, is_dm: Boolean(row.is_dm), members: parseJson(row.members, []) }
  }

  /** May `gatewayId` see (or write into) this channel? DMs and member-listed channels: members only. */
  allowed(channelId, gatewayId, cache) {
    const key = `${channelId}\u0000${gatewayId}`
    if (cache && cache.has(key)) return cache.get(key)
    let ok
    if (String(channelId).startsWith('dm:')) {
      ok = dmMembers(channelId).includes(gatewayId)
    } else {
      const ch = this.channel(channelId)
      const ids = ch ? ch.members.map(m => m && m.id).filter(Boolean) : []
      ok = ids.length === 0 || ids.includes(gatewayId)
    }
    if (cache) cache.set(key, ok)
    return ok
  }

  upsertChannel(ch, sender) {
    if (!ch || typeof ch !== 'object') return
    const id = String(ch.id ?? '')
    const created = stamp(ch.created_at) === null ? new Date(this.now()).toISOString() : str(ch.created_at, 40)
    if (ch.is_dm) {
      const members = (Array.isArray(ch.members) ? ch.members : [])
        .filter(m => m && typeof m === 'object')
        .slice(0, 2)
        .map(m => ({ id: str(m.id, 64), name: cleanName(m.name, '?') }))
      if (members.length !== 2 || !members.every(m => ID_RE.test(m.id))) return
      if (id !== 'dm:' + members.map(m => m.id).sort().join('+')) return
      if (!members.some(m => m.id === sender)) return // only the two people in a DM can bring it here
      const name = members.map(m => m.name).join(' & ')
      const row = this.db.all('SELECT name, members FROM channels WHERE id = ?', id)[0]
      const json = JSON.stringify(members)
      if (!row) {
        this.db.all('INSERT INTO channels(id, name, topic, is_dm, members, created_at) VALUES (?, ?, \'\', 1, ?, ?)',
          id, name, json, created)
        this.bump()
      } else if (row.name !== name || row.members !== json) {
        this.db.all('UPDATE channels SET name = ?, members = ? WHERE id = ?', name, json, id)
      }
      return
    }
    if (!CHANNEL_RE.test(id)) return
    const raw = Array.isArray(ch.members) ? ch.members : []
    const members = []
    for (const item of raw) {
      const mid = String(item && typeof item === 'object' ? item.id ?? '' : item ?? '')
      if (!ID_RE.test(mid)) return
      if (members.some(m => m.id === mid)) continue
      members.push({ id: mid, name: cleanName(item && typeof item === 'object' ? item.name : '', mid) })
    }
    if (members.length > MAX_CHANNEL_MEMBERS) return
    if (members.length && !members.some(m => m.id === sender)) return // not this sender's channel to bring
    const topic = String(ch.topic ?? '').replace(/\s+/g, ' ').trim().slice(0, 200)
    const topicAt = stamp(ch.topic_at) === null ? created : str(ch.topic_at, 40)
    const row = this.db.all('SELECT topic, topic_at, created_at, members FROM channels WHERE id = ?', id)[0]
    if (!row) {
      this.db.all(
        'INSERT INTO channels(id, name, topic, is_dm, members, created_at, topic_at) VALUES (?, ?, ?, 0, ?, ?, ?)',
        id, id, topic, JSON.stringify(members), created, topicAt)
      this.bump()
      return
    }
    // A stored channel's member list never changes here; a sender outside it cannot touch its topic either.
    const ids = parseJson(row.members, []).map(m => m && m.id).filter(Boolean)
    if (ids.length && !ids.includes(sender)) return
    const theirs = stamp(topicAt)
    const ours = stamp(row.topic_at || row.created_at) ?? 0
    if (theirs !== null && theirs > ours) {
      this.db.all('UPDATE channels SET topic = ?, topic_at = ? WHERE id = ?', topic, topicAt, id)
      if (topic !== row.topic) this.bump()
    }
  }

  validMessage(m, sender) {
    if (!m || typeof m !== 'object') return null
    const id = str(m.id, 64)
    const channelId = str(m.channel_id, 200)
    const gid = str(m.gateway_id, 64).trim() || sender
    const authorType = String(m.author_type || 'human')
    const deleted = m.deleted ? 1 : 0
    const content = deleted ? '' : String(m.content ?? '')
    if (!id || !channelId || !ID_RE.test(gid)) return null
    if (!['human', 'agent'].includes(authorType)) return null
    if (!deleted && (!content.trim() || content.length > MAX_CONTENT)) return null
    const createdAt = stamp(m.created_at) === null ? new Date(this.now()).toISOString() : str(m.created_at, 40)
    const editedAt = stamp(m.edited_at) === null ? '' : str(m.edited_at, 40)
    return {
      id, channel_id: channelId, author_type: authorType, author_name: cleanName(m.author_name, 'someone'),
      gateway_id: gid, gateway_name: cleanName(m.gateway_name, ''), content, created_at: createdAt,
      thread_parent_id: str(m.thread_parent_id, 64) || null, promoted_from: str(m.promoted_from, 200) || null,
      task_id: str(m.task_id, 64) || null, edited_at: editedAt || null, deleted,
    }
  }

  applyHeldEdit(m) {
    const held = this.db.all(
      "SELECT content, deleted, edited_at, gateway_id FROM edits WHERE message_id = ? AND channel_id = ''", m.id)[0]
    if (!held) return
    if (held.gateway_id !== m.gateway_id) {
      this.db.all('DELETE FROM edits WHERE message_id = ?', m.id)
      return
    }
    const data = { ...m, content: held.content, edited_at: held.edited_at, deleted: held.deleted ? 1 : 0 }
    this.db.all('UPDATE messages SET data = ? WHERE id = ?', JSON.stringify(data), m.id)
    this.db.all(
      'INSERT OR REPLACE INTO edits(message_id, channel_id, content, deleted, edited_at, gateway_id) VALUES (?, ?, ?, ?, ?, ?)',
      m.id, m.channel_id, held.content, held.deleted, held.edited_at, held.gateway_id)
  }

  applyEdit(e, sender, cache) {
    if (!e || typeof e !== 'object') return 0
    const messageId = str(e.message_id, 64)
    const gid = str(e.gateway_id, 64).trim()
    const editedAt = str(e.edited_at, 40)
    const deleted = e.deleted ? 1 : 0
    const content = deleted ? '' : String(e.content ?? '')
    const at = stamp(editedAt)
    if (!messageId || !ID_RE.test(gid) || at === null) return 0
    if (!deleted && (!content.trim() || content.length > MAX_CONTENT)) return 0
    const held = this.db.all('SELECT edited_at FROM edits WHERE message_id = ?', messageId)[0]
    if (held && (stamp(held.edited_at) ?? 0) >= at) return 0
    const msg = this.db.all('SELECT channel_id, gateway_id, data FROM messages WHERE id = ?', messageId)[0]
    if (msg && msg.gateway_id !== gid) return -1 // someone else's message: not theirs to change
    if (msg && !(this.allowed(msg.channel_id, sender, cache) && this.allowed(msg.channel_id, gid, cache))) return -1
    this.db.all(
      'INSERT OR REPLACE INTO edits(message_id, channel_id, content, deleted, edited_at, gateway_id) VALUES (?, ?, ?, ?, ?, ?)',
      messageId, msg ? msg.channel_id : '', content, deleted, editedAt, gid)
    if (msg) {
      const data = { ...parseJson(msg.data, {}), content, edited_at: editedAt, deleted }
      this.db.all('UPDATE messages SET data = ? WHERE id = ?', JSON.stringify(data), messageId)
    }
    return 1
  }

  applyReaction(r, sender, cache) {
    if (!r || typeof r !== 'object' || !isReactionEmoji(r.emoji)) return 0
    const messageId = str(r.message_id, 64)
    const gid = str(r.gateway_id, 64).trim() || sender
    if (!messageId || !ID_RE.test(gid)) return 0
    const msg = this.db.all('SELECT channel_id FROM messages WHERE id = ?', messageId)[0]
    const channelId = msg ? msg.channel_id : str(r.channel_id, 200)
    if (!channelId) return 0
    if (!(this.allowed(channelId, sender, cache) && this.allowed(channelId, gid, cache))) return -1
    const createdAt = stamp(r.created_at) === null ? new Date(this.now()).toISOString() : str(r.created_at, 40)
    const id = `${messageId}|${r.emoji}|${gid}`.slice(0, 200)
    const existing = this.db.all('SELECT created_at, active FROM reactions WHERE id = ?', id)[0]
    const active = r.active ? 1 : 0
    if (existing) {
      const ours = stamp(existing.created_at) ?? 0
      const theirs = stamp(createdAt) ?? 0
      if (ours > theirs) return 0 // newest wins, whatever order rows arrive in
      if (ours === theirs && existing.active === active) return 0 // the same row again
    }
    this.db.all(
      'INSERT OR REPLACE INTO reactions(id, message_id, channel_id, emoji, gateway_id, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
      id, messageId, channelId, r.emoji, gid, active, createdAt)
    return 1
  }

  recordPresence(sender, body) {
    const now = this.now()
    const row = this.db.all('SELECT status, status_at, typing, typing_at FROM members WHERE gateway_id = ?', sender)[0]
    const raw = body.status && typeof body.status === 'object' ? body.status : null
    const phrase = raw ? String(raw.phrase ?? '').trim().toLowerCase() : ''
    const status = STATUS_PHRASES.includes(phrase) ? JSON.stringify({ phrase, agent: cleanName(raw.agent, '') }) : ''
    if (status !== row.status) this.bump()
    const typing = (Array.isArray(body.typing) ? body.typing : [])
      .filter(c => typeof c === 'string' && c).slice(0, 4).map(c => c.slice(0, 200))
    const typingJson = typing.length ? JSON.stringify(typing) : ''
    // While someone keeps typing their Hermes Multiplayer re-sends it every few seconds: pass that on often enough that the
    // others' indicator does not lapse, without waking them for every keystroke.
    if (typingJson !== row.typing || (typingJson && now - row.typing_at >= 3000)) this.bump()
    this.db.all('UPDATE members SET status = ?, status_at = ?, typing = ?, typing_at = ? WHERE gateway_id = ?',
      status, status ? now : 0, typingJson, typingJson ? now : 0, sender)
  }

  roster(viewer, cache) {
    const now = this.now()
    return this.db.all('SELECT * FROM members ORDER BY name COLLATE NOCASE LIMIT ?', MAX_MEMBERS).map(m => {
      const status = m.status && now - m.status_at < STATUS_TTL_MS ? parseJson(m.status, null) : null
      const typing = m.typing && now - m.typing_at < TYPING_TTL_MS
        ? parseJson(m.typing, []).filter(c => this.allowed(c, viewer, cache)) : []
      return { gateway_id: m.gateway_id, display_name: m.name, online: now - m.last_seen < ONLINE_MS, status, typing }
    })
  }

  export(viewer, afterSeq, afterRseq, afterEseq, cache) {
    const limit = BATCH_LIMIT
    const examined = this.db.all(
      'SELECT seq, channel_id, gateway_id, history, data FROM messages WHERE seq > ? ORDER BY seq LIMIT ?', afterSeq, limit)
    const rexamined = this.db.all(
      'SELECT rseq, id, message_id, channel_id, emoji, gateway_id, active, created_at FROM reactions WHERE rseq > ? ORDER BY rseq LIMIT ?',
      afterRseq, limit)
    const eexamined = this.db.all(
      'SELECT eseq, message_id, channel_id, content, deleted, edited_at, gateway_id FROM edits WHERE eseq > ? ORDER BY eseq LIMIT ?',
      afterEseq, limit)
    // A cursor moves past rows the viewer wrote (it has them) and rows it may not see (it never gets them).
    const mine = row => row.gateway_id === viewer
    const messages = examined.filter(r => !mine(r) && this.allowed(r.channel_id, viewer, cache)).map(r => {
      const data = parseJson(r.data, null)
      return data && r.history ? { ...data, history: true } : data
    }).filter(Boolean)
    const reactions = rexamined.filter(r => !mine(r) && this.allowed(r.channel_id, viewer, cache))
    const edits = eexamined.filter(r => r.channel_id && !mine(r) && this.allowed(r.channel_id, viewer, cache))
    const channels = this.db.all('SELECT * FROM channels ORDER BY id LIMIT 1000')
      .filter(c => this.allowed(c.id, viewer, cache))
      .map(c => ({ ...c, is_dm: Boolean(c.is_dm), members: parseJson(c.members, []) }))
    return {
      channels, messages, next_seq: examined.length ? examined[examined.length - 1].seq : afterSeq,
      more: examined.length >= limit, reactions,
      next_rseq: rexamined.length ? rexamined[rexamined.length - 1].rseq : afterRseq, rmore: rexamined.length >= limit,
      edits, next_eseq: eexamined.length ? eexamined[eexamined.length - 1].eseq : afterEseq,
      emore: eexamined.length >= limit,
    }
  }

  /** POST /hermes-multiplayer/v1/sync. Returns `{status, body}`. The caller has already checked the room key. */
  async sync(body) {
    if (!body || typeof body !== 'object' || Array.isArray(body)) return fail(422, 'Body must be a JSON object.')
    const from = body.from && typeof body.from === 'object' ? body.from : {}
    const sender = String(from.gateway_id ?? '').trim()
    const admitted = await this.admit(sender, from.display_name, from.token, true)
    if (admitted !== 200) return fail(admitted, ADMIT_ERRORS[admitted] || 'Not allowed.')
    const cache = new Map()
    let accepted = 0
    let dropped = 0
    this.recordPresence(sender, body)
    for (const ch of (Array.isArray(body.channels) ? body.channels : []).slice(0, BATCH_LIMIT)) this.upsertChannel(ch, sender)
    const history = body.first_contact === true ? 1 : 0
    for (const raw of (Array.isArray(body.messages) ? body.messages : []).slice(0, BATCH_LIMIT)) {
      const m = this.validMessage(raw, sender)
      if (!m) continue
      if (!(this.allowed(m.channel_id, sender, cache) && this.allowed(m.channel_id, m.gateway_id, cache))) {
        dropped += 1
        continue
      }
      if (this.db.all('SELECT 1 AS x FROM messages WHERE id = ?', m.id)[0]) continue
      this.db.all('INSERT INTO messages(id, channel_id, gateway_id, history, data) VALUES (?, ?, ?, ?, ?)',
        m.id, m.channel_id, m.gateway_id, history, JSON.stringify(m))
      this.applyHeldEdit(m)
      accepted += 1
      this.dirty = true
    }
    for (const raw of (Array.isArray(body.reactions) ? body.reactions : []).slice(0, BATCH_LIMIT)) {
      const result = this.applyReaction(raw, sender, cache)
      if (result > 0) this.dirty = true
      if (result < 0) dropped += 1
    }
    for (const raw of (Array.isArray(body.edits) ? body.edits : []).slice(0, BATCH_LIMIT)) {
      const result = this.applyEdit(raw, sender, cache)
      if (result > 0) this.dirty = true
      if (result < 0) dropped += 1
    }
    const out = this.export(sender, cursor(body.after_seq), cursor(body.after_rseq), cursor(body.after_eseq), cache)
    const response = {
      v: PROTOCOL_VERSION,
      from: { gateway_id: `relay-${this.roomId.toLowerCase()}`.slice(0, 64), display_name: 'Team room', relay: true },
      accepted, dropped, ...out, participants: this.roster(sender, cache), ev: this.ev,
    }
    this.flush()
    return { status: 200, body: response }
  }

  /** Has anything changed for this member since the cursors it holds? Also counts as being seen. */
  async waitState(query, token) {
    const gateway = String(query.gateway ?? '')
    const admitted = await this.admit(gateway, undefined, token, false)
    if (admitted !== 200) return fail(admitted, ADMIT_ERRORS[admitted] || 'Not allowed.')
    this.flush()
    const top = name => this.db.all(`SELECT COALESCE(MAX(${name}), 0) AS n FROM ${TABLE_OF[name]}`)[0].n
    const changed = top('seq') > cursor(query.after_seq) || top('rseq') > cursor(query.after_rseq) ||
      top('eseq') > cursor(query.after_eseq) || this.ev !== cursor(query.ev)
    const others = this.db.all(
      'SELECT COUNT(*) AS n FROM members WHERE gateway_id != ? AND last_seen > ?', gateway, this.now() - ONLINE_MS)[0].n
    return { status: 200, body: { changed, alone: others === 0, ev: this.ev } }
  }

  /** GET /hermes-multiplayer/v1/wait: answer at once when there is news (or nobody else is here), else hold for a while. */
  async wait(query, token, holdMs = WAIT_HOLD_MS) {
    const first = await this.waitState(query, token)
    if (first.status !== 200 || first.body.changed || first.body.alone) return first
    await this.hub.wait(holdMs)
    const second = await this.waitState(query, token)
    if (second.status === 200) second.body.alone = false
    return second
  }
}

const TABLE_OF = { seq: 'messages', rseq: 'reactions', eseq: 'edits' }
const ADMIT_ERRORS = {
  401: 'This Hermes Multiplayer did not say who it is. Update Hermes Multiplayer and join the room again.',
  403: 'This room already knows that Hermes Multiplayer id with a different token.',
  422: 'from.gateway_id is missing or malformed.',
  429: 'This room is full.',
}
const fail = (status, message) => ({ status, body: { error: message } })

/** Parse `/r/<room>/hermes-multiplayer/v1/<action>`; null when the path is something else. */
export function route(pathname) {
  const match = /^\/r\/([A-Za-z0-9_-]{8,64})\/(?:hermes-multiplayer|herd)\/v1\/(sync|wait)$/.exec(pathname)
  return match ? { roomId: match[1], action: match[2] } : null
}

export function bearer(header) {
  const [scheme, token] = String(header || '').trim().split(/\s+/, 2)
  return scheme && scheme.toLowerCase() === 'bearer' && token ? token : ''
}
