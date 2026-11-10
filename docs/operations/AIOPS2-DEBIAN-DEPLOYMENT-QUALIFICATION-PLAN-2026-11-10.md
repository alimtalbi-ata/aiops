# AIOPS2 — Debian deployment and qualification plan

**Date:** 2026-11-10  
**Target documented by the project:** `SRV-DEB-05`, Debian 13, working root `/home/aiops`  
**Status:** planning only — no Debian host was accessed or changed while preparing this document.  
**Authority:** this plan does not authorize production changes, secret rotation, service stops, migrations, legacy retirement, deployment or LIVE execution.

## 1. Current evidence and constraints

### GitHub qualification snapshot

Last checked 2026-11-10:

| PR | Head | CI | State |
|---|---|---:|---|
| #536 | `e364a456` | 13/13 PASS | Draft |
| #537 | `e85f0c61` | 10/10 PASS | Draft |
| #539 | `73a12fe1` | 10/10 PASS | Draft |
| #541 | `a4a8a5f9` | 10/10 PASS | Draft |
| #542 | `3f2cedab` | 16/16 PASS | Draft |
| #544 | `865fea95` | 10/10 PASS | Draft |

All six PRs were reported by GitHub as mergeable `clean` at that check. This is CI evidence for those exact heads, not proof that the PRs have been merged, that their dependency order is correct, that the Debian runtime matches them, or that production is qualified. Re-check exact heads and checks immediately before any promotion.

