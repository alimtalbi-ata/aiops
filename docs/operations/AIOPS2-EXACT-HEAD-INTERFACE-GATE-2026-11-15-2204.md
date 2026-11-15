# AIOPS2 — exact-head interface gate / 2026-11-15 22:04 CET

**Scope:** DEV documentation only; one candidate `integration/aiops2-convergence-20261114`. No merge/deploy/host changes. LIVE **NO-GO**, synthetic results must be labeled DEMO/SIMULATION. Unattested = UNKNOWN. Revert this document's single commit to roll back.

## Single P0 queue (WIP 3/3)

| Order | Accountable / reviewer | PR / exact HEAD | Evidence on exact HEAD | Business gate / next action |
|---|---|---|---|---|
| 1 Correlation | Core 3/5 / Architect 5/5 | #718 `1f73d0e33a04a9cd9ad026b8b1249101323619bb` | adversarial 43757038205 PASS; synthetic 43757038235 PASS; quality 43757038219 FAIL | zero cross-tenant joins; preserve event/source IDs, timestamps and evidence lineage; Core owns test/workflow mismatch; BLOCKED |
| 2 Twin business impact | Twin 1/5 / Core 3/5 | #715 `3da16e9177bf6afbacfd79742b7f910663e95c4d` | synthetic 43742358029 PASS; quality 43742358010 FAIL | SAN→storage→Payments impact with graph edge provenance, freshness and UNKNOWN on missing edge; BLOCKED |
| 3 Analyst/Critic/RAG | Policy 4/5 / Architect 5/5 | #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`; #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | #716 quality 43732445942 FAIL, synthetic 43732446134 FAIL; #720 synthetic 43737651757 FAIL, quality 43737651704 FAIL | independently checkable citations, independent Critic and fail-closed HITL, no external effect; BLOCKED |

Downstream **not fourth WIP:** UX 2/5 #719 `bdaccaba59e338ac181d64ae205980167443bfe1`, synthetic 43758071637 PASS, quality 43758071639 FAIL. NOC and ITSM consume validated canonical contracts only.

Integration parent #713 `ec3bfbbae3272de47ba5d72b8b496378b1064baa` is DRAFT, targets main, mergeability not qualified. No PR-triggered runs returned for that exact HEAD in the queried first page; **CI NOT_TESTED** rather than PASS.

## Interface compatibility / ownership

1. **Correlation → canonical Incident:** immutable `tenant_id`, `source`, `source_event_id`, `observed_at`, `incident_id`, `evidence_refs`; reject absent tenant and cross-tenant join. Core owns canonical identity; Twin must not re-key.
2. **Incident/CI → Twin:** scoped CI/service identity and as-of timestamp; each edge includes provenance/freshness. Missing/contradictory topology => `UNKNOWN`, never zero impact or fabricated Payments outage. Twin owns graph read; Core owns authoritative xref.
3. **Twin/Evidence → Analyst/Critic:** evidence reference IDs, source timestamps and mode travel unchanged; Critic challenges claims and citations independently. Policy owns deterministic gate; LLM output cannot authorize action.
4. **Policy → UX/ITSM:** `mode`, `decision`, `approval_state`, `effect_allowed`, `audit_refs`; absent approval or stale evidence => no effect. UX renders read-only; no direct DB writes.

Changed-file scan: #715, #716, #718, #719, #720 each own distinct paths, but #713 already changes central `scripts/aiops2_event_correlation.py`, `scripts/aiops2_digital_twin_impact.py`, `scripts/aiops2_analyst_critic.py`, `scripts/aiops2_noc_decision.py` and quality workflows. Integrate via reviewed contracts, not concurrent edits or implicit replacement. CI green for one workflow does not override another FAIL.

## Risks / milestones

- R1 cross-tenant contamination — Core; S1 correlation gate BLOCKED.
- R2 stale/unsourced Twin edge — Twin; S2 impact gate BLOCKED.
- R3 hallucinated citations or permissive Critic — Policy; S3 intelligence gate BLOCKED.
- R4 shared quality workflow schedule-contract false negative — Core/CI; S4 quality reconciliation BLOCKED. Investigate `test_convergence_branch_pushes_run_quality_gates` newline expectation; do not create schedule.
- R5 broad #713 change surface/contract drift — Architect; S5 interface freeze BLOCKED.
- R6 NOC/ITSM premature promotion — UX; S6 operator journey NOT_TESTED.
- R7 no end-to-end signed synthetic proof — Architect; S7 customer value NOT_TESTED.
- R8 LIVE evidence/rollback unavailable — host operator; S8 LIVE gate BLOCKED / NO-GO.

**Acceptance before integration:** full exact-head quality CI success; reproducible offline synthetic receipt tying tenant/event/incident/CI/Payments/evidence/decision; negative tests for cross-tenant, stale edge, missing citation and absent HITL; explicit rollback per PR; Architect reviews compatibility. No automatic merge, rebase, cherry-pick, deployment, SSH, Debian access or V1/V30 modification.

**Next:** Core fixes the test/workflow contract in its own branch and reruns CI; Twin/Policy provide their exact-head receipts; Architect rechecks changed files, SHA and CI before any manual promotion.