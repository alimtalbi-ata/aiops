# AIOPS2 integration checkpoint — 2026-11-16 11:17 CET

Scope: **DEV documentation only**, no runtime access. Integrator 5/5. Canonical integration target: PR #713, branch `integration/aiops2-convergence-20261114`. This checkpoint was created from exact PR #713 HEAD `91551be28bc1383062669ef48d9c29aff6a83718`; **do not apply previous CI results to this HEAD**.

## Single ordered P0 backlog (WIP 3/3)

| Order | Owner / PR | Inspected head | Required product acceptance | Current gate |
|---|---|---|---|---|
| 1 | Core/correlation #718 | `5f8a3fb00882d7cbfc1ca164ed4bf19173e6d404` | Tenant/actor/source-event stable identity, no cross-tenant join, deterministic duplicate handling, trace Event→Incident→Run→Evidence | BLOCKED: no exact-head integrated acceptance proof |
| 2 | Twin #715 | `3da16e9177bf6afbacfd79742b7f910663e95c4d` | SAN→storage→Payments graph, edge authority, observation timestamp, age bound, source-backed blast radius; stale/missing/cross-tenant edge→UNKNOWN | BLOCKED: no authenticated CMDB/runtime attestation |
| 3 | Analyst/Critic/RAG #716 and #720 | `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`, `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | Evidence receipt and citation integrity, independent Critic authority, no positive policy from generated text, HITL deny→zero effect | BLOCKED: no end-to-end authority proof |

NOC #719 and ITSM follow these three gates; do not open a fourth P0.

## Interface acceptance / evidence handoff

1. **Core→Twin:** versioned tenant/CI/service identifiers and event time; prohibit inferred joins across tenant; output UNKNOWN when xref or source authority missing. Test cross-tenant, duplicate, stale and mismatched identity with machine-readable reason codes.
2. **Twin→Analyst:** separate observed edge, inferred impact and business criticality; include `source_ref`, `observed_at`, `as_of`, tenant and maximum age. Missing provenance cannot be converted to CONFIRMED impact.
3. **Analyst→Critic→Policy/HITL:** cited evidence must resolve to same-tenant immutable receipts; Critic must be independently validated. A model assertion, synthetic receipt or approval text is not an authorization. Missing fencing, ownership, preconditions or explicit human decision must deny effects.
4. **NOC/ITSM:** read-only projection with UNKNOWN and blocked reasons; do not claim ticket creation or runtime reconciliation from fixtures.

## Integration drift and test discipline

PR #713 is DRAFT and reported non-mergeable on inspection. Contributor PR base SHAs are different from current #713 HEAD; a green job on an older SHA cannot qualify the convergence candidate. Exact-head CI for this checkpoint: **NOT_TESTED** until a completed run is observed. Local tests: **NOT_TESTED**. Synthetic source inspection is not LIVE evidence.

Earlier quality workflow failures were traced in the integrator handoff to the `Daily quality schedule contract` check and escaped newline assertion in `tests/test_quality_schedule_contract.py`. This is a **diagnostic hypothesis requiring a verified fix and exact-head rerun**, not permission to alter the shared test file in this PR. Core/CI owns the change; no new workflow schedule or cron.

## Risk register R1–R8

| Risk | Gate / mitigation |
|---|---|
| R1 cross-tenant identity leakage | Reject cross-tenant joins; zero accepted adversarial cases |
| R2 duplicate event amplification | Stable source identity and deterministic idempotency |
| R3 unproven business impact | UNKNOWN unless authoritative and fresh edge provenance |
| R4 fabricated/stale RAG citation | Reject unresolved, stale or wrong-tenant receipts |
| R5 Critic self-attestation | Independent Critic validation required |
| R6 unauthorized HITL/Policy effect | Fail-closed and verify zero side effects |
| R7 CI/base drift and concurrent edits | Exact head/base/diff/check matrix; separate owner paths |
| R8 simulation mistaken for LIVE | Fence DEMO/SIMULATION; LIVE NO-GO |

## Milestones S1–S8 (conservative)

S1 canonical identity: BLOCKED. S2 correlation: BLOCKED. S3 Twin impact: BLOCKED. S4 evidence/Analyst/Critic: BLOCKED. S5 Policy/HITL: BLOCKED. S6 NOC projection: NOT_TESTED end-to-end. S7 ITSM journey: NOT_TESTED end-to-end. S8 release/LIVE: BLOCKED / NO-GO.

## Next owner actions and rollback

Core/CI: isolate and correct existing quality assertion on owned branch, execute targeted test and exact-head CI, then publish commands/logs. Twin: deliver same-tenant fresh and negative UNKNOWN receipts. Policy: deliver independent Critic and zero-effect refusal evidence. Integrator: re-evaluate changed paths and contract compatibility on the resulting SHAs; no merge, rebase, cherry-pick or deployment. Rollback: revert only this documentation commit after review. No V1 :7777, V30 :7788, Debian, SSH, LIVE or secret access.
