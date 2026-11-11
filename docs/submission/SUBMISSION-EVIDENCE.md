# Submission evidence — Hermes Multiplayer (Hackathon entry, Nov 2026)

Verified by @herald · Final check **Nov 11, 2026, 14:52 MST** (deadline 17:00 EST / 15:00 MST).

## The three gates

| Gate | Status | Artifact |
|---|---|---|
| 1. Catalog PR | ✅ open | https://github.com/NousResearch/hermes-agent/pull/153148 |
| 2. Demo video on X, tagged @NousResearch | ✅ live | https://x.com/tyler_amberry/status/2120617127568961879 |
| 3. Entry form, both links | ✅ submitted by Tyler | https://form.typeform.com/to/FwJLvOln |

## 1. Catalog PR — verified details

- **One file:** `plugin-catalog/hermes-multiplayer.yaml` (+19/−0), `mergeable: MERGEABLE`
- **Pin:** `a60c87a31515b36f3ef4054ed54634247b91be7d` — commit exists in
  `tyleramberry/hermes-multiplayer` (committed 2026-11-11T17:15:32Z), full 40-hex, `version: "0.1.0"` quoted
- **Entry == repo file:** the PR branch's entry is byte-identical (comments ignored) to
  `docs/submission/plugin-catalog-hermes-multiplayer.yaml`
- **Capabilities:** `multiplayer_list_channels`, `multiplayer_post`, `multiplayer_read_channel`,
  `multiplayer_set_status` — no hooks, no middleware, no `requires_env`
- **`requires_hermes`:** `">=0.22.0"`, same floor as `plugin.yaml`
- **Disclosures:** the PR body carries the full rule-13 list (relay team room + author-run Cloudflare
  Worker, direct-link egress, inbound `/sync` `/ping` `/pair`, background sync loop, credential paths,
  read-only Kanban title lookup, no shell commands, no self-updater)
- **Screenshots:** `docs/media/agent-answer.png`, `channel-agent-thread.png`, `dm.png`
- **Known external gate:** PR checks show *"no checks reported"* — a first-time-contributor workflow
  approval that only a Nous maintainer can start. The PR itself is mergeable and the entry is valid.

## 2. Demo video on X — verified details

- Post: **1/** `Hermes agent is finally multiplayer!` — tagged **@NousResearch** (and @Teknium), part of a
  3-post thread; links the install page, the repo and the catalog PR
- **Media attached:** verified from the live tweet payload — `mediaDetails[0].type = video`, duration
  **84,171 ms = 84.2 s**, under the 90-second cap
- Same video on Loom: https://www.loom.com/share/dce03f6beb6f49f49dba0029629c11d9 (1:24)

## 3. Entry form

- Submitted by **Tyler** in-session on Nov 11 with both links (PR + X post).
- **Outstanding artifact:** the form confirmation screenshot (the submission receipt) — capture it into
  this file or the H-4 card as the last piece of proof.

## Post-submission watch items

1. If a Nous maintainer starts catalog CI and it fails, fix at the **same pin** (or bump the pin —
   last bump allowance was Nov 10 18:00 MST, already passed; a fix now is a new PR/commit, not a re-pin).
2. Keep the X post up and the PR open until judging concludes.
