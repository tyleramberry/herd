# N-1 — Herd Locked Cut-LIST (Nov 4, by Foreman per fallback)

**SHIPS IN THE HACKATHON ENTRY (nothing else):**

1. **Shared channels** — create/list channels; messages persist per channel; `#general` seeded.
2. **DMs** — direct human↔human messages, private, separate from channels.
3. **Human → agent posting** — agents receive channel messages and can act on them (agent-side tools `herd_post`, `herd_list_channels` registered via plugin.yaml).
4. **Two-gateway fan-out (the SPINE)** — message posted on gateway A appears in the channel view on gateway B without manual reload, and reverse; client-UUID convergence, no duplicates.
5. **One-command join** — co-founder connects via `hermes peer add`; the pane reflects the peer with no config dance.
6. **Native desktop UX** — `/herd` route + pane using the app's UI kit; empty states; composer; React Query with polling fallback.

**HARD EXCLUSIONS (post-hackathon backlog — reject any PR containing them):**
Threads · reactions · file/attachment sharing · presence indicators · voice · channel permissions/roles · message search · >2 gateways · message editing/deletion · read receipts · typing indicators · notification preferences · MySI integration.

**Scope-creep yardstick:** any task or PR not serving items 1–6 gets rejected with a pointer here. Judging is usefulness/reliability/polish/creativity — a polished subset of 1–6 wins over a buggy everything.
