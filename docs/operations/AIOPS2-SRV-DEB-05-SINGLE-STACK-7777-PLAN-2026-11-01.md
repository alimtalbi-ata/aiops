# SRV-DEB-05 — one DEV stack, one portal TCP 7777 (proposal, 2026-11-01 15:21 CET)

**Status: PLAN_ONLY / NO_GO / NOT_HOST_VERIFIED.** This document is not an operator execution receipt. The existing reporter's [latest.json](https://github.com/alimtalbi-ata/aiops/blob/ops/debian-runtime-reports/ops/debian-reports/SRV-DEB-05/latest.json) at `2026-11-01T14:19:01.751858+00:00` (15:19 CET) lists 61 containers: 53 running, 8 exited; 22 healthy, 38 without healthcheck, 1 unhealthy. The reporter's loopback probe for **17777** is reachable; it does **not** test **7777**, external routing, TLS, Host header or firewall. Portal `aiops2-rebuild-portal` and Core `aiops2-rebuild-core` are running/healthy. Historical `aiops2-portal-rollback-v2-20261028` is exited/unhealthy, not evidence of an active portal outage.

## Binding decision and safe target
One **existing** DEV control plane; prefer the healthy `aiops2-rebuild-*` services and the existing GLPI/Temporal/PG16 dependencies. One canonical operator UI at host **TCP 7777**, no second portal, no alternative external UI, and never treat 17777 as 7777. Project name, image digests, host-to-container PortBindings, compose labels, networks, volumes, DB ownership, live traffic and backup integrity are **UNKNOWN** until independently inspected. The accompanying [manifest proposal](../../ops/debian/compose.canonical.plan.yml) is deliberately non-deployable; it is **not** a runnable Compose file.

## KEEP / MIGRATE / STOP-LATER / UNKNOWN matrix (non-destructive)
| Group from inventory | Current evidence | Decision now | Promotion/stop gate |
|---|---|---|---|
| `aiops2-rebuild-portal`, `aiops2-rebuild-core`, `aiops2-rebuild-worker`, `aiops2-rebuild-twin`, `aiops2-rebuild-policy`, `aiops2-rebuild-evidence`, `aiops2-rebuild-temporal` | Running; primary portal/Core healthy | **KEEP**; in-place upgrade candidate, not executed | Host 7777 binding, image digest, backups, dependency graph, exact-head CI, rollback |
| `aiops2-rebuild-postgres`, `aiops2-rebuild-temporal-postgres`, `aiops2-rebuild-glpi-db`, `aiops2-rebuild-glpi` | Running; DB health where available | **KEEP**; preserve volumes and immutable 013/014 audit | Read-only DB ownership, mount mapping, consistent backups, tested restore |
| `aiops2-rebuild-*` supporting services (Prometheus, Grafana, n8n, alertmanager, copilot, test LLM, etc.) | Running; mixed healthchecks | **KEEP/UNKNOWN** pending usage | Read-only traffic, consumers, dependencies and data retention |
| `aiops2-portal-candidate-web-20261029`, `aiops2-noc-rag-test`, `aiops2-noc-rag-copilot-test` | Running; no healthcheck | **UNKNOWN → STOP-LATER candidate**, not authorized | Ports, reverse proxy routes, clients, image digest, sessions, backups, fallback |
| `aiops2-v27-qual-*`, `aiops2-e2e-v1-*`, `aiops2-v28-*-qf*`, `aiops2-v28-sql-qual` | Multiple running/exited | **UNKNOWN → STOP-LATER candidate** | Confirm no traffic/cron, DB/Temporal ownership, networks/volumes and restore |
| `aiops2-glpi-recovery-db`, `aiops2-glpi-http-qual-db` | Running; no healthcheck | **UNKNOWN**, never stop DB blindly | Proven independent ownership, no active sessions, snapshots and retention |
| `aiops2-portal-rollback-v2-20261028` and exited init jobs | Exited; rollback marked unhealthy | **KEEP rollback evidence / UNKNOWN** | Rollback viability and retention documented before any stop |
| Demo observability stack `aiops2-demo-observability-*` | Running; no healthcheck | **UNKNOWN** | Identify telemetry consumers, retention and port use |

**STOP-LATER is a classification, not permission to stop.** No host commands, Docker mutation, volume deletion, `down -v`, prune, second persistent Compose project, GLPI write, or push to poller-controlled `deploy/aiops2-stable`.

## Authorized read-only evidence checklist (NOT EXECUTED)
An authorized host operator must collect **redacted**: `docker inspect` (RepoDigests, Config.Labels compose project/service, HostConfig.PortBindings, Networks, Mounts and volume names, Health), `docker compose config` for the *currently installed* project, `ss -lnt` for **7777 and 17777 separately**, reverse proxy routing/Host/TLS, firewall rules, `curl` HTTP Host and health probes on 7777, active connections/traffic, image pinning, DB/volume ownership, backup inventory/checksums, and restore drill receipts. Do not export credentials, raw env vars, connection strings or secret-bearing labels. A reporter extension must remain read-only and redact secrets; no unrestricted Docker socket exposure to GitHub jobs.

## Reversible in-place migration gates
1. Freeze an exact current image/compose/volume/DB manifest and checksum backup/restore receipts; keep healthy `rebuild` services running.
2. Prove host TCP **7777** and intended single reverse-proxy/UI route; map current 17777 without assuming equivalence. If 7777 is not proven, **NO_GO**.
3. Qualify selected source changes in ephemeral CI, including exact-head Core 001/004/009→014 PG16 migration and native backup/restore, Portal negative ACL and Worker/Temporal. Never apply 014 to persistent DB as a test.
4. Approve a single in-place compose delta (image digest pinning, 7777:actual internal port only after inspect, existing networks/volumes retained), run a read-only preflight and an authorized change window. No alternate portal or extra permanent stack.
5. After verified 7777 Host/TLS/health and ITIL readback, reclassify duplicates from UNKNOWN to STOP-LATER with an owner, backup, traffic evidence and revert; **do not delete** containers, volumes or DB in this cycle.
6. Roll back **application code/image/config** to recorded digests and previous route if health fails; keep immutable 013/014 audit, DB/volumes and existing backups. No force-push, no main reset.

**Owner:** Architect coordinates host-evidence schema/manifest and gate. Portal owns UI 7777/IdP negative contract, Core owns 014 audit and DB, Worker owns delivery/Temporal, ACME owns synthetic seven-event fixture. **RUNTIME_OBSERVED** is only GitHub-published read-only inventory and disposable CI; host 7777, single public entry and actual in-place migration remain **NOT_VERIFIED**.

## 2026-11-01 16:14 CET — read-only inventory checkpoint

GitHub latest.json collected_at 2026-11-01T15:14:02.002390+00:00: 61 containers, 53 running/8 exited; 22 healthy/38 no-healthcheck/1 unhealthy. Rebuild Portal healthy; candidate Portal running without healthcheck; historical rollback exited/unhealthy. Loopback 17777 reachable, host TCP 7777 NOT_VERIFIED. KEEP/MIGRATE/STOP-LATER/UNKNOWN until read-only PortBindings, image digests, Compose labels, networks, proxy, ss, firewall, Host/TLS, traffic, volumes, DB ownership, backups and rollback. No host action, no new stack, no volume changes.
