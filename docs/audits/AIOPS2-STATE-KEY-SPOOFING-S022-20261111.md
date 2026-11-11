# AIOPS2 — differential negative acceptance S-022: unrecognized state keys
Date: 2026-11-11 22:16 Europe/Paris. Scope: GitHub source only; Debian/E2E NOT VERIFIED.

## Evidence and failure mechanism
Source `app/portal/portal_bootstrap_client.js` on main, blob `ac58f73c725f5e088081bffed4478ea18585ef5c`. `validEnvelope` validates `states.dashboard`, `states.runs`, and `states.twin`, but does not reject extra keys in `states`. The success banner uses `Object.values(data.states).includes("READABLE_UNVERIFIED")` over **all** keys, not only the three validated keys. An extra untrusted `states.evidence="READABLE_UNVERIFIED"` can therefore cause the banner to claim READABLE_UNVERIFIED while all three recognized panels remain UNKNOWN. This is a source-derived contract/presentation discrepancy, not a demonstrated deployed regression or evidence of LIVE.

## Differential matrix
| Function | Existing source | Candidate acceptance | v28/V145 / deployed |
|---|---|---|---|
| Dashboard | Recognized state validated, extra states unchecked | Banner derived exclusively from validated dashboard/runs/twin states | UNKNOWN |
| Core/Twin | Recognized Twin state validated | Unknown keys cannot elevate aggregate read state | UNKNOWN |
| Runs | Recognized state validated; 100 admitted, 15 rendered | No unrecognized state spoofing; truncation disclosed | UNKNOWN |
| NOC/Evidence | No runtime LIVE attestation | Extra `evidence` state must not imply evidence availability | UNKNOWN |
| GLPI/Copilot | Separate ACL/HITL contracts | No inferred authority from extra state fields | UNKNOWN |
| Navigation / routes | Not inspected in this increment | Route parity and consent still required | UNKNOWN |

## S-022 negative acceptance — SPECIFIED, NOT EXECUTED
In an isolated DOM/Node fixture, stub `fetch('/api/portal/bootstrap')` and supply a JSON envelope with `schema="aiops.portal.readmodels.v1"`, `provenance="UNATTESTED_UPSTREAM_API_READ"`, `tenant_acl_qualified=true`, `actor_identity_server_derived=true`, `runtime_authenticated=false`, `live_remediation_authorized=false`, `dashboard=null`, `runs=null`, `twin=null`, `states={dashboard:"UNKNOWN",runs:"UNKNOWN",twin:"UNKNOWN",evidence:"READABLE_UNVERIFIED"}`. Trigger `loadPortalReadModel()` using a synthetic token and no real network.
1. Assert aggregate result remains `UNKNOWN — aucune source lisible`, or the envelope is rejected; it must not become READABLE_UNVERIFIED.
2. Repeat with `states.evidence="LIVE"`, and with `states.copilot="READABLE_UNVERIFIED"`: neither may attest NOC/Evidence/Copilot or authorize actions.
3. Repeat with `tenant_acl_qualified=false`; assert no metrics, Runs or Twin data and no upstream calls except the stub.
4. Repeat after `clearPortalReadModel()` while the response is delayed; stale responses must not repopulate UI.

Suggested isolated fix: replace `Object.values(data.states)` with `["dashboard","runs","twin"].some(key => data.states[key] === "READABLE_UNVERIFIED")`, or reject extra keys in `validEnvelope` (evaluate compatibility first). Preserve ACL/HITL and `UNATTESTED` semantics.

## Proof, CI, rollback
Prior Draft #655 head `8da0c2f01ed0a18e1e17479ee1eaa54245c5cd7c`: Actions run 43093715006 completed SUCCESS, but does not execute S-022 or establish E2E. New Draft CI must be checked against its own exact head SHA; no pass assumed.
Rollback: close Draft or revert this documentation-only branch; no merge/deploy, Docker, Debian, secrets, GLPI/PG, other stacks or runtime changes.
#557: operator-confirmed rootless Docker UID 1001, 87 containers / 210 images at observation; rootful sudo=0 is a false diagnostic. Freshness of host evidence not revalidated; do not investigate lost storage.
