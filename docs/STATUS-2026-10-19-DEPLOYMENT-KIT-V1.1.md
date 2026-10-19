# AIOps 2.0 — Status update: Deployment Kit V1.1

**Date:** 2026-10-19  
**Author:** Abdelhalim Talbi  
**Host audited:** SRV-DEB-05 (Debian 13)  
**Branch:** `chore/aiops2-deployment-kit-v1.1-status`

## Summary

The cumulative Deployment Kit V1.1 was transferred to the host and extracted. Its archive SHA-256 matched the locally produced artifact:

`3c22ef388abaea3263a38f3403221892f0e6b8b06e0d130bb8f39a5b5f4fd5cf`

The read-only runtime audit completed and confirmed the current AIOps 2.0 Compose labels and Temporal workflow visibility. The subsequent preflight **failed safely** because the Compose file recorded in the running core container's labels was not found at:

`/home/aiops/aiops2-v8-r4/00-Deployment/compose.yml`

This is a blocker to deployment, not permission to reconstruct or guess a Compose file. No databases were modified, no workflows were started, and no containers were restarted by this audit.

## Runtime facts from the captured audit

- Host: `SRV-DEB-05`, Debian 13.
- Existing Compose project label: `aiops2`.
- Core/worker reported working directory: `/home/aiops/aiops2-v8-r4/00-Deployment`.
- V2 Temporal container: `aiops2_temporal`; worker queue: `aiops2`.
- Workflow visibility observed in V2: `AIOpsRun` (1 execution) and `IncidentDecisionWorkflow` (17 executions).
- V2 namespace catalog query returned `default` and `temporal-system`; the kit's preflight expects `default`.
- Separate historical Temporal projects remain running and use namespace `aiops` with queues `aiops-v28` / `aiops-incidents`. Do not merge or redirect them by assumption.

## Immediate next actions

1. Locate and verify the actual Compose files recorded by Docker labels, including any overrides; record existence, hashes, and rendered service names without printing secret values.
2. Locate the V2 source/configuration tree and compare it with the GitHub repository; do not infer missing files from labels alone.
3. Review image availability and Docker daemon/containerd errors before attempting builds or service reconciliation.
4. Repair the kit's preflight only after the canonical path and Temporal namespace contract are verified against the actual runtime.
5. Run a plan-only deployment and inspect the exact service list; keep Temporal, PostgreSQL, MariaDB and other stateful services excluded.
6. Open a PR with the source/configuration kit, scripts, evidence and updated continuity notes. No direct main change.

## Product direction and safety invariants

AIOps 2.0 remains the target architecture. Reuse historical portal V1/V145 capabilities only after inspecting source, contracts, dependencies and tests. Temporal must preserve durable ordering/retries for core functions. ACME digital-twin and chaos campaigns must be deterministic and simulation-only by default. Policy/HITL gates remain independent of LLM recommendations. Keep PC11K5 fencing/ownership invariants unchanged. Missing or stale evidence is UNKNOWN; LIVE remediation stays fail-closed.

## Qualification labels

- **Archive integrity:** PASS (SHA-256 matched).
- **Read-only runtime audit:** completed; see the operator-provided terminal capture.
- **Preflight:** FAIL — canonical Compose path missing.
- **Deployment/reconciliation:** NOT RUN.
- **Build / container image integrity:** NOT QUALIFIED; the audit reported a containerd blob-not-found error.
- **Synthetic E2E:** NOT RUN.
- **Production qualification:** NOT QUALIFIED.

No secrets, .env files, database dumps, credentials, or production exports belong in this repository.
