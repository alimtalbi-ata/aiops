# AIOPS2 differential upgrade audit — Runs truncation and false-success guard (2026-11-11 15:15 CET)

Scope: GitHub source-only, isolated Draft; no production/host/runtime operations.

## Verified provenance
- main source `app/portal/portal_bootstrap_client.js`, blob `ac58f73c725f5e088081bffed4478ea18585ef5c`: `validEnvelope` accepts <=100 Runs, `show` renders `items.slice(0,15)`. No explicit truncation count or pagination in this JS.
- Prior Draft #618 head `db564b9a533a393a17646881a182990058e64315`: GitHub Actions `AIOps quality gates` run 43027692903 **completed/success** as checked 2026-11-11 15:15 CET. CI is not E2E.
- Historical v28/V145, rollback images, active :7777 and candidate :17778 remain UNKNOWN; do not infer loss from absence of measurements.

## Differential matrix
| Function | Source baseline | v28/V145 | Active :7777 | Candidate :17778 | Acceptance risk |
|---|---|---|---|---|---|
| Dashboard/Core/Twin | tenant+actor qualification; READABLE_UNVERIFIED != LIVE | UNKNOWN | UNKNOWN | UNKNOWN | P0 unauthorized exposure |
| Runs | <=100 accepted; 15 displayed, no truncation label in inspected JS | UNKNOWN | UNKNOWN | UNKNOWN | P1 critical failure invisible |
| NOC/Evidence | no independent LIVE attestation in bootstrap | UNKNOWN | UNKNOWN | UNKNOWN | P0 false healthy |
| GLPI/Copilot | separate tenant/HITL boundary | UNKNOWN | UNKNOWN | UNKNOWN | P0 unauthorized transfer/action |
| Navigation/DemoCenter | not assessed in this file | UNKNOWN | UNKNOWN | UNKNOWN | P1 capability/link loss |

## Negative acceptance test R-016 (specified, not executed)
Use an isolated fake DOM and stub fetch. No live credentials, network or privileged calls.
1. Feed a valid `aiops.portal.readmodels.v1` envelope with qualified tenant/actor, `runtime_authenticated=false`, `live_remediation_authorized=false`, `provenance=UNATTESTED_UPSTREAM_API_READ`, and 17 synthetic Runs. Put FAILED/P0 `run-critical-016` in position 16.
2. Assert UI displays the critical Run **or** an explicit `15 of 17` truncation indicator and tenant-authorized path to full results. If neither exists, FAIL acceptance; do not claim a proven deployed regression.
3. Feed 101 Runs; assert no Runs rendered and result UNKNOWN. Feed an HTTP 200 envelope with `tenant_acl_qualified=false`; assert no metrics or Runs rendered, token cleared.
4. Resolve an earlier JSON response after a newer request or clear; assert stale response cannot repopulate UI. Feed HTTP 200 from Grafana/NOC without Evidence provenance; assert no LIVE/healthy promotion.
5. Capture test command, exit status, fixture checksum, DOM assertions and screenshots. Record Git SHA, workflow run, source blob, image digest and HTTP timestamp separately. E2E remains NOT VERIFIED.

## Rollback and safety
Close Draft or revert only this branch-local document. No merge, deploy, Docker, Debian, cron, secrets, PG/GLPI, other stacks, ACL or HITL changes.
#557 is an operator-confirmed rootful/rootless diagnostic mismatch: aiops UID 1001, rootless socket /run/user/1001/docker.sock, 87 containers/210 images at evidence time. No lost-storage search; current host freshness UNKNOWN.
