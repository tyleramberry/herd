// Hermes Multiplayer team room on Cloudflare: one Durable Object per room, with its own SQLite database.
import { DurableObject } from 'cloudflare:workers'
import { MAX_BODY_BYTES, Room, bearer, route, validKey } from './core.js'

const json = (status, body) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } })

export class MultiplayerRoom extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env)
    const sql = ctx.storage.sql
    this.db = { all: (query, ...params) => sql.exec(query, ...params).toArray() }
    this.room = null
  }

  open(roomId) {
    if (!this.room) this.room = new Room(this.db, roomId)
    return this.room
  }

  async sync(roomId, key, body) {
    const room = this.open(roomId)
    if (!(await room.authorize(key))) return { status: 401, body: { error: 'Wrong key for this room.' } }
    return room.sync(body)
  }

  async wait(roomId, key, token, query) {
    const room = this.open(roomId)
    // A wait never creates a room: only a sync does.
    if (!room.meta('key_hash') || !(await room.authorize(key))) return { status: 401, body: { error: 'Wrong key for this room.' } }
    return room.wait(query, token)
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    if (url.pathname === '/' || url.pathname === '/health') return json(200, { ok: true, service: 'hermes-multiplayer-relay' })
    const target = route(url.pathname)
    if (!target) return json(404, { error: 'Not a Hermes Multiplayer relay path.' })
    const key = bearer(request.headers.get('Authorization'))
    if (!validKey(key)) return json(401, { error: 'Missing or malformed room key.' })
    const stub = env.ROOMS.get(env.ROOMS.idFromName(target.roomId))
    if (target.action === 'wait') {
      if (request.method !== 'GET') return json(405, { error: 'Use GET.' })
      const out = await stub.wait(target.roomId, key, request.headers.get('X-Multiplayer-Member') || request.headers.get('X-Herd-Member') || '',
        Object.fromEntries(url.searchParams))
      return json(out.status, out.body)
    }
    if (request.method !== 'POST') return json(405, { error: 'Use POST.' })
    if (Number(request.headers.get('Content-Length') || 0) > MAX_BODY_BYTES) return json(413, { error: 'Batch too large.' })
    const text = await request.text()
    if (text.length > MAX_BODY_BYTES) return json(413, { error: 'Batch too large.' })
    let body
    try {
      body = JSON.parse(text)
    } catch {
      return json(422, { error: 'Body must be JSON.' })
    }
    const out = await stub.sync(target.roomId, key, body)
    return json(out.status, out.body)
  },
}