Security blocker: issue [#535](https://github.com/alimtalbi-ata/aiops/issues/535) remains OPEN and unassigned. The historic n8n credential exposure still requires credential-owner evidence of revocation/rotation, usage audit and copy/history assessment, plus independent security approval. Green CI does not close this gate.

### Debian host inventory is stale

The latest committed SRV-DEB-05 inventory is dated 2026-11-08. It records 5 Compose projects, 78 containers (59 running, 18 exited, 1 created), 18 networks and 59 volumes. It explicitly says it did not query application APIs/databases or prove service health. Several services lack Docker health checks; one Compose source path was missing; multiple qualification and rollback stacks coexist. These figures are a historical baseline only. Obtain a fresh read-only inventory before planning a change window.

### Source-level blockers to resolve before running the installer

1. `compose.yml` defaults the Portal host port to **17777** (`AIOPS_PORTAL_HOST_PORT`) mapped to container port 777.
2. `deploy/preflight.sh` currently checks for the literal port string `7777:777`, which does not match the Compose default expression. This can reject the default configuration even though `tests/static-audit.sh` checks for the 17777 expression.
3. `docs/README-DEPLOY.md` still documents Portal port **7777**, while the current `README.md` and `compose.yml` say **17777**. Resolve this documentation/configuration contract and test both default and override cases before deployment.
4. `deploy/install.sh` calls preflight, builds and starts the stack, then runs qualification and synthetic E2E. It does not itself create a verified backup or test rollback.
5. `deploy/big-bang.sh` defaults `RETIRE_LEGACY` to 1 and invokes `deploy/retire-legacy.sh` before build/up. That script stops containers matching its legacy-name pattern. **Do not run big-bang.sh or enable RETIRE_LEGACY during this plan.**
6. Compose has fixed `container_name: aiops2-...` names. A second candidate Compose project on the same Docker daemon can collide even with a different Compose project name. Use a separate Debian VM/host for staging, or first engineer and qualify a complete namespacing change. Do not attempt parallel staging on the existing host as-is.
7. `deploy/init-env.sh` intentionally leaves an existing `.env` unchanged. It does not rotate secrets. Secret changes require a separate coordinated consumer/database plan and rollback.

## 2. Promotion model and stop/go gates

Promotion order: **DEV source → CI → isolated integration/qualification → Debian staging → controlled production change window → post-deploy verification**. LIVE execution is a separate approval, not part of installation.

### Gate 0 — fresh read-only SRV-DEB-05 discovery

Run only after access is separately arranged. No commands in this section should change host state.

- Confirm Debian version, kernel, hostname, UTC/local time, uptime, filesystem free space/inodes, memory and CPU.
- Confirm Docker Engine and Compose versions and daemon health.
- Capture `docker compose ls -a`, `docker ps -a`, and metadata-only inspect: Compose project/service labels, image tags and immutable digests, container state/health, restart policy, published ports, networks and mounts/volume names.
- Hash every effective Compose file and identify working directories/override files; reconcile by Compose labels, not container names.
- Check port listeners and firewall rules without changing them.
- Inspect cron and systemd timers read-only. Reuse the existing `aiops-debian-reporter` → `aiops-publish-report` pipeline if still present; do not create a duplicate cron, self-hosted runner, or unrestricted Docker-socket job.
- Do not print `.env`, environment values, tokens, credential-bearing command lines or secret-bearing inspect fields. Redact before saving or publishing.
- Record unknown/unverifiable fields as UNKNOWN. Do not infer application health from a running container.

**Gate 0 output:** timestamped, redacted inventory; Compose ownership map; port/volume/network map; backup capacity estimate; list of conflicts and UNKNOWNs. If source files, ownership or data volumes cannot be mapped, STOP.

### Gate 1 — source and release qualification

- Re-check the six PR exact heads, all required check runs, changed-file lists, branch bases and dependency DAG.
- Resolve PR dependencies and review all diffs. Do not merge by numerical PR order or merge a child branch before its intended base changes are available.
- Resolve the P0 #535 security requirements. No production promotion while it is open.
- Fix and test the Portal port/preflight mismatch before relying on `deploy/preflight.sh`.
- Produce a versioned release manifest with exact commit SHA, image digests, migration set, SBOM/package hash, configuration schema and release notes.
- Confirm no `.env`, secrets, database dumps, production data or private keys are included in artifacts.

**Gate 1 output:** approved exact source commit(s), review approvals, CI evidence, security sign-off, release manifest and checksums. Otherwise STOP.

### Gate 2 — isolated staging qualification

Preferred target: a dedicated disposable Debian 13 VM/host, not the current multi-project SRV-DEB-05 Docker daemon. Use synthetic data and unique staging credentials.

1. Validate Docker/Compose versions and disk capacity.
2. Run secret-safe Compose validation; never paste rendered Compose config into logs.
3. Build every image from the exact release commit and record immutable image digests.
4. Apply the complete migration chain to a disposable PostgreSQL 16 instance; verify schema, indexes, constraints and immutable-ledger triggers.
5. Run PostgreSQL DR rehearsal using PostgreSQL 16-matched `pg_dump/pg_restore` tools; verify restored row counts/hashes and corruption detection.
6. Run MariaDB/GLPI recovery rehearsal separately; verify backup and restore against a disposable database.
7. Run Python unit/contract tests, static audit, SQL audit, package verification, YAML/JSON workflow contract tests and n8n fail-closed security lab.
8. Start the staging stack; wait for health/readiness, not just container-running state.
9. Run service/API smoke tests for Portal, Core, Twin, Evidence, Policy, Copilot, Worker, Simulator, Temporal, PostgreSQL, GLPI/MariaDB, n8n, Prometheus, Grafana and Alertmanager.
10. Run synthetic E2E Portal → Core → Temporal → Worker with a synthetic DEMO run; verify idempotency, event/evidence lineage, policy fail-closed behavior and no external side effects.
11. Inject controlled failure cases: dependency unavailable, timeout, duplicate delivery, worker restart, stale/missing evidence, partial failure and restore failure. Confirm safe terminal state and reconciliation.
12. Test rollback to the prior image/config and restore the backup into a separate disposable target. Do not use production volumes for rehearsal.

**Gate 2 output:** signed test report with PASS/FAIL/SKIP/NOT RUN, exact commit/digests, timestamps, synthetic Run ID, backup/restore hashes, failure-injection outcomes and rollback evidence. Any failed critical test or unexplained UNKNOWN blocks promotion.

### Gate 3 — production change request and pre-change backup

Requires a separately approved maintenance window, named operator, reviewer, application owner, security owner and rollback decision-maker.

- Re-inventory the live host immediately before the window and compare against Gate 0.
- Identify exact Compose project(s), files, services, ports, networks and volumes to be changed. Confirm no unrelated project is targeted.
- Back up PostgreSQL application DB, Temporal DB and GLPI/MariaDB DB using version-compatible tools; capture persistent volumes/configuration and exact Compose files. Store backups encrypted and outside Git/chat. Verify backup checksums and restore into an isolated target.
- Preserve current image digests and configuration. Verify sufficient disk space for backups plus new images.
- Confirm the maintenance window, service impact, user communications, monitoring coverage and rollback trigger thresholds.
- No `docker compose down -v`, `docker system prune`, volume deletion, legacy retirement, database merge or credential rotation as an incidental install step.

**Gate 3 output:** approved change record, verified backups and restore proof, exact target inventory, stop conditions, operator/reviewer assignments and tested rollback command sequence. Otherwise STOP.

### Gate 4 — controlled deployment

Only after Gates 0–3 and explicit production authorization:

- Deploy the approved artifact/commit only; do not pull mutable tags as the release identity.
- Apply only reviewed configuration changes. Keep production secrets external and permission-restricted; never regenerate or rotate them implicitly.
- Apply migrations in the documented order with pre/post schema checks and a tested recovery path.
- Start/upgrade only the named Compose project/services. Do not retire old stacks or remove volumes as part of this release.
- Run post-deploy health and API smoke checks, then synthetic DEMO E2E only.
- Observe logs/metrics/traces for the agreed soak period; redact secrets and customer data.
- Stop and roll back on migration error, failed critical health check, data-integrity mismatch, unexpected external action, elevated error rate or inability to prove the expected source/image provenance.

### Gate 5 — post-deploy and handover

- Capture fresh read-only inventory: project labels, effective Compose file hashes, image digests, source SHA, health checks, ports, networks, mounts, volumes and restart policies.
- Run approved post-deploy functional checks and compare with pre-change baseline.
- Verify alerting, dashboards, backups, restore receipt and existing Debian reporter/publication receipt.
- Update project continuity, component catalog, architecture and dated operations inventory in the same PR/change record.
- Keep the previous release and backups until the rollback retention window expires and the owner approves retirement.

## 3. Test matrix

| Layer | Test / evidence | Required outcome |
|---|---|---|
| Source | Python compile, unit/contract tests | All required tests pass |
| Static | `tests/static-audit.sh`, secret scan, YAML/JSON contracts | No unsafe defaults, embedded credentials or LIVE path in n8n template |
| SQL | `tests/sql-audit.sh`, migration chain on disposable PG16 | Schema and invariants pass |
| DR | PG16 dump/restore and MariaDB restore | Hash/row checks match; corruption is detected |
| Packaging | `deploy/package.sh`, checksum, SBOM | Reproducible artifact; no secrets/data |
| Compose | `docker compose --env-file .env config --quiet` | Valid model; rendered values not logged |
| Runtime | `tests/qualification.sh` plus per-service readiness/API checks | All required services ready |
| Synthetic E2E | `tests/synthetic-e2e.sh` | DEMO run reaches inventory; no LIVE effects |
| Resilience | timeout, duplicate, restart, stale evidence, partial failure | Fail closed; idempotency and reconciliation preserved |
| Rollback | restore prior image/config/DB on isolated target | Verified recovery to known baseline |
| Security | P0 remediation, n8n security lab, independent review | Explicit signed clearance before production |

The existing `tests/qualification.sh` checks container presence plus Portal, GLPI, Prometheus and Grafana endpoints; it is not by itself full service qualification. The existing `tests/synthetic-e2e.sh` posts to `/api/demo` and checks Run inventory; it is synthetic evidence, not LIVE qualification.

## 4. Debian change sequence — proposed, not executed

1. **Read-only discovery only:** capture current host/runtime state and resolve unknown project ownership.
2. **Source fixes:** correct preflight port assertion and deployment docs; add tests for default 17777 and explicit port override. Review fixed container names and staging isolation.
3. **Release assembly:** resolve PR dependency graph, security P0, exact release commit and immutable artifact manifest.
4. **Staging:** qualify on a separate disposable Debian host/VM.
5. **Change request:** obtain named approvals, maintenance window, verified backups and tested rollback.
6. **Production:** controlled upgrade of only the approved project/services.
7. **Acceptance:** smoke, synthetic E2E, monitoring soak, inventory and handover.
8. **LIVE:** separate risk assessment and signed authorization; not included in this deployment.

## 5. Immediate action list

- [ ] Re-check exact PR heads and CI; all PRs currently remain Draft.
- [ ] Resolve issue #535 and record independent security approval.
- [ ] Fix `deploy/preflight.sh` Portal port assertion and `docs/README-DEPLOY.md` port mismatch; add tests.
- [ ] Decide staging host/VM and confirm isolation from existing fixed `container_name` values.
- [ ] Obtain a fresh read-only SRV-DEB-05 inventory; 2026-11-08 snapshot is stale.
- [ ] Inspect and reuse existing Debian reporter/publisher; do not add a new cron.
- [ ] Define backup, restore, rollback, change window, operator and reviewer.
- [ ] Run staging qualification and attach immutable evidence.
- [ ] Only then submit a production change request; no deployment is authorized by this plan.

## 6. Explicitly prohibited during planning

- No SSH/remote host mutation, install, restart, stop, migration, cleanup or credential rotation.
- No running `deploy/install.sh`, `deploy/big-bang.sh` or `deploy/retire-legacy.sh` against SRV-DEB-05.
- No `RETIRE_LEGACY=1`, `docker compose down -v`, `docker system prune` or volume deletion.
- No production data in synthetic tests and no synthetic-to-LIVE promotion.
- No new cron, self-hosted runner or unrestricted Docker socket access.
- No assertion that Debian is healthy or deployed until a fresh host-side receipt proves it.
