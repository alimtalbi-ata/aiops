# F-026 — negative release gate for stale host observations

Date: 2026-11-12 Europe/Paris. Scope: Portal V3 qualification only. This protocol does not assert deployed behavior.

## Provenance boundary
CODE (GitHub commit), CI (workflow at that exact SHA), DEBIAN (authenticated aiops UID 1001 rootless daemon) and E2E (tenant-scoped browser journey) are independent evidence sources. CI success cannot make an old or absent Debian observation fresh. Docker rootful is never a substitute for rootless.

## Negative fixtures and acceptance
1. Given CI success at candidate SHA and a Debian report collected 2026-11-08, evaluate on 2026-11-12. Expected host=STALE and release=NO_GO; not FRESH.
2. Given missing, future-dated, unparseable or timezone-less collection timestamp, expect UNKNOWN/NO_GO.
3. Given Docker context not rootless, socket not /run/user/1001/docker.sock, UID !=1001, permission error or command timeout, expect UNKNOWN/NO_GO.
4. Given listed image/container rows not equal to independently reported total, expect UNKNOWN/NO_GO, even if CI green; no silently truncated output.
5. Given cross-tenant incident/Run/Evidence request, expect 401/403 and no data or stale authorized state leakage. Policy/HITL remains fail-closed; no LIVE actions.
6. Given delayed older request resolving after newer request, UI must discard old response and retain the newer authorized generation.
7. Given portal release SHA not equal to CI-tested SHA, expect NO_GO.

All fixtures must run in isolated test harness with no GLPI writes, no Debian mutations, no secret exposure. Tests here are specified, NOT_EXECUTED.

## Differential matrix (baseline → stable → candidate)
| Capability | v28/V145 baseline | Stable rootless | Portal V3 candidate acceptance |
|---|---|---|---|
| Dashboard / incidents | UNKNOWN | UNKNOWN | tenant scoped, accurate source/freshness |
| CMDB / service map | UNKNOWN | UNKNOWN | graph parity and no cross-tenant edges |
| NOC | UNKNOWN | UNKNOWN | freshness, read-only provenance |
| Core / Twin / Runs | UNKNOWN | UNKNOWN | atomic rendering, pagination, generation race |
| Evidence | UNKNOWN | UNKNOWN | fail-closed, no fabricated LIVE |
| Policy / HITL | UNKNOWN | UNKNOWN | deny without approval; no bypass |
| Prometheus / Grafana | UNKNOWN | UNKNOWN | independent source and age |
| GLPI | UNKNOWN | UNKNOWN | read-only ticket linkage; no write |
| Copilot ticket / portal | UNKNOWN | UNKNOWN | permission boundary and provenance |
| Navigation / auth | UNKNOWN | UNKNOWN | 401/403/404/405, keyboard, CSP, route parity |

## Host collection contract
Run only as aiops (UID 1001), Docker rootless socket /run/user/1001/docker.sock, no sudo docker. Capture timestamp UTC, exact source SHA, docker context/info, full counts plus completeness flags, container IDs/status/health and image digests or redacted identifiers, ports and volume names only after privacy review, systemd --user status, cron metadata, bounded redacted logs. UNKNOWN on inaccessible commands. Lock with flock, bounded timeout, mode 0600, retention, no secrets or volume contents. Collector #670/#673/#676 needs review and execution; do not install cron without review.

## Release gate and rollback
No Debian authenticated session in this audit; no deploy attempted. Gate: green CI at exact SHA, compatibility/parity, fresh rootless inventory, backup and tested rollback, portal-only change window, before/after health, tenant/auth/HITL smoke, immediate revert on failure. Preserve other five stacks and data. Git rollback: close Draft/revert documentation commits; no main merge.
