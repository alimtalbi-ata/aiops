# AIOPS2 merge, test, deployment and Debian change plan

Status: **PLAN ONLY — HOLD / NO_GO**. This document authorizes no merge, production change, Debian command, service restart, migration, or deployment. Execute each phase only after its gate is reviewed and explicitly approved by the system owner.

## 0. Current verified baseline (2026-11-10)

- PR #543 is OPEN, DRAFT, not merged; head `1a6d0b79a932ca813dbdd73ea333e915937d1b6f`, base branch `agent/ci-postgres16-dr-client-20261110`. It is stacked on #540.
- PR stack observed: #537 -> #539 -> #540 -> #543. All four are OPEN and DRAFT. #537 targets `fix/portal-read-error-publish-20261110`; #539 targets #537's head branch; #540 targets #539's head branch; #543 targets #540's head branch. #540 currently reports `mergeable=false`; #537/#539 report `mergeable=true`. Recheck all PR metadata and exact head/base SHAs immediately before any merge.
- Latest tested #543 head: `1a6d0b79a932ca813dbdd73ea333e915937d1b6f`. AIOps quality gates run #8550 (run ID `42891135959`) and isolated V2.8 #2160, V2.12.8 #1873, V2.12.9 #1873 completed SUCCESS. All six quality jobs succeeded: quality-build-package, database-migrations, mariadb-dr-rehearsal, migration-runner-upgrade, runtime-e2e, release-kit.
- The new `test_model_evaluation_postgres_integration.py` step succeeded against the disposable PostgreSQL 16 CI service. It exercises concurrent same-ID insert/replay, one-row persistence, stable fields and HTTP 409 for changed payload. This is CI integration evidence, not production database qualification.
- Existing CI artifacts are synthetic/disposable. Runtime E2E uses deterministic provider and no live effects. PostgreSQL logical DR and MariaDB logical DR do not qualify Temporal MariaDB named-volume backup/restore.
- Portal operational projection helper remains deliberately disconnected from HTTP routes. There is no proven end-user actor/tenant identity provider or tenant-scoped production query in the current contract. Chromium integrated acceptance and Debian environment qualification are not evidenced.

## 1. Merge sequence — no batch merge

**Do not merge #543 first.** Preserve the stack's ancestry and merge only one PR at a time, from bottom to top, after exact-head checks and independent review:

1. Establish the intended base/ownership of #537 and verify prerequisite PRs/commits #523, #524 and #533 are already present in the target lineage. #537 is not a direct-to-main PR; do not retarget it casually.
2. Review and merge #537 only after its portal timeout/stale-response/secret-redaction tests pass on its exact head, reviewers approve, and its base ancestry is confirmed.
3. Rebase/update #539 onto the resulting #537 merge SHA; rerun intelligence contract tests and the full required checks. Merge #539 only after review and all required checks.
4. Rebase/update #540 onto the resulting #539 merge SHA; resolve its current mergeability=false state; rerun PostgreSQL 16 DR and all required checks. Merge #540 only after clean mergeability and approval.
5. Rebase/update #543 onto the resulting #540 merge SHA; rerun full CI including PostgreSQL idempotency integration, portal guards and JS tests. Keep #543 DRAFT until its scope is agreed. It is documentation plus a disconnected projection policy and must not be represented as live actor/tenant integration. Merge only if the owner explicitly accepts documentation/policy helper scope and all branch protections pass.
6. After each merge, record merge SHA, source SHA, checks, reviewer and rollback reference. Stop immediately on conflict, changed ancestry, failing check, new review finding, or unexpected file scope. Do not enable auto-merge for the stack.

## 2. Pre-merge test gates

