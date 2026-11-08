# AIOps 2.0 — Change and Qualification Protocol

**Author:** Abdelhalim Talbi

## Before a change

- Identify target runtime/version, source branch/commit and production impact.
- Inspect current service state, repository status, relevant contracts and active dependencies.
- Create a timestamped backup of files/configuration to be changed; do not bundle secrets into Git or chat.
- Define preconditions, expected result, stop conditions and rollback procedure.
- Confirm DEMO/REPLAY/LIVE mode and credentials scope.

## Test evidence labels

1. **Source inspection:** code read; no execution implied.
2. **Static:** lint, type checks, static audit or contract-shape checks.
3. **Unit/contract:** isolated deterministic tests.
4. **Integration:** cooperating services in an isolated environment.
5. **Synthetic E2E:** full flow using explicitly synthetic events and data.
6. **Live verification:** actual deployed service/API verified; report timestamp, endpoint, status and redacted result.
7. **Production qualification:** approved test window, safety checks, observed results, audit trail and rollback readiness.

Always list failed, skipped and not-run tests. Expected output is not evidence of actual execution.

## Change and promotion gates

- No direct main changes: branch → tests → commit → pull request.
- No automatic merge unless separately authorized.
- No production restart/cutover as a side effect of documentation or source changes.
- No live mutation from synthetic/demo flows.
- High-risk actions require policy authorization and human approval where policy requires it.
- Check fencing/ownership, current preconditions, idempotency, effect evidence, verification and reconciliation.
- Test partial failure after external effect, timeout, duplicate delivery, worker restart, stale evidence and rollback failure.
- Keep all logs and reports secret-safe.

## Release/handover checklist

- [ ] Component and API contracts updated.
- [ ] Architecture and decision log updated.
- [ ] Reuse matrix and catalog updated.
- [ ] Automated tests and exact outcomes recorded.
- [ ] Version, changelog, manifest and hashes updated where applicable.
- [ ] Install/upgrade/rollback steps tested or explicitly marked untested.
- [ ] Cumulative ZIP includes required source/scripts/docs/evidence, without secrets or runtime databases.
- [ ] Commit and PR verified on GitHub.
- [ ] Next steps, unresolved risks and current runtime snapshot recorded in `docs/PROJECT-CONTINUITY.md`.


## Runtime inventory maintenance

After every material installation, upgrade, rollback, Compose change or service retirement:

1. Capture a read-only timestamped inventory on the affected host.
2. Record Compose project labels, working directories, all effective Compose files and SHA-256 hashes, container IDs/states/health, image tags **and immutable digests**, source commit/build provenance, published ports, restart policies, networks, mounts and volume ownership.
3. Reconcile observed state against the intended architecture and existing component catalog. Record drift and UNKNOWN fields explicitly; do not infer source ownership from container names or image tags.
4. Update the existing `docs/COMPONENT-CATALOG-AND-REUSE.md`, `docs/ARCHITECTURE-AND-BOUNDARIES.md` where topology changed, and `docs/PROJECT-CONTINUITY.md` in the same documentation change. Add a dated snapshot under `docs/operations/` when a full host-level capture is needed.
5. Attach exact commit/PR and relevant CI, integration, synthetic E2E or runtime evidence. Distinguish Docker running from application-ready and from qualified.
6. Preserve previous snapshots and decision-log history. Do not silently overwrite historical evidence.
7. Do not stop, remove, migrate, merge or retire runtime components/volumes as part of an inventory-only task. Require an approved change, backup, dependency review and tested rollback.

For the SRV-DEB-05 2026-11-08 snapshot, the capture is read-only and does not itself qualify any component or authorize cleanup. See [the recorded inventory](operations/SRV-DEB-05-INVENTORY-2026-11-08.md).


## Existing Debian cron reuse — mandatory controls

The default approach is to reuse and, if approved, extend an existing suitable Debian cron job in place. Do not install a duplicate scheduler or create a second inventory pipeline.

Before changing any job, perform read-only discovery of user/system crontabs, cron spool, systemd timers, referenced scripts, ownership, cadence, logs and execution receipts. Do not reveal environment values, credentials or tokens. Map the selected job to its exact script and GitHub publication mechanism.

