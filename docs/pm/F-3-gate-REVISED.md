# F-3 — REPLACES the Nov 8 code freeze (Tyler's directive, Sat Nov 7)

**Tyler's directive, verbatim intent:** he does not care about the Nov 8 code cutoff and will ship
until the last minute of the competition (Nov 11, 5:00 PM EST) to win. The Nov 8 freeze is CANCELLED.

## The rules that replace it

1. **No freeze date. The only deadline is Nov 11, 5:00 PM EST.**
2. **The QA gate is not cancelled — it is the only thing that still blocks a merge.** Nothing reaches
   `main` or the catalog pin without Sentry verifying it at the head. Volume goes up; verification does not go down.
3. **Ship continuously.** Merges are expected right up to the deadline. Cut nothing for schedule reasons
   while it can still be finished and verified.
4. **The one hard ordering constraint is the catalog PR review window**, not our build: the entry pins a
   40-hex SHA, and maintainers review the pinned tree. Therefore:
   - Open the catalog PR as soon as H-2 is pin-ready (do not wait) so review starts early.
   - Every later improvement goes in as a **SHA-bump PR** (catalog rule 4) — normal, expected, re-reviewed.
   - **Last pin bump: Nov 10, 6:00 PM MST** so the final tree is reviewed and green before the form deadline.
5. **The entry form is submitted by Nov 10 EOD**, with the video link. Both links (PR + video) must be
   live in the form. The form is the submission; a perfect repo submitted late scores zero.
6. **Demo video can be re-recorded** any time up to Nov 10 if a later feature makes a better 90 seconds.

## What still stops a ship

- A QA round that has not passed (no S1/S2 open on the path being shipped).
- The B1-class rules: credentials, core overrides, desktop-surface, disclosures. Non-negotiable, always.
- Anything that breaks the two-gateway SPINE. It is the product.

## Tyler's remaining gates

| When | What he decides |
|---|---|
| When H-2 is pin-ready | Approve opening the catalog PR (one screen: what is being submitted, the pin, the disclosures) |
| Anytime before Nov 10 | Approve the demo video cut |
| Nov 10 EOD | Form submission is sent; he is informed, not asked |
