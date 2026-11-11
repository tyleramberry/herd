#!/usr/bin/env node
// Hermes Multiplayer team room as a plain node server: the same room logic as the Cloudflare Worker (src/core.js), for
// running a relay on your own machine or server, and for tests. Needs node 22.5+ (built-in node:sqlite).
//
//   node relay/server.mjs --port 8787 --data ./rooms      (one SQLite file per room; omit --data for memory only)
//
// Put it behind https (a tunnel or a reverse proxy) before sharing a room link: Hermes Multiplayer refuses plain http off
// this machine.
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { MAX_BODY_BYTES, Room, bearer, route, validKey } from './src/core.js'

function arg(name, fallback) {
  const at = process.argv.indexOf(`--${name}`)
  return at > 0 && process.argv[at + 1] ? process.argv[at + 1] : fallback
}

export function createRelay({ dataDir = '', holdMs } = {}) {
  const rooms = new Map()
  if (dataDir) fs.mkdirSync(dataDir, { recursive: true })

  function open(roomId) {
    let room = rooms.get(roomId)
    if (!room) {
      const sqlite = new DatabaseSync(dataDir ? path.join(dataDir, `${roomId}.db`) : ':memory:')
      const db = {
        all(query, ...params) {
          const statement = sqlite.prepare(query)
          return /^\s*(SELECT|PRAGMA)/i.test(query) ? statement.all(...params) : (statement.run(...params), [])
        },
      }
      room = new Room(db, roomId)
      rooms.set(roomId, room)
    }
    return room
  }

  const send = (res, status, body) => {
    const data = JSON.stringify(body)
    res.writeHead(status, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data), 'Cache-Control': 'no-store' })
    res.end(data)
  }

  async function handle(req, res) {
    const url = new URL(req.url, 'http://relay.local')
    if (url.pathname === '/' || url.pathname === '/health') return send(res, 200, { ok: true, service: 'herd-relay' })
    const target = route(url.pathname)
    if (!target) return send(res, 404, { error: 'Not a Hermes Multiplayer relay path.' })
    const key = bearer(req.headers.authorization)
    if (!validKey(key)) return send(res, 401, { error: 'Missing or malformed room key.' })
    if (target.action === 'wait') {
      if (req.method !== 'GET') return send(res, 405, { error: 'Use GET.' })
      const exists = dataDir ? fs.existsSync(path.join(dataDir, `${target.roomId}.db`)) : rooms.has(target.roomId)
      if (!exists) return send(res, 401, { error: 'Wrong key for this room.' })
      const room = open(target.roomId)
      if (!room.meta('key_hash') || !(await room.authorize(key))) return send(res, 401, { error: 'Wrong key for this room.' })
      const out = await room.wait(Object.fromEntries(url.searchParams), String(req.headers['x-herd-member'] || ''), holdMs)
      return send(res, out.status, out.body)
    }
    if (req.method !== 'POST') return send(res, 405, { error: 'Use POST.' })
    const chunks = []
    let size = 0
    for await (const chunk of req) {
      size += chunk.length
      if (size > MAX_BODY_BYTES) return send(res, 413, { error: 'Batch too large.' })
      chunks.push(chunk)
    }
    let body
    try {
      body = JSON.parse(Buffer.concat(chunks).toString('utf8'))
    } catch {
      return send(res, 422, { error: 'Body must be JSON.' })
    }
    const room = open(target.roomId)
    if (!(await room.authorize(key))) return send(res, 401, { error: 'Wrong key for this room.' })
    const out = await room.sync(body)
    return send(res, out.status, out.body)
  }

  return http.createServer((req, res) => {
    handle(req, res).catch(() => {
      if (!res.headersSent) send(res, 500, { error: 'Relay error.' })
    })
  })
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const port = Number(arg('port', process.env.PORT || 8787))
  const host = arg('host', '127.0.0.1')
  const hold = arg('hold-ms', '')
  createRelay({ dataDir: arg('data', ''), holdMs: hold ? Number(hold) : undefined }).listen(port, host, function () {
    console.log(`herd-relay listening on http://${host}:${this.address().port}`)
  })
}
