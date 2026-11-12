# AIOPS2 / Portal V3 — F-030 2026-11-12 09:13 Europe/Paris

## CODE
Branch `audit/portal-v3-canonical-ids-f030-20261112` stacked on #686 SHA `b81a47919374e2e439ba5006a85d5dd5c23d2337`. New standalone `tests/observability/test_portal_v3_canonical_ids_f030.py`: 8 unittest methods, including negatives for truncated image/container IDs, tag masquerading as identity, uppercase/whitespace, duplicates, boolean counts and absent completeness. Docker image identity must be `sha256:` + 64 lowercase hex; container identity 64 lowercase hex. Collector must use `--no-trunc` before this gate can be integrated; shape alone is NOT host provenance or deployment approval. Tests NOT_EXECUTED; no release-gate integration. Run `python3 tests/observability/test_portal_v3_canonical_ids_f030.py`.

## CI
#686 SHA `b81a47919374e2e439ba5006a85d5dd5c23d2337`: quality run 43174753074 completed SUCCESS, three jobs success (policy/static, Grafana, Core/PG/NOC). No evidence F-029 standalone tests executed. F-030 final SHA and CI must be checked separately.

## DEBIAN
NOT_INSPECTED: no authenticated SRV-DEB-05 session. Historical aiops UID 1001 rootless socket `/run/user/1001/docker.sock`, 87 containers / 210 images; stale historical evidence, not current state. #557 rootful/rootless diagnostic only. Read-only command after script review and verified checkout SHA: `env DOCKER_HOST=unix:///run/user/1001/docker.sock timeout 90s python3 scripts/observability/debian_rootless_readonly.py` as user aiops, never sudo docker. Collector privacy, flock, 0700/0600, bounded retention, masking and completeness require review; no cron installed.

## E2E
NOT_VERIFIED. NO_GO Portal V3: exact candidate green CI, fresh complete rootless inventory, functional v28/V145 → stable → candidate parity, portal-only backup/rollback and tenant ACL/HITL smoke required. No LIVE, GLPI write, main merge or other-stack change.

## Matrix
| Domain | v28/V145 | Stable | Portal V3 | Negative gate |
|---|---|---|---|---|
| Dashboard / incidents | UNKNOWN | UNKNOWN | UNKNOWN | stale/foreign tenant |
| CMDB / service map | UNKNOWN | UNKNOWN | UNKNOWN | cross-tenant relation |
| NOC | UNKNOWN | UNKNOWN | UNKNOWN | provenance mismatch |
| Core / Twin / Runs | UNKNOWN | UNKNOWN | UNKNOWN | pagination, concurrency |
| Evidence / Policy / HITL | UNKNOWN | UNKNOWN | UNKNOWN | fail closed, no LIVE |
| Prometheus / Grafana | UNKNOWN | UNKNOWN | UNKNOWN | stale metric |
| GLPI | UNKNOWN | UNKNOWN | UNKNOWN | deny write |
| Copilot ticket / portal | UNKNOWN | UNKNOWN | UNKNOWN | ACL and evidence |
| Navigation / auth | UNKNOWN | UNKNOWN | UNKNOWN | 401/403/404/405 and CSP |

## Rollback
Close F-030 Draft or revert isolated F-030 test and handover commits. No runtime changes to undo.

---

# AIOPS2 / Portal V3 — handover 2026-11-12 08:21 Europe/Paris

## CODE
F-029 branch `audit/portal-v3-inventory-uniqueness-f029-20261112` stacked on F-028 PR #683 SHA `3f6760caf554d861b2d37555aeec702bd5375e1f`. Adds isolated synthetic negative identity tests at `tests/observability/test_portal_v3_inventory_identity_f029.py`. Duplicate or blank image/container identifiers are rejected even when declared counts equal list lengths; Boolean count, mismatched count and absent completeness rejected. Command: `python3 -m unittest -v tests/observability/test_portal_v3_inventory_identity_f029.py`. NOT integrated into collector/release gate. No runtime writes.

## Capability matrix (v28/V145 -> stable -> Portal V3)
| Domain | Baseline | Stable host | Candidate | Negative acceptance |
|---|---|---|---|---|
| Dashboard / incidents | UNKNOWN | UNKNOWN | UNKNOWN | stale response / tenant isolation |
| CMDB / service map | UNKNOWN | UNKNOWN | UNKNOWN | cross-tenant links denied |
| NOC | UNKNOWN | UNKNOWN | UNKNOWN | source provenance independent |
| Core / Twin / Runs | UNKNOWN | UNKNOWN | UNKNOWN | stale state, pagination, concurrency |
| Evidence / Policy / HITL | UNKNOWN | UNKNOWN | UNKNOWN | fail closed; no LIVE |
| Prometheus / Grafana | UNKNOWN | UNKNOWN | UNKNOWN | stale metric not LIVE |
| GLPI | UNKNOWN | UNKNOWN | UNKNOWN | read-only, deny write |
| Copilot ticket / portal | UNKNOWN | UNKNOWN | UNKNOWN | tenant ACL and provenance |
| Navigation / auth | UNKNOWN | UNKNOWN | UNKNOWN | 401/403/404/405, keyboard/CSP |

## CI
#683 exact SHA `3f6760caf554d861b2d37555aeec702bd5375e1f`: workflow run 43166281116 completed SUCCESS (queried 2026-11-12). This does not prove F-028 standalone tests were executed. F-029 SHA pending final commit and CI recheck; test execution NOT_ATTESTED.

## DEBIAN
NOT_INSPECTED. No authenticated SRV-DEB-05 session available. Operator historical rootless UID 1001, socket `/run/user/1001/docker.sock`, 87 containers and 210 images; not a fresh measurement. Existing collector PRs #670/#673/#676/#679/#682 and privacy PR #685 must be reviewed before install. Required read-only execution as aiops (not sudo docker): `env DOCKER_HOST=unix:///run/user/1001/docker.sock timeout 90s python3 scripts/observability/debian_rootless_readonly.py` from an approved checkout, after verifying script path and SHA. Collector output must redact logs, avoid secrets, enforce 0700 directory, 0600 files, flock, timeout and retention after review. No cron installed. #557 is rootful/rootless false diagnostic, no recovery.

## E2E
NOT_VERIFIED; NO_GO deployment. Green exact candidate CI, fresh rootless provenance, parity fixtures, portal-only compatibility, backup and tested rollback, ACL/HITL smoke required. No other stack changes, no LIVE, no GLPI writes.

## Rollback
Close Draft F-029 or revert its isolated test+handover commits. No Debian changes to roll back. No merge main.
