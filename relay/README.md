# Hermes Multiplayer relay (team room)

One small server that holds a team's Hermes Multiplayer messages, so teammates join with one link and never need to reach each other's computers.

- **Cloudflare (recommended, free plan works):** `npm install && npx wrangler deploy`. One Durable Object with its own SQLite database per room.
- **Your own machine:** `node server.mjs --port 8787 --data ./rooms` (node 22.5+). Put it behind https before sharing a link.
- **Tests:** `npm test` here, and `tests/test_room.py` in the repo root runs real Hermes Multiplayer stores against this server.

A room is created by the first Hermes Multiplayer that reaches it and belongs to the key in its link (`https://<relay>/r/<room>#<key>`). The relay stores only a hash of the key. Each member also registers its own token on first contact; the relay refuses that member id with any other token.

Cost note: Hermes Multiplayer keeps one request open per member while others are online. On the free plan that fits about one busy room; a paid Workers plan covers many.
