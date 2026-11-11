# AIOPS2 — CI Chromium failure boundary and differential acceptance (2026-11-11 16:10 CET)

Scope: source/CI-only, no host operations or runtime changes. Distinguish source, GitHub CI, Debian rootless and authenticated E2E.

## New verified finding
Draft #625 head `90bb89b98d7fbfbc03a6eae6a700a4a9b0287add`: Actions run [43036821588](https://github.com/alimtalbi-ata/aiops/actions/runs/43036821588) completed **failure**. Jobs: `core-postgres-noc-real-integration` success, `grafana-real-integration` success; `policy-and-static` failure at step **Install isolated Chromium for real portal browser E2E**. Subsequent browser E2E and static audit steps skipped. This does NOT establish an application regression; determine whether Chromium installation is infrastructure/transient before attribution. Do not claim E2E passed.
Source `main:app/portal/portal_bootstrap_client.js` blob `ac58f73c725f5e088081bffed4478ea18585ef5c`: <=100 Runs accepted; only first 15 displayed. This is a source visibility limitation, not proof of deployed regression.

## Differential matrix
| Capability | Current GitHub source/CI | Historical v28/V145 | Active :7777 | Candidate :17778 | Gate |
|---|---|---|---|---|---|
| Runs | first 15 of <=100; hidden P0 possible | UNKNOWN | UNKNOWN | UNKNOWN | P1 negative DOM R-016 |
| Dashboard/Core/Twin | qualified tenant/actor; Core PostgreSQL NOC CI success | UNKNOWN | UNKNOWN | UNKNOWN | P0 fail closed |
| NOC/Grafana/Evidence | Grafana HTTP CI success != NOC/Evidence LIVE proof | UNKNOWN | UNKNOWN | UNKNOWN | P0 provenance |
| GLPI/Copilot/HITL | independent authorization contracts | UNKNOWN | UNKNOWN | UNKNOWN | P0 refusal |
| Navigation/DemoCenter | Chromium browser E2E skipped after install failure | UNKNOWN | UNKNOWN | UNKNOWN | P1 browser coverage |

## Negative / non-regression acceptance protocol (not executed)
1. In isolated DOM fixture, supply valid qualified envelope with 17 synthetic Runs, FAILED/P0 at index 15 (position 16). Assert P0 visible **or** explicit '15/17' truncation plus tenant-authorized retrieval; otherwise FAIL. Assert no synthetic data is promoted to LIVE.
2. Supply 101 Runs or `tenant_acl_qualified=false`; assert no Runs or metrics shown and result UNKNOWN. Resolve stale JSON after clear; assert no repaint.
3. Re-run Chromium installation in isolated CI only after reviewing failing job logs; classify dependency/download failure separately from portal test failure. Do not modify shared workflows or relax safety gates merely to turn CI green.
4. Capture fixture hash, test exit code, screenshots, source SHA, Actions job and run, browser version and timestamp. Compare v28/V145, :7777 and :17778 only with authorized, timestamped HTTP and image digests; otherwise UNKNOWN.

## Provenance, handoff and rollback
#557: operator-proven rootless Docker for aiops UID 1001 at /run/user/1001/docker.sock, historical 87 containers/210 images. Rootful sudo docker emptiness is a false diagnostic. No new Debian read; host freshness UNKNOWN. E2E NOT VERIFIED.
Coordinate with #555 and existing handover ownership on #599/#618/#625; do not overwrite canonical document on main. Rollback: close Draft or revert this branch-only audit file. No merges, deployments, Docker, secrets, Debian, cron, PG/GLPI, other stacks, ACL/HITL changes.
