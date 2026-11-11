# AIOPS2 — differential acceptance X-021: cross-panel atomicity
Date: 2026-11-11 21:07 Europe/Paris. GitHub source only; no host access.

## Verified source and CI
Source: `app/portal/portal_bootstrap_client.js` on main, blob `ac58f73c725f5e088081bffed4478ea18585ef5c`.
Prior PR #650 SHA `3d8b5d18c041b2f0432fe1db1ff4425ab06f4586`: Actions run 43084511146 concluded **success**. This does NOT execute X-021 and does not establish E2E.
The `show()` function mutates dashboard metric nodes before it renders Runs. It then clears and appends Run rows individually, and updates Twin and states only after Runs. A coercion exception in a later Run field can leave **dashboard updated, Runs partial, Twin/states stale, and global result UNKNOWN**. This is a source-derived risk, not a proven runtime regression.

## Differential matrix
| Function | Source before | Candidate acceptance | v28/V145 / deployed |
|---|---|---|---|
| Dashboard | Metrics written before Run validation | No cross-panel partial update on malformed payload | UNKNOWN |
| Core/Twin | Twin updated after Runs | Atomic commit or fail-closed clearing of all panels | UNKNOWN |
| Runs | Max 100 admitted, first 15 shown; per-row append | Full prevalidation, detached render, explicit truncation | UNKNOWN |
| NOC/Evidence | Bootstrap is UNATTESTED_UPSTREAM_API_READ | No LIVE attestation without independent evidence and freshness | UNKNOWN |
| GLPI/Copilot | Independent ACL/HITL contract | No implied authorization from viewer token | UNKNOWN |
| Navigation/routes | Not compared this increment | Route/consent parity required before upgrade | UNKNOWN |

## Negative acceptance X-021 — SPECIFIED, NOT EXECUTED
Use an isolated DOM fixture (no host, network, secrets). Install the actual JS and stub `fetch` with a valid schema `aiops.portal.readmodels.v1`, `provenance=UNATTESTED_UPSTREAM_API_READ`, `tenant_acl_qualified=true`, `actor_identity_server_derived=true`, `runtime_authenticated=false`, `live_remediation_authorized=false`; all three states `READABLE_UNVERIFIED`; six safe integer dashboard metrics, valid Twin nodes/edges, and two Runs. First Run contains five ordinary string fields. Second Run contains `status: {"toString":null}`, which is valid JSON and causes `String(value)` to throw.
1. Trigger `loadPortalReadModel()` with a synthetic bearer token; ensure no external calls except the stub.
2. Assert either **all panels remain at UNKNOWN** (fail-closed) or **all panels update coherently with a safe replacement value**; NEVER updated metrics + partial Run table + stale Twin/states + UNKNOWN result.
3. Repeat with `tenant_acl_qualified=false` and assert no Run/metric data rendered.
4. Repeat with clear invoked before a delayed JSON resolves; assert stale response cannot repopulate any panel.
5. Repeat with 17 Runs and a synthetic P0 failure in position 16; require explicit truncation and tenant-authorized retrieval path or flag failure.

Acceptance evidence required: fixture source, command, test output, commit SHA, exact CI run URL, and screenshot/DOM assertions where relevant. Until executed, X-021 is an unverified protocol. Never equate CI success with Debian runtime or E2E.

## Rollback and boundaries
Documentation-only Draft branch. Rollback: close Draft PR or revert branch-local documentation commit(s). No main writes, merges, deployments, Docker/cron/secrets/PG/GLPI changes, tenant ACL or HITL bypass. #557 rootful/rootless misdiagnosis is secondary; operator rootless evidence is historical, not a fresh host check.
