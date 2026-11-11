# AIOPS2 differential audit — Runs visibility, 2026-11-11 14:16 CET

Scope: source-only functional upgrade audit; no runtime, tenant ACL, HITL or deployment changes.

## Evidence and provenance
- `main:app/portal/portal_bootstrap_client.js`, blob `ac58f73c725f5e088081bffed4478ea18585ef5c`, inspected through GitHub.
- `validEnvelope` permits at most 100 Runs and requires qualified tenant ACL and server-derived actor, while `show` renders only `data.runs.items.slice(0, 15)`.
- The first 15 entries have no explicit sort, criticality or pagination guarantee in this client. This is a **source-confirmed visibility limitation**, not a proven runtime regression.
- Prior #612 SHA `234800da97da84adc6be65d32569e71f4a7c82d8`: GitHub Actions run 43018460718 completed SUCCESS (CI only, not E2E).

## Before/after matrix (UNKNOWN means not measured, not absent)
| Capability | Main source contract | v28/V145 | Active :7777 | Candidate :17778 | Risk |
|---|---|---|---|---|---|
| Dashboard / Core / Twin | tenant/actor qualified read, UNKNOWN or READABLE_UNVERIFIED | UNKNOWN | UNKNOWN | UNKNOWN | P0 forged tenant disclosure |
| Runs | <=100 accepted, first 15 rendered; no pagination indication in this JS | UNKNOWN | UNKNOWN | UNKNOWN | P1 hidden critical run |
| NOC / Evidence | no LIVE attestation derivable from bootstrap | UNKNOWN | UNKNOWN | UNKNOWN | P0 false healthy |
| GLPI / Copilot | separate authorization contracts | UNKNOWN | UNKNOWN | UNKNOWN | P0 unauthorized read/action |
| Navigation / DemoCenter | not evaluated by this source-only inspection | UNKNOWN | UNKNOWN | UNKNOWN | P1 broken link or lost capability |

## Isolated negative / non-regression acceptance recipe
Use a simulated DOM and stubbed fetch, no real credentials or upstream calls.
1. Supply a syntactically valid, tenant-qualified `aiops.portal.readmodels.v1` fixture with 17 Runs; place `run-crit-016` (status FAILED/P0) in position 16, and `run-crit-017` in 17. Assert the critical Run is discoverable via an explicit truncation indicator and accessible pagination/search, **or fail the acceptance test**. Existing `slice(0,15)` predicts failure unless a separate UI control exists; do not assert that it already exists.
2. Supply 101 Runs: reject the entire invalid envelope, display UNKNOWN, do not render any Run.
3. Supply HTTP 200 with `tenant_acl_qualified=false` or `actor_identity_server_derived=false`: reject, no metrics or Runs displayed, no token persistence.
4. Trigger a second request / clear before the first response JSON resolves: stale response must never overwrite UNKNOWN.
5. Supply NOC/Evidence/Grafana HTTP 200 without independently verified provenance: never promote to LIVE/healthy.
Record test command, exit code, fixture SHA, screenshots/DOM assertions and source/candidate image digest separately. No claims of passing tests until executed.

## Decision and rollback
P1 candidate improvement: show '15 of N Runs' and a clearly labelled route to authorized complete results, preserving tenant scope; do not introduce an unqualified API or bypass HITL. Hold upgrade acceptance if a critical Run is hidden without an approved visibility contract.
Rollback this documentation-only increment by closing its Draft PR or reverting its branch-only commit(s); no main merge, Docker, cron, Debian, secrets, PG/GLPI or other stacks changes.
#557 is rootful/rootless diagnostic mismatch, operator-confirmed UID 1001, rootless socket /run/user/1001/docker.sock, 87 containers/210 images at time of evidence. Current host freshness UNKNOWN; E2E NOT VERIFIED.