An infrastructure inventory job must be observational only: no `docker exec`, Compose lifecycle commands, restarts, prune, database access or business/API mutations. Collect only metadata required for installation/function provenance, sanitize before publication, and upload a timestamped report plus checksum through an existing least-privilege mechanism. Do not grant a general runner unrestricted Docker socket access.

The existing GitHub-hosted daily `quality.yml` schedule at 02:23 UTC validates repository source and tests; it is not a Debian runtime inventory. PR #188 remains Draft because its proposed self-hosted runtime smoke uses `docker exec` and unrestricted Docker access; do not merge/install it as written. The six-hour PR #189 schedule is redundant and must not be duplicated.

A Debian job is not considered active/healthy until a recent timestamped execution receipt and successful GitHub publication are independently observed. The existing heartbeat gate must continue to report UNATTESTED/missing evidence as WARN or FAIL, never PASS.

For current findings and the no-new-cron decision, see [Project Continuity — 2026-11-08](PROJECT-CONTINUITY.md).


## Comparative qualification across development stacks

Use the existing `aiops-debian-reporter` and `aiops-publish-report` schedule as the single inventory/reporting pipeline; do not add a cron. Extend only after review and preserve its lock behavior. Keep the deployment poller and FS watcher separate.

The component comparison must use immutable image digests and exact source commits, Compose project/service ownership, contracts/dependency compatibility, implemented feature evidence and passing CI/contract/integration/E2E tests. Prefer the most advanced **usable and integrated** candidate, not the numerically newest tag. Unknown evidence is NOT_QUALIFIED. Retain all development stacks while comparing; no automated promotion, deletion, volume cleanup or database migration. Any later consolidation requires a separate reviewed change, backup and tested rollback.

Publish sanitized simulated-development inventory and feature/test evidence to GitHub with timestamped history. Do not publish credentials or authentication material, even if the environment contains only simulated data.


## Preservation-first qualification order (mandatory)

Before cross-version scoring or consolidation, preserve the development state deployed on SRV-DEB-05 during the preceding 48 hours. It takes precedence over undeployed GitHub candidates and older qualification stacks as the baseline for comparison. Then consider other installed/working Debian components, qualification/E2E candidates, undeployed branches/worktrees, and only lastly old duplicates.

The preservation gate requires a timestamped runtime snapshot, immutable image IDs/digests, Compose project/service/config sources, exact source commit and dirty state, effective configuration, network/mount/volume mapping, feature/test evidence, and verified backup plus rollback. Do not use tags or timestamps alone to infer provenance. If evidence is missing, mark UNKNOWN and preserve the artifact.

A replacement recommendation must prove usable feature gain, integration and contract/schema compatibility, passing relevant tests, operational readiness and rollback. Keep all environments intact during comparison. Deletion, volume cleanup, rebuild, migration, restart, deployment or promotion are separate changes requiring explicit approval after preservation is verified.


## 2026-11-08 — Two-stage preservation and qualification gates

For every component variant, enforce **G0 preservation** before **G1 technical qualification**. G0 requires an auditable backup of recent deployed Debian source, immutable images/digests, Compose overlays, local dirty worktrees, mounts/volumes/simulated data, and recovery/rollback checksums. Unknown recent host provenance => HOLD and preserve. G1 requires an exact SHA, documented implemented feature delta and parity, contract/API/schema compatibility, relevant exact-head targeted tests, integration/E2E evidence and no unresolved critical check failures. CI check-run counts alone do not meet G1.

After G0/G1, compare eligible candidates for the *same function* using integration 30, usable features 25, tests/reliability 20, Debian preservation 15, maintainability/rollback 10. These are weights only, not invented candidate scores. Prefer additive feature porting over replacing a recent installed build if that avoids regression.

At the 2026-11-08 GitHub check, #448 Twin Decimal metrics (operator-reported host qualification, source lineage) and #431 Worker V28 isolation (18 successful check runs, some repeated) are priority preservation/verification candidates. #443 Worker FS147 and #450 Core HITL are useful recent but unqualified cross-service candidates. #451 Twin isolation has a failed database-migrations check, #446 Worker Temporal guard has two failed database-migrations checks, and #449 FS147 release receipt has failed runtime-e2e and quality-build-package checks. #438 Portal frontend lacks its authenticated backend/E2E. No automated merge, promotion, deployment, cleanup or Debian claim is authorized by these results.
