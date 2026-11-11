# AIOPS2 — audit différentiel : statut Run non attesté (2026-11-11 17:11 CET)

Scope: GitHub source only. No Debian, Docker, GLPI, deployment or ACL/HITL changes.

## Evidence source
`app/portal/portal_bootstrap_client.js` blob `ac58f73c725f5e088081bffed4478ea18585ef5c` on main:
- `validEnvelope` requires `provenance=UNATTESTED_UPSTREAM_API_READ`, `runtime_authenticated=false`, `live_remediation_authorized=false`, qualified tenant/actor booleans, and states UNKNOWN or READABLE_UNVERIFIED.
- `runs.items` validates non-empty run_id and length <=100 but does **not** validate `status`, `mode`, `scenario_id` or `overall_confidence` semantics.
- `show` displays arbitrary `String(run.status)` verbatim as a table cell; page-level label remains READABLE_UNVERIFIED. Risk: a synthetic upstream `status: "LIVE / REMEDIATED"` appears as a factual row-level status without explicit provenance in that cell. This is a presentation ambiguity, not proof of a deployed regression.

## Before/after acceptance matrix
| Feature | Current source | Required candidate / upgrade | v28/V145, :7777, :17778 |
|---|---|---|---|
| Dashboard / Core / Twin | tenant/actor envelope, UNKNOWN vs READABLE_UNVERIFIED | preserve fail-closed; no LIVE inference | UNKNOWN |
| Runs row status | arbitrary upstream string displayed | visibly qualify unverified status at row level; no fabricated LIVE | UNKNOWN |
| NOC / Evidence | no runtime attestation in bootstrap | independent signed/fresh evidence; no false healthy | UNKNOWN |
| GLPI / Copilot | not proven by bootstrap | preserve tenant/HITL boundaries | UNKNOWN |
| Navigation / DemoCenter | not proven by bootstrap | retain routes and consent gates | UNKNOWN |

## Negative test U-017 (fixture only; NOT EXECUTED)
1. In an isolated browser/DOM fixture, return HTTP 200 with schema `aiops.portal.readmodels.v1`, provenance `UNATTESTED_UPSTREAM_API_READ`, tenant_acl_qualified=true, actor_identity_server_derived=true, runtime_authenticated=false, live_remediation_authorized=false.
2. Set dashboard=null, twin=null; states dashboard=UNKNOWN, twin=UNKNOWN, runs=READABLE_UNVERIFIED; runs.items=[{run_id:"synthetic-r1", status:"LIVE / REMEDIATED", mode:"AUTO", overall_confidence:1, scenario_id:"synthetic"}].
3. Verify the row cannot be mistaken for a LIVE attestation: status must be visibly qualified as UNVERIFIED (e.g. column label or per-row suffix), without modifying upstream semantics.
4. Repeat with a forged tenant_acl_qualified=false: no rows and UNKNOWN. Repeat with response arriving after clear(): no stale rows. No Core/GLPI/NOC upstream calls from the fixture.
5. Fail if any Run appears as authenticated LIVE, or if the forged envelope populates UI.

Expected with current source: row-level provenance qualification is absent; test U-017 likely fails. Not executed, not a runtime regression claim.

## Evidence / CI / rollback
Source blob as above; this document is a review protocol, not execution evidence. CI at this branch SHA must be checked separately. Do not interpret green source CI as Debian E2E. #557 is an operator-confirmed rootful/rootless diagnostic mismatch (UID 1001, rootless socket /run/user/1001/docker.sock, 87 containers/210 images at observation); host freshness not independently rechecked. E2E NOT VERIFIED.
Rollback: close Draft PR or revert this single documentation commit on isolated branch. No merge/deploy.