- GitHub required checks green on the exact head SHA and current target base; no stale green checks from ancestor commits.
- Python compile and all relevant unit/contract/security tests; Node operational-state tests.
- PostgreSQL 16 migration chain plus concurrent evaluation-ledger replay integration; verify one row, same payload, deterministic first/replay responses, 409 on changed payload.
- PostgreSQL logical DR restore, hash checks and corruption negative control.
- MariaDB logical DR restore, integrity and corruption negative control.
- Separate Temporal MariaDB **named-volume** backup/restore rehearsal, checksums, service metadata, documented RPO/RTO and isolated recovery. Until passed, keep that storage layer NOT_QUALIFIED.
- Portal browser matrix on the integrated deployed candidate: anonymous, expired session, forged actor/tenant headers, authorized tenant, cross-tenant denial, verified empty, stale/future/missing timestamp, upstream timeout/error, redaction, retry/cancel and stale-response race. Capture Chromium traces/screenshots and server-side audit evidence. A disconnected helper or JS unit test is not acceptance.
- Security review of identity source, membership/revocation, cache partitioning, query-level tenant filter, service-token boundaries and data minimization. No route exposure until these are implemented and tested.

## 3. Deployment plan — separate staging then production

**Stage A: staging rehearsal**
- Identify exact Debian host, owner, environment, deployed commit, Compose project, service names, data volumes, firewall/DNS, secret-management path and maintenance window. Do not infer host identity from this repository.
- Confirm out-of-band access, monitoring and on-call owner. Verify free disk, Docker/Compose versions, service health and backup restoreability.
- Take consistent database backups and volume snapshots; record hashes, timestamps, encryption/location, retention and restore operator. Prove rollback restore in isolated staging before change.
- Build immutable images once; pin image digests and migration bundle. Generate SBOM/signature if configured. Promote the exact tested digests; do not rebuild between test and deploy.
- Deploy to staging only with explicit approval; run additive/expand migrations first, deploy one service at a time, health/readiness checks, smoke tests, integrated Chromium suite, API compatibility and log/metric checks. No destructive migration or live-effect enablement.
- Observe agreed soak window and error/latency/resource thresholds. Abort on auth/scope anomaly, data mismatch, failed health, elevated 5xx, migration warning, backup issue or unexplained restart.

**Stage B: production Debian change**
- Require staging sign-off, change ticket, named operator and approver, maintenance window, tested backup/restore, exact image digests, migration plan, rollback command sequence and customer impact notice.
- Confirm SSH/console access and host identity independently. Record pre-change commit/image digest, `docker compose ps`, health, disk, database migration version, volume inventory and monitoring baseline. Do not print secrets.
- Apply only reviewed additive migrations and approved service changes. No blanket `docker compose down -v`, volume deletion, prune, reset, or manual DB edits.
- Deploy canary/one instance where topology supports it; otherwise a controlled service-by-service rollout. Verify readiness, authenticated tenant-scoped requests, cross-tenant negative tests, Chromium acceptance, background worker/Temporal health, DB connections and audit logs.
- Keep live AI/provider effects and external action execution disabled unless separately approved and tested. No automatic promotion from DEMO to LIVE.
- Soak, compare metrics to baseline, validate backup after deployment, then close change with evidence and operator/approver sign-off.

## 4. Rollback and stop conditions

- Stop rollout on any failed health check, unauthorized/cross-tenant response, missing scope/freshness evidence, migration failure, data integrity discrepancy, Temporal workflow backlog/regression, elevated 5xx/latency, unexpected side effect, or failed backup.
- Roll back application images to recorded immutable digests first when schema compatibility permits. For schema/data rollback, use the rehearsed restore procedure and explicit DBA approval; never improvise destructive down-migrations.
- Restore database/volumes only from verified pre-change backups using the documented recovery runbook. Preserve logs and evidence for incident analysis.
- Do not continue if rollback cannot be demonstrated before the maintenance window.

## 5. Explicit outstanding blockers

1. Trusted end-user identity and tenant membership/revocation integration.
2. Tenant-filtered source query and integrated Chromium acceptance.
3. Temporal MariaDB named-volume DR qualification.
4. Exact Debian host/environment inventory, backups and restore rehearsal.
5. Stacked PR review, current mergeability and exact-head checks at each sequential merge.
6. Explicit owner approval for each merge and each staging/production change.

**Current release decision remains HOLD / NO_GO.** This is a sequencing and acceptance plan only; no PR was merged, no deployment was initiated, and no Debian host was accessed or changed.
