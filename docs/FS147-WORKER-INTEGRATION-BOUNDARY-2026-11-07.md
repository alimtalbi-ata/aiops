# FS147 Worker — proposed integration boundary (2026-11-07)

Status: CODE contract only; no claim of Debian execution, authenticated HTTP, CI PASS, or GLPI mutation. Source: FS364. This proposal does not modify Core-owned contracts or Portal FS1097/FS1113.

## Invocation
Input: tenant_id, actor_id, incident_id, run_id, ticket_id (integer 147), mode=DEMO; authenticated principal must be checked by every service. STOP_AUTO is checked before claiming or calling services. Reject LIVE and mismatched identities.

Core-owned interface proposal: atomic durable claim(tenant, incident, run, ticket, idempotency_key), returning CLAIMED, DUPLICATE, or UNKNOWN; never interpret UNKNOWN as permission to retry effects. Reconciliation should read existing run/evidence records before retrying a claim. No Worker-generated ticket or RUN identifiers.

Bridge-owned interface proposal: authenticated read-only observation of /fs-lab with exact df/du/ls allowlist, source=fs-lab-bridge-readonly, evidence_id, collected_at timezone-aware, filesystem=/fs-lab, read_only=true, used_percent finite 0..100, matching scope and optional provenance (host/container/image digest, command exit codes, per-command SHA256). Accept only evidence within 5 minutes, with at most 30 seconds future skew. Require actual command results and bridge attestation before production qualification; metadata alone is not evidence of execution.

Analyst and Critic outputs must carry the exact tenant/actor/incident/run/ticket/evidence identity. Findings must be nonempty; Critic state must be PASS. Policy must be independently authenticated and scoped; only PASS+SIMULATE can complete a diagnostic NO_EFFECT. All other decisions fail closed, including EXECUTE, refusal, missing fields and timeout.

## Transport and recovery
Proposed per-stage client deadlines: bridge 5 s, Analyst 15 s, Critic 15 s, Policy 10 s, overall 50 s. Enforce deadlines at transport layer; exceptions and HTTP 408/429/5xx become UNKNOWN/NO_EFFECT and are not retried blindly. Persist per-stage state and immutable evidence hash in Core before advancing (Core owner approval required). A retry with the same run_id must read the existing durable state and never duplicate external effects. No GLPI write, file mutation, truncate, SAN, HITL acceptance, or RESOLVED transition is in this Worker scope.

## Qualification
CODE: run `python -m pytest -q tests/test_fs147_resume_refusal_contract_20261107.py` and existing FS147 tests. CI: record workflow, commit SHA and result. HÔTE: independently verify deployed image SHA, credentials, endpoints, bridge command outputs and Core claim. EXÉCUTÉ: record one fresh ticket147/run_id/evidence_id chain and negative tests against authenticated non-production services. Do not claim E2E until all four evidence layers are present.
