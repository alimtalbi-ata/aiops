# GLPI/Core/Copilot merge and Debian rollout plan

Status: PLANNING ONLY — NOT APPROVED FOR MERGE OR PRODUCTION EXECUTION.
Related: PR #520, issue #519.
Planning baseline: branch head f99aa8f354818d0b073b00744628432df34331ba; main base 0e232c9fdf4a519de36ba8035b506621854e0277.

## 0. Current facts and immediate merge risk
- PR #520 is OPEN and DRAFT. No submitted reviews were found at planning time.
- The branch compares as 165 commits ahead of main, 0 behind, with 39 changed files in the PR diff. This is too large a history delta to merge blindly. Before any merge decision, review the complete commit range, identify unrelated changes, confirm the intended merge strategy, and preferably split unrelated work into separately reviewable PRs.
- Latest confirmed full CI: run #8549 SUCCESS on commit 20dec0b006c9bf314ea643c9f7da65ed1e67aaf6. The documentation-only head f99aa8f354818d0b073b00744628432df34331ba has no workflow run reported in the current check. Require a fresh green run on the exact final head.
- No positive authenticated GLPI 11.0.9 + MariaDB 11.4 E2E exists. GLPI/Core HTTP tests use offline fakes; PostgreSQL nonce replay has a real ephemeral CI integration.
- No trusted end-user actor/tenant ACL provider or deployed signed xref event source has been established. Core internal token is service authentication, not end-user identity.
- Ticket-specific Copilot routes remain unmounted. Generic /api/copilot remains fail-closed. Do not mount either historical ticket-specific path in this rollout.
- The nonce SQL is explicitly optional and has not been applied. It creates aiops.glpi_xref_consumed_nonces; no production schema change is authorized by this plan.
- No Debian host inspection, worktree status, service inventory, production backup, or production connectivity check has been performed as part of this planning task. Assume nothing about host cleanliness or live versions.

## 1. Merge readiness gates (all required)
### Gate A — scope and review
- Audit all 165 commits in the branch range against main; explain every commit and changed path.
- Confirm the 39-file diff is the intended deliverable; split unrelated commits/features into separate PRs.
- Obtain at least one independent code/security review and resolve every blocking thread.
- Keep PR #520 Draft until gates B–E pass; do not mark ready merely because earlier CI passed.

### Gate B — identity, authorization, and data trust
- Implement or integrate a real server-side principal resolver from a trusted issuer/gateway. Verify signature, issuer, audience, expiry/not-before, key rotation and revocation.
- Resolve actor and tenant membership server-side. Bind actor+tenant+action+resource to an authoritative ACL decision, including GLPI instance/entity scope and Core Run scope.
- Never treat Portal shared bearer, AIOPS_INTERNAL_TOKEN, ADMIN_TOKEN, browser headers, ticket text, or caller-provided *_verified booleans as proof of user/resource authorization.
- Wire real signed-event issuance/source, issuer/audience verification, durable nonce replay store and independent GLPI/Core service credentials.
- Keep authorization fail-closed and emit auditable decision metadata without logging secrets.

### Gate C — exact-head CI and tests
- Run the full quality workflow on the final proposed merge SHA; all jobs must pass.
- Add tests for missing/invalid/expired principal, issuer/audience mismatch, key rotation, revoked membership, cross-tenant/entity denial, missing/duplicate/expired/replayed xref, mismatched Core/GLPI raw readbacks, upstream timeout and cleanup failure.
- Prove browser headers cannot alter principal or ACL results.
- Preserve /itsm, /api/portal/itsm, existing Portal navigation, generic Copilot refusal, and hourly automations.
- Keep ticket-specific Copilot fastpaths unmounted until a separate reviewed change wires the real ACL and canonical readback chain.
- Keep Copilot/HITL inactive; no proposal creation or execution in this candidate.

### Gate D — isolated positive E2E
- Provision disposable GLPI 11.0.9 + MariaDB 11.4 and disposable Core PostgreSQL in CI/staging, with ephemeral credentials and synthetic data only.
- Exercise authenticated GLPI ticket GET, entity check, signed xref verification, nonce replay rejection, independent Core Run GET and raw identity comparison.
- Exercise timeout, mismatch, duplicate association, wrong tenant/entity and replay cases.
- Do not use Debian production GLPI or its database for qualification.
- Ticket CREATE/PUT/writeback is OUT OF SCOPE for this read-only candidate. Any future writeback requires a separate PR, explicit authorization/HITL policy, idempotency/concurrency tests, and its own approval.

### Gate E — operational readiness
- Record exact target Debian host, OS, Docker/Compose versions, current commit/image digests, service names, health endpoints, disk capacity, DB size and maintenance window.
- Inspect git status and preserve every dirty/untracked file. Never reset, clean, checkout over, or overwrite unknown worktree state.
- Verify secret source and rotation plan without printing secret values.
- Prepare and test a backup/restore path for PostgreSQL and deployment configuration.
- Confirm rollback artifacts and operator access before any change.

## 2. Proposed merge sequence (not yet authorized)
1. Complete scope audit and split unrelated commits. Do not merge the 165-commit branch range without that audit.
2. Obtain independent security review and close all review threads.
3. Produce a fresh green CI run on the exact final PR head.
4. Complete isolated authenticated read-only GLPI/Core E2E.
5. Obtain explicit human approval for PR readiness and merge. Prefer a reviewed merge strategy preserving traceability; do not squash/rebase until commit-range audit determines the correct strategy.
6. Merge only the read-only candidate. Keep Copilot ticket routes unmounted and write operations disabled.
7. Re-check main CI and build an immutable image/artifact from the merge SHA. Record digest and SBOM/provenance if available.

## 3. Proposed Debian rollout sequence (read-only only; not executed)
### Pre-change
- Announce maintenance window and freeze concurrent deploys.
- Capture git status --short, current deployed SHA, container image IDs/digests, docker compose ps, redacted Compose configuration, health responses, disk/memory, and current DB schema version.
- Preserve dirty worktrees and local config; never print .env, tokens, passwords, or private keys.
- Take a PostgreSQL custom-format backup (pg_dump -Fc) and verify the archive can be listed/restored to an isolated database. Back up deployment manifests/config with secrets excluded or encrypted.
- Verify rollback image(s), backup location, checksums, and access to the previous known-good deployment.

### Stage 1 — deploy no-op/read-only code
- Deploy only after merge approval and E2E gates. Use an immutable image built from the approved merge SHA.
- Do not change GLPI data, do not enable ticket-specific Copilot routes, do not enable HITL, and do not enable Core/GLPI writes.
- Do not run the nonce SQL migration until the production nonce consumer and real signed-event/ACL provider have been reviewed and enabled under a separate migration approval.
- Start one service at a time using the repository actual deployment topology; verify health/readiness and logs with secrets redacted.
- Confirm /itsm, /api/portal/itsm, generic /api/copilot refusal, Portal navigation and hourly automation behavior.

### Stage 2 — observe and hold
- Observe error rates, auth denials, upstream timeouts, session cleanup, DB connections, CPU/memory, and scheduled automation runs for an agreed observation window.
- Compare before/after route responses and confirm no unexpected GLPI/Core writes.
- Keep the previous image and database backup available. No automatic progression to Copilot/HITL.

### Rollback
- Stop rollout and route traffic back to the previous immutable image if health, auth, cleanup, latency, or regression gates fail.
- Restore prior image/config; do not use docker compose down -v.
- Do not automatically drop the nonce table or delete nonce rows during rollback; preserve replay/audit safety. If a migration is ever applied, schema rollback requires a separately reviewed migration plan and evidence that no deployed code depends on it.
- Verify Portal routes, hourly automation, and service health after rollback; record exact deployed SHA and incident evidence.

## 4. Separate future phases — require separate approvals
- Phase 2: real actor/tenant identity provider and resource ACL integration.
- Phase 3: signed xref event producer and production nonce persistence.
- Phase 4: enable read-only ticket-specific GLPI → Copilot context behind ACL, canonical signed association and dual readback, with HITL remaining PROPOSED only.
- Phase 5: any GLPI writeback or HITL execution in a separate PR with explicit human approval, idempotency and concurrency safeguards, isolated E2E, and independent rollback plan.

## 5. Current decision
NO-GO for merge, Debian deployment, schema migration, GLPI writes, Copilot route activation, or HITL.

GO only for planning, code review, scope audit, isolated CI/E2E preparation, and gathering the missing deployment facts. This document is a runbook proposal, not deployment authorization.
## 6. Commit-range and target-host audit — 2026-11-10

### Commit range reviewed

- GitHub compare now reports `main...feat/glpi-copilot-xref-guard-20261110`: 166 commits ahead, 0 behind, 39 changed paths. Merge base/main SHA: `0e232c9fdf4a519de36ba8035b506621854e0277`.
- The commit list is a focused, same-day GLPI read-only/security hardening sequence, not an obvious unrelated 166-commit product feature dump. Message-prefix classification of the 166 commits: 27 feature/security, 37 fix, 79 test, 18 CI, 5 docs. Most commits are narrow test/fix pairs that progressively harden canonical identity validation, HMAC xref verification, nonce replay, Core/GLPI GET-only transport, GLPI 11 session cleanup, and fail-closed Portal route policy.
- The 39-file PR diff consists of the quality workflow, 15 shared GLPI/Core adapter modules, 4 documentation/SQL paths, and 19 test modules. The SQL file is an optional, unapplied schema proposal.
- This substantially reduces the concern that the branch is mixing unrelated application features. It does not remove the need for commit-level review: 166 commits are unusually granular, all commits are unsigned per GitHub commit metadata, and the code still lacks a real actor/tenant ACL provider and positive authenticated GLPI E2E. Consider a single reviewed merge or a clean focused follow-up PR only after the full diff and commit history are independently reviewed; do not rewrite history or discard tests merely to reduce commit count.
- Latest exact-HEAD CI is now available: run #8556 on `bb76fcd454647130243b1582b3e326417eed613a`, all three jobs SUCCESS (policy-and-static, Core/PostgreSQL/NOC real integration, Grafana real integration). This qualifies the configured CI scope, not live Debian or GLPI positive E2E.

### Target Debian host — documentation baseline found

- The project continuity record identifies `SRV-DEB-05`, Debian 13, working root `/home/aiops`. This resolves the previously open target-host question at the documentation level; it is not a live host confirmation.
- The latest supplied host inventory is dated 2026-11-08, not a fresh 2026-11-10 preflight. It records 78 containers (59 running, 18 exited, 1 created), 5 Compose projects, 18 networks and 59 volumes. Many containers have no healthcheck; some exited rollback/before-metrics containers were reported unhealthy. One metrics-cutover Compose source referenced a missing temporary /tmp file. Some container names do not match Compose project labels. Do not infer current state from this snapshot.
- Observed projects: `aiops2-demo-observability`, `aiops2-e2e-v1`, `aiops2-metrics-cutover`, `aiops2-rebuild`, `aiops2-v27-qual`. Keep their distinct databases, volumes, qualification stacks and rollback artifacts intact until exact ownership and preservation are verified.
- The inventory recorded GLPI `glpi/glpi:11.0.9` and MariaDB `11.4` images in the rebuild project, plus Core PostgreSQL 16. This is image-tag evidence from the dated snapshot, not proof of current live versions, successful connectivity or functional qualification.
- The documented existing `aiops` user crontab has three per-minute flock-guarded jobs (deployment poller, reporter, publisher) and a 10-minute FS watcher. The preferred inventory/reporting path is the existing reporter → publisher. Do not create another cron, duplicate inventory agent, or invoke/modify the deployment poller. Its ability to execute approved deployment scripts makes it a separate deployment control plane.
- The reporter does not collect image digests, Compose labels, source commits, mounts, or feature/test evidence. The deployment plan therefore requires a new read-only capture to enrich evidence, but it must be designed as a reviewed extension of the existing reporter and must preserve lock behavior, redaction and least privilege.
- The supplied inventory explicitly says the root crontab was not inspected, report generation/publication success was not proven, and no application APIs/databases were queried. Exact 48-hour runtime chronology remains UNKNOWN.

### Operational access limitation

No SSH, shell, Docker, or Debian host connector is available in this session. No live command has been run on SRV-DEB-05; no current git status, container digest, Compose hash, DB backup, restore test, cron receipt or health endpoint has been observed. The next on-host step must be a read-only preflight executed by an authorized operator or an approved host connector, with output sanitized before sharing.

### Updated decision

- Commit-scope audit: substantially completed at message-category and diff-path level; independent security review remains required.
- Exact-head CI: PASS (#8556, 3/3).
- Target host: documented as SRV-DEB-05 / Debian 13 / /home/aiops; current live state unverified.
- Merge: still HOLD pending independent review and isolated authenticated positive E2E.
- Debian: HOLD pending fresh preservation inventory, verified backups/restores, current health and rollback readiness.
- No migration, restart, deployment, GLPI write, Copilot activation or HITL execution is authorized by this plan.
