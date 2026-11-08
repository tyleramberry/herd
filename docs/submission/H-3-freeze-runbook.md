# H-3 / H-4 — Freeze-day + submission-day runbook

Owner: @herald · Created Nov 7 · Executes Sun **Nov 8** (freeze + record) → Tue **Nov 10** (post + form).
Gate: **nothing opens or posts until Foreman review + Tyler sign-off (Nov 8).**

## A. Freeze-day pin procedure (~2 minutes, mechanical)
1. `cd ~/herd && git fetch origin && git rev-parse origin/main` → **the pin** (40 hex) — the frozen
   `origin/main` after PR #56 (SEC-1 + S-24) merges. Record it here: `__________`
2. Confirm the tree at that SHA still carries the fixes the package assumes:
   `git show <SHA>:dashboard/herd_store.py | grep -c '_NoRedirect'` → expect `2`
   `git show <SHA>:plugin.yaml | grep -c 'herd_set_status'` → expect `1`
   `git show <SHA>:README.md | grep -ci 'doesn't do (yet)'` and confirm "reactions" is absent from that line
2b. Confirm the **SEC-1 (S-19…S-23) controls** are in the pinned tree (folded in by card H-7; counts are
    at the Nov 7 SEC-1 head — if the tree moved, read them as *present / absent*):
   `git show <SHA>:__init__.py | grep -c 'inbound_authorized'` → expect non-zero (peer routes check **this gateway's Herd secret**)
   `git show <SHA>:dashboard/herd_store.py | grep -c 'compare_digest'` → expect non-zero (constant-time secret compare)
   `git show <SHA>:__init__.py | grep -c '_check_auth'` → expect `0` (the gateway API-key check is **gone**; `API_SERVER_KEY` not accepted on `/herd/v1/*`)
   `git show <SHA>:dashboard/herd_store.py | grep -c '_peer_url_refusal'` → expect non-zero (cleartext policy checked **before** the request is built)
   `git show <SHA>:dashboard/herd_store.py | grep -c 'CLEARTEXT_REFUSED'` → expect non-zero (off-loopback `http://` refused by default)
   `git show <SHA>:dashboard/herd_store.py | grep -c '_bound_gateway_id'` → expect non-zero (synced-row identity bound to the declared sender)
   `git show <SHA>:dashboard/herd_store.py | grep -c '_dm_export_allowed'` → expect non-zero (DM export is members-only)
   `git show <SHA>:plugin.yaml | grep -c 'e\.g\. http://'` → expect `0` (the settings copy ships **no** `http://` example)
   `git show <SHA>:plugin.yaml | grep -c 'e\.g\. https://'` → expect `1` (the `peer_url` example is `https://`)
3. Re-run both gates **at that SHA**:
   `hermes plugins validate <checkout> --install-deps` → expect `Validation passed.`
   `python3 scripts/qa/catalog_audit.py <checkout> --entry herd.yaml` → expect `0 FAIL, 0 WARN` and **4** tools
4. Swap `sha:` in `docs/submission/H-2-catalog-pr-package.md` → the freeze SHA. Re-pin the `image:`/`screenshots:` URLs to the same SHA **only if** the files exist at it (§B).
5. Tick the checklist items that are now true; leave the PR unopened.

## B. Media decision (rule-safe)
- `docs/media/` is **empty** on main (audit WARN 5). A `screenshots:`/`image:` URL that 404s at the pin is a broken gallery.
- **Default: ship the entry WITHOUT `image:` and `screenshots:`.** Cosmetic fields are not worth a broken page.
- **Optional upgrade:** during the Nov 8 recording session capture the three real stills — (1) Add-teammate form with the key masked, (2) both Macs showing the same `#general`, (3) the agent handoff with `agent` pills. Commit them to `docs/media/` **in a commit that is part of the freeze SHA** (i.e. before `rev-parse`), then enable the fields and pin them to that SHA. Post-freeze captures belong in the PR body only.

## C. H-3 — open the catalog PR (post-sign-off)
1. Fork/branch `NousResearch/hermes-agent`; add **one** file: `plugin-catalog/herd.yaml` (exact contents from H-2 §1).
2. PR description: H-2 §2 — what it does, "What Herd adds over core" line (N-3), surfaces used, and every rule-13 line that is true at the pin (incl. the settled redirect wording and the S-15 status line verbatim).
3. Attach screenshots in the PR body (works even if the entry omits the fields).
4. Wait for catalog CI green; then a maintainer reviews the pinned tree.
5. Record the PR URL here: `__________` — this is link #1 for the entry form.

## D. Record the demo (Nov 8, same day)
- Script: `docs/submission/H-1-demo-script.md` (v9). **Prereq:** rig updated to the freeze build — the old two-Mac window ran 28 commits behind and does not count as evidence (shots 3–5 re-verified there).
- Rehearse with @sentry first; full dry run ≤85s.
- Record shot 5 both ways (mention take = primary, baseline = fallback) and the shot 5A reaction beat.
- Publish the video (needs a public URL for the form) and record it here: `__________` — link #2.

## E. H-4 — submission day (Nov 10; hard deadline Nov 11 17:00 EST)
1. Post to X, tagged **@NousResearch**, using H-1's copy; verify the tag renders in the live post and record the post URL: `__________`
2. Submit the entry form with **both** links (catalog PR + video).
3. Screenshot the form confirmation; report the confirmation + all three URLs to Foreman as proof.
4. Re-check the PR is still green and the video URL still plays **before** submission — a dead link at 17:00 EST is unrecoverable.

## F. Evidence to hand Foreman at each gate
| Gate | Artifact |
|---|---|
| Freeze | freeze SHA · validate output · catalog_audit output |
| H-3 | catalog PR URL · CI run link |
| Record | video URL · takes recorded (5-mention / 5-baseline / 5A) |
| H-4 | X post URL · form confirmation screenshot |
