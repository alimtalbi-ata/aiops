# AIOPS2 — Interface proof matrix (2026-11-16 05:00 Europe/Paris)

Status: **DRAFT / NO-GO LIVE**. Source of truth: PR #713, branch `integration/aiops2-convergence-20261114`, observed HEAD `931cd107439c2180acb143f9198ed84649443b3f`. This document is a review contract, **not** an execution or deployment receipt.

## Single backlog — WIP 3/3

| Order | Owner / contribution | Measurable acceptance | Negative case / evidence needed | Current decision |
|---|---|---|---|---|
| P0.1 | Core 3/5 #718 `5f8a3fb00882d7cbfc1ca164ed4bf19173e6d404` | Correct dedup and correlation with source/tenant identity; **0 cross-tenant joins** | Two tenants sharing service and incident identifiers must not correlate; conflicting/future/stale evidence -> UNKNOWN; attach test command, output, exact SHA | BLOCKED |
| P0.2 | Twin 1/5 #715 | SAN→STORAGE→SERVICE→Payments graph with source IDs, timestamp and freshness, impact only when supported | Missing edge, stale CMDB provenance, duplicate edge, cross-tenant reference -> UNKNOWN or reject; supply fixture and assertion results | BLOCKED |
| P0.3 | Policy 4/5 #716/#720 | Analyst citations resolve to immutable evidence; Critic independent; HITL DENY without effects | Forged digest/citation, self-declared critic independence, absent approval -> DENY_LIVE; supply negative tests and side-effect-free receipt | BLOCKED |

Cockpit #719 and ITSM are downstream only, not additional active WIP.

## Explicit interface handoffs (no inferred compatibility)

1. **Core → Twin**: require `tenant_id`, stable `incident_id`, canonical `service_id`, source event IDs, UTC observation timestamp, evidence references, dedup group and unknown-state semantics. Reject missing tenant/source identity; do not infer causality from shared service grouping.
2. **Twin → Analyst**: require path edges with CMDB authority, provenance identifiers, observed/expiry timestamps, and per-edge status. `SOURCED` in a fixture is not LIVE attestation. Unknown/stale path must never be rendered as confirmed Payments impact.
3. **Analyst → Critic → Policy**: require immutable citation IDs/digests, critic independence evidence external to the critic's own assertion, policy decision + rationale + HITL authorization proof. Missing proof -> `DENY_LIVE`, no external action.
4. **Policy → NOC/ITSM**: read-only representation of incident, uncertainty, citations, decision and next operator action. No route activation, ticket mutation, remediation or outbound effect until separately authorized.

## Collision and drift inventory

GitHub PR changed-file listings inspected 2026-11-16: #713 has 182 paths; #718 has 2; #715 has 3; #716 has 3; #720 has 3; #719 has 7. The incoming PRs use separate named files from each other and from the inspected #713 list; this is a **path-level observation**, not semantic/API compatibility. Incoming bases predate observed #713 HEAD. No merge, rebase, cherry-pick or competing edits to owner files.

## Risks / milestone gates

| Risk | Control |
|---|---|
| R1 cross-tenant join | negative isolation assertion, zero tolerance |
| R2 inferred impact | per-edge provenance/freshness, UNKNOWN fallback |
| R3 fake citations | independently resolve IDs/digests |
| R4 self-attested Critic | independently verify separation |
| R5 HITL bypass | fail-closed DENY and zero external effects |
| R6 CI false-green | check workflow conclusion **at exact SHA** |
| R7 base drift | compare contracts against current #713 HEAD |
| R8 owner collision | isolated files, owner review before wiring |

S1 correlation, S2 identity, S3 Twin, S4 Analyst, S5 Critic/Policy: **BLOCKED** pending executable negative proofs. S6 NOC, S7 ITSM: **NOT_TESTED E2E**. S8 release gate: **BLOCKED / NO-GO LIVE**.

## Next proof request and execution protocol

Core: publish exact SHA, `python -m pytest -q tests/test_aiops2_correlation_adversarial_contract.py`, stdout, and CI link. Twin: same for `tests/test_aiops2_twin_dependency_read.py`. Policy: same for `tests/test_aiops2_critic_negative_gate.py tests/test_aiops2_sandbox_chain_receipt.py`. Architect then compares schema/fixtures across boundaries, reruns the narrow tests in an isolated checkout if available, and records PASS/FAIL/BLOCKED/NOT_TESTED separately. **None of these commands was executed in preparing this document.** CI for this document's new SHA is NOT_TESTED until a terminal result is retrieved.

No new stack, cron, runtime, LIVE, SSH, Debian access or secret. DEMO/SIMULATION only. Rollback: close this draft and omit its sole new document.
