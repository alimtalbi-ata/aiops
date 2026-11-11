# AIOps 2.0 — Status update: Deployment Kit V1.1

**Date:** 2026-10-19  
**Author:** Abdelhalim Talbi  
**Host audited:** SRV-DEB-05 (Debian 13)  
**Branch:** `chore/aiops2-deployment-kit-v1.1-status`

## Summary

The cumulative Deployment Kit V1.1 was transferred to the host and extracted. Its archive SHA-256 matched the operator-provided artifact:

`3c22ef388abaea3263a38f3403221892f0e6b8b06e0d130bb8f39a5b5f4fd5cf`

The read-only runtime audit completed and confirmed the current AIOps 2.0 Compose labels and Temporal workflow visibility. The subsequent preflight **failed safely** because the Compose file recorded in the running core container's labels was not found at:

`/home/aiops/aiops2-v8-r4/00-Deployment/compose.yml`

No databases were modified, no workflows were started, and no containers were restarted by the captured audit.

## Additional source-level findings

GitHub source inspection on 2026-10-19 confirms:
- The Temporal worker intentionally blocks LIVE stages until qualified live adapters exist; it does not create evidence on the LIVE guard path.
- DEMO/REPLAY/STORY use synthetic evidence and must stay visibly synthetic.
- The general Core event endpoint updates stage state for BLOCKED events but does not, in the inspected implementation, consistently reconcile the canonical Run lifecycle to BLOCKED. This is a source-level finding, not a host runtime test.
- The existing qualification script checks container presence and selected health endpoints; it does not by itself prove retry/idempotency, ACME twin determinism, fencing, partial-effect recovery or rollback.
- Existing architecture/decision records require one canonical runtime, Portal→Core-only state mutation, Temporal-owned progression, append-only evidence, fail-closed LIVE actions, and PC11K5 fencing/ownership preservation.

## Runtime facts from the captured audit

- Host: `SRV-DEB-05`, Debian 13.
- Existing Compose project label: `aiops2`.
- Core/worker reported working directory: `/home/aiops/aiops2-v8-r4/00-Deployment`.
- V2 Temporal container: `aiops2_temporal`; worker queue: `aiops2`.
- Workflow visibility observed in V2: `AIOpsRun` (1 execution) and `IncidentDecisionWorkflow` (17 executions).
- V2 namespace catalog query returned `default` and `temporal-system`.
- Separate historical Temporal projects remain running and use namespace `aiops` with queues `aiops-v28` / `aiops-incidents`. Do not merge or redirect them by assumption.

## Immediate next actions

1. Run `deployment-kit/v1.1/scripts/discover-compose.sh` on SRV-DEB-05 and return its report (not .env values).
2. Compare labeled Compose files, overrides, Git-tracked source and backups by hashes; identify the real deployment source of truth.
3. Investigate the reported containerd blob-not-found error and verify image IDs/digests.
4. Fix general BLOCKED Run lifecycle reconciliation with deterministic tests before enabling any new workflow progression.
5. Extend qualification with Temporal retry/idempotency, deterministic ACME twin replay, and failure injection for event append/activity crash, stale evidence, partial external effect, HITL resume and rollback failure.
6. Repair the kit preflight only after canonical paths and the Temporal namespace/queue contract are verified.
7. Run plan-only deployment and inspect the exact service list; keep Temporal, PostgreSQL, MariaDB and other stateful services excluded.
8. Do not enable LIVE remediation until real evidence, CMDB/RAG/analyst/critic, HITL, remediation, verification, rollback and reconciliation adapters pass qualification.

## Qualification labels

- **Archive integrity:** PASS (SHA-256 matched).
- **Read-only runtime audit:** completed based on operator-provided terminal capture.
- **GitHub source inspection:** completed for architecture, decisions, Core, Worker, Policy and current tests.
- **Preflight:** FAIL — canonical Compose path missing.
- **Deployment/reconciliation:** NOT RUN.
- **Build / container image integrity:** NOT QUALIFIED; the audit reported a containerd blob-not-found error.
- **Synthetic E2E:** NOT RUN.
- **Production qualification:** NOT QUALIFIED.

No secrets, .env files, database dumps, credentials, or production exports belong in this repository.
