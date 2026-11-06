# F-3 — Nov 8 code-freeze approval gate (Tyler)

Foreman fills the **Evidence** column on Nov 8. Tyler signs off only when every row is ✅ or
explicitly waived. After sign-off, Herald opens the catalog PR (H-3) pinned to the approved SHA.

## A. Build is real
| # | Check | Evidence | ✅ |
|---|---|---|---|
| A1 | All feature PRs merged to `main`; freeze SHA recorded (`git rev-parse origin/main`, 40 hex) | | |
| A2 | `pytest tests/ -q` green at freeze SHA | | |
| A3 | `node --check desktop/plugin.js` passes | | |
| A4 | `hermes plugins validate .` clean | | |
| A5 | `hermes plugins doctor . --ci` clean | | |
| A6 | SPINE demonstrated: message on gateway A appears on gateway B (Q-1 TC-2.1/2.2 signed by Sentry) | Q-9 PASSED Nov 6 on two real Macs (Tyler first-hand; card t_4e0473ee). Written artifact owed: `docs/qa/Q9-SPINE-RUNLOG.md` (Q-10, due Nov 7). Fill ✅ at freeze. | |

## B. Scope (N-1 cut-list)
| # | Check | Evidence | ✅ |
|---|---|---|---|
| B1 | Channels, DMs, agent posting, 2-gateway fan-out all work | | |
| B2 | Nothing from the post-hackathon backlog snuck in | | |

## C. Catalog rules (Sentry Q-3)
| # | Check | Evidence | ✅ |
|---|---|---|---|
| C1 | No `os.environ` / `getenv` in the Python half (rule 11); `gateway_id` via `config_schema` | | |
| C2 | `plugin.yaml` has `requires_hermes`, matching `herd.yaml` exactly (rule 14) | | |
| C3 | `herd.yaml` capabilities match what the freeze SHA actually registers (rule 6) | | |
| C4 | `version` quoted in `herd.yaml` and equal to `plugin.yaml` | | |
| C5 | Rule-13 disclosures true at freeze SHA, incl. peer-sync network egress once S-2 lands | | |
| C6 | Desktop plugin uses SDK only; no core-UI patching | | |
| C7 | Security scan clean; no secrets committed | | |

## D. Submission readiness (Herald)
| # | Check | Evidence | ✅ |
|---|---|---|---|
| D1 | `herd.yaml` `sha:` = freeze SHA (not the placeholder) | | |
| D2 | Screenshots pinned to freeze SHA URLs | | |
| D3 | Demo script final, ≤90s, swappable constants filled, real key masked | | |
| D4 | Recording slot booked for Nov 8 with both instances | | |
| D5 | README install + `hermes peer add` instructions match shipped behaviour | | |

## E. Judging criteria spot-check (Foreman)
| # | Check | Notes |
|---|---|---|
| E1 | Hook lands in first 10s (join flow) | |
| E2 | Payoff is visible: two agents + two humans in one channel | |
| E3 | Clear "why multiplayer Hermes" in description | |

## Sign-off
- Freeze SHA: `________________________________________`
- Tyler: ☐ Approved ☐ Approved with waivers: ________ ☐ Not approved (reason): ________
- Date/time:
