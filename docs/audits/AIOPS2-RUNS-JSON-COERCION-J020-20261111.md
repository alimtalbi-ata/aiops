# AIOPS2 — differential acceptance J-020: JSON coercion atomicity
Date: 2026-11-11 20:08 Europe/Paris. Scope: GitHub source only, no Debian/runtime access.

## Evidence and boundaries
Source: `app/portal/portal_bootstrap_client.js` on `main`, blob `ac58f73c725f5e088081bffed4478ea18585ef5c`.
`validEnvelope` checks `run_id` only for each item; `show` clears `#portal-runs` and appends each row while converting other fields with `String(run[field] ?? "UNKNOWN")`. JSON can represent an object with an own noncallable `toString` property; `String({toString:null})` throws TypeError. The load catch sets the global result to UNKNOWN without clearing already appended rows. This is a source-level failure mode, not an observed production incident.

## Differential matrix (do not infer live behavior)
| Capability | Current inspected source | Candidate acceptance | v28 / V145 / Debian |
|---|---|---|---|
| Runs atomicity | Per-row DOM mutation before all fields converted | Validate/format all fields and construct detached rows, then replace once | UNKNOWN |
| Runs completeness | 100 admitted, first 15 rendered, no truncation marker | Explicit truncation + authorized path to remaining runs | UNKNOWN |
| Dashboard / Core / Twin | Qualified tenant+actor envelope required | Preserve fail-closed and stale-response discard | UNKNOWN |
| NOC / Evidence | Bootstrap never attests LIVE | Independent timestamped provenance | UNKNOWN |
| GLPI / Copilot | Separate ACL/HITL contracts | No privileged read or action from viewer token | UNKNOWN |
| Navigation / DemoCenter | Not inspected in this increment | Route and consent parity before upgrade | UNKNOWN |

## Negative recipe J-020 (not yet executed)
Use an isolated DOM fixture (jsdom or equivalent), no network and no credentials. Load the real JS in a fresh context with nodes `portal-runs`, `portal-read-result`, `portal-read-token`, `portal-twin`, `portal-states`; stub `fetch` to return HTTP 200 with a valid `aiops.portal.readmodels.v1` envelope, provenance `UNATTESTED_UPSTREAM_API_READ`, `tenant_acl_qualified:true`, `actor_identity_server_derived:true`, `runtime_authenticated:false`, `live_remediation_authorized:false`, `states:{dashboard:"UNKNOWN",runs:"READABLE_UNVERIFIED",twin:"UNKNOWN"}`, `dashboard:null`, `twin:null`, and `runs:{items:[{"run_id":"R-OK","status":"RUNNING"},{"run_id":"R-BAD","status":{"toString":null}}]}`. This fixture is valid JSON; avoid JavaScript functions or Symbols in the payload.

Call `loadPortalReadModel()` after setting a synthetic token. **Fail condition:** a visible R-OK row remains while the global result reads UNKNOWN. **Pass condition:** either reject the whole malformed payload before DOM mutation, or safely render both rows with an explicit unverified/invalid field marker. A 503/ACL failure must leave no Run rows. Also test a late fetch after `clearPortalReadModel()`, 17 Runs with a P0 at index 16, and a forged tenant envelope. Do not label READABLE_UNVERIFIED as LIVE.

## Proposed minimal correction (not applied)
Preformat all run fields with a bounded type-safe formatter (accept only string, finite number, boolean; objects/arrays => UNKNOWN), build rows in a DocumentFragment, and replace children atomically after all validation. Keep the tenant/actor envelope and generation checks unchanged. Add a visible truncation indicator in a separate PR to avoid coupling concerns.

## Acceptance and rollback
Evidence required before upgrade: red test on baseline, green test on isolated candidate, CI URL tied to exact candidate SHA, screenshots or DOM assertions, route parity matrix and authenticated runtime evidence explicitly labeled by environment. A green GitHub CI is not Debian E2E proof. Rollback: close the Draft PR or revert its documentary commits on the isolated branch; no merge or deployment. #557 is the confirmed rootful/rootless diagnostic mismatch per operator, not a lost-storage recovery task.
