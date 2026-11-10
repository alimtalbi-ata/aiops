# SRV-DEB-05 — in-place consolidation contract (2026-11-01 14:15 CET)

**User decision:** stop multiplying persistent containers. Consolidate and evolve only the useful services of **one** AIOps2 DEV stack on the existing Debian 13 host. This instruction supersedes any prior plan to deploy another permanent `rebuild`, `v27-qual`, `e2e-v1`, `candidate`, or `v28-qf` parallel stack.

## Grounded inventory

Read-only GitHub-published host report `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json` collected `2026-11-01T13:14:01.830140+00:00`: **61 containers, 53 running, 8 exited**. Observed active `aiops2-rebuild-*` healthy: intelligence, simulator, worker, portal, core, twin, policy, copilot, prometheus, grafana, test-llm, evidence, temporal, postgres, temporal-postgres, glpi-db. GLPI, n8n, Temporal UI and other auxiliary containers have no declared healthcheck; running is not application-level proof. Historical rollback portal is exited/unhealthy; do not count it as a failure of active portal.

Other running groups observed: `aiops2-v27-qual-*`, `aiops2-e2e-v1-*`, `aiops2-v28-core-qf186`, `aiops2-v28-sql-qual`, `aiops2-portal-candidate-web-20261029`, `aiops2-glpi-http-qual-db`, `aiops2-glpi-recovery-db`, `aiops2-noc-rag-*-test`, `aiops2-demo-*`. **These are candidates for investigation, NOT approved deletions.** They may contain unique data, active dependencies or a needed rollback.

## Mandatory decision matrix (to be completed with on-host read-only evidence)

| Service class | Initial disposition | Gate |
|---|---|---|
| `aiops2-rebuild-{core,worker,portal,twin,policy,intelligence,evidence,simulator}` | KEEP / evolve in place after qualification | actual image digest/commit, compose config, API smoke, backup, rollback |
| `aiops2-rebuild-{postgres,temporal,temporal-postgres,glpi,glpi-db}` | KEEP / protect state | volume map, backup restore rehearsal, migration compatibility |
| Monitoring and support (`prometheus,grafana,alertmanager,otel,loki,tempo,copilot,n8n,temporal-ui`) | KEEP if dependency or explicit product value, else UNKNOWN | consumer graph, ports, ownership, retention |
| `aiops2-v27-qual-*`, `aiops2-e2e-v1-*`, `aiops2-v28-*-qf*`, `portal-candidate` | REVIEW FOR STOP-LATER | no active clients, distinct DB/volumes, preservation plan, rollback |
| `glpi-*-qual-db`, `glpi-recovery-db`, `noc-rag-*-test`, `demo-*` | UNKNOWN | inspect real users, persisted data, unique service dependencies |
| exited init/schema/namespace containers | REVIEW, often expected completed jobs | exit code and init semantics, no cleanup until verified |
| exited rollback portal | RETAIN until replacement rollback is proven | rollback artifact and recovery test |

**No container deletion or stop is authorized solely by a name or inventory state.** Keep a reversible STOP-LATER list, with volume preservation and restart commands, before any operator-authorized execution.

## Non-destructive evidence to collect

Read-only, scoped host command outputs (without secret env values): `docker ps -a --format '{{json .}}'`, `docker inspect` on selected containers for image ID, labels, mounts, network, exposed/bound ports, restart policy and health, `docker compose ls --all`, `docker volume ls`, `docker network ls`, and read-only dependency/port probes. Record which compose project owns each service and which database/volume it uses. **Never publish secrets or unredacted env.** Existing GitHub reporter currently proves name/state/health/image but not full dependency graph.

## Upgrade gates

1. Pin current working compose manifest and image digests; snapshot/checksum config, DB backups, tested restore, rollback.
2. Build a **single canonical compose project** by reusing existing networks/volumes and canonical service names. Do not rename existing volumes accidentally (Compose project names alter generated resource names).
3. Perform unit/CI tests in disposable GitHub runners; no extra persistent host stacks.
4. Upgrade one application service at a time only when its contract and migration are qualified; verify health and business smoke. State-bearing PostgreSQL/GLPI/Temporal upgrades require explicit backup/restore and schema compatibility.
5. Stop duplicates **only after** traffic, mounts, clients, owners and rollback are mapped and a safe stop window approved. Never use `docker compose down -v`, global prune, volume deletion or mass kill.
6. Keep stable branch `deploy/aiops2-stable` unchanged until the tested in-place plan is approved; its poller may auto-deploy new commits.

## Eight-hour supervision dispatch

All five existing schedules updated with this directive on 2026-11-01; architect owns the consolidated KEEP/MIGRATE/STOP-LATER/UNKNOWN matrix, and owners must avoid new persistent stacks. Every cycle must link code/test/doc delta and exact SHA/CI; distinguish `SOURCE_REVIEWED`, `CI_PASS`, `RUNTIME_OBSERVED`, `NOT_VERIFIED`. Current status: **PLAN DOCUMENTED, HOST CHANGES NOT EXECUTED**.

Related recovery handoff: [AIOPS2-8H-SUPERVISION-CONTEXT-2026-11-01.md](AIOPS2-8H-SUPERVISION-CONTEXT-2026-11-01.md). Host runbook: [SRV-DEB-05-AUTOMATION-RUNBOOK.md](../operations/SRV-DEB-05-AUTOMATION-RUNBOOK.md).
