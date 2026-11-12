# F-031 — CI coverage is not test execution (2026-11-12 10:09 Europe/Paris)

## Verified GitHub observation
PR #689 head `f931e4201e441a36f533488b9f32da7dcfc0f9f9`: workflow run [43181259702](https://github.com/alimtalbi-ata/aiops/actions/runs/43181259702) completed **success**. Three jobs completed success: `policy-and-static`, `grafana-real-integration`, `core-postgres-noc-real-integration`. Enumerated job steps contain no explicit invocation of `test_portal_v3_canonical_ids_f030.py`; therefore F-030 execution **NOT_ATTESTED**, not FAILED. Do not infer it ran from generic `Compile Python source` or `Static repository audit` steps.

## Negative regression recipe F-031 (not executed)
1. At exact candidate SHA, execute `python3 -m unittest -v tests/observability/test_portal_v3_canonical_ids_f030.py` in isolated CI checkout.
2. Inject `sha256:` plus 12 hex digits as image ID, 12 hex digits as container ID, and a valid-length duplicate ID; each must yield NO_GO (noncanonical or duplicate). A canonical full-length synthetic inventory may yield only `IDENTITY_SHAPE_ELIGIBLE_NOT_DEPLOY_APPROVAL`.
3. Assert collector implementation exists at pinned ref, uses `docker image ls --no-trunc` and `docker ps -a --no-trunc` (or equivalent full-ID Docker API), and reports explicit completeness, source context, timestamps and counts. The path `scripts/observability/debian_rootless_readonly.py` returned GitHub 404 on #689 head during this cycle: **COLLECTOR_PATH_UNKNOWN**, not proof of absence on all branches. Locate implementation before integration.
4. Require a named CI job/step that invokes this test on the exact candidate SHA; record stdout/stderr after redaction, exit status, job ID, workflow URL. A green workflow without this coverage is `CI_GREEN_COVERAGE_UNKNOWN` and NO_GO for release.
5. Rootless host report must originate from aiops UID 1001, socket `/run/user/1001/docker.sock`, with fresh UTC timestamp, full counts and no truncation. Do not use sudo docker or equate host and CI.

## Differential acceptance matrix
| Domain | v28/V145 | Stable | V3 candidate | Negative gate |
|---|---|---|---|---|
| Dashboard / incidents | UNKNOWN | UNKNOWN | UNKNOWN | tenant isolation, stale read |
| CMDB / service map | UNKNOWN | UNKNOWN | UNKNOWN | cross-tenant edges |
| NOC | UNKNOWN | UNKNOWN | UNKNOWN | provenance conflict |
| Core / Twin / Runs | UNKNOWN | UNKNOWN | UNKNOWN | pagination, supersession |
| Evidence / Policy / HITL | UNKNOWN | UNKNOWN | UNKNOWN | fail closed, no LIVE |
| Prometheus / Grafana | UNKNOWN | UNKNOWN | UNKNOWN | stale telemetry |
| GLPI | UNKNOWN | UNKNOWN | UNKNOWN | no write |
| Copilot ticket / portal | UNKNOWN | UNKNOWN | UNKNOWN | tenant and citation ACL |
| Navigation / auth | UNKNOWN | UNKNOWN | UNKNOWN | 401/403/404/405 and CSP |

## Decision and rollback
CODE: protocol only, no runtime mutation. CI: #689 SUCCESS but F-030 coverage NOT_ATTESTED; F-031 CI UNKNOWN pending new SHA. DEBIAN: NOT_INSPECTED, no authenticated host session. E2E: NOT_VERIFIED. NO_GO release. Rollback: close this Draft or revert its documentation commits; no Debian rollback required. No merge, deployment, cron, secrets, GLPI writes, or other-stack changes.
