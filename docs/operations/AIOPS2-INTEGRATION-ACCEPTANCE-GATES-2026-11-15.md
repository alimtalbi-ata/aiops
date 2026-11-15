# AIOPS2 — Integration acceptance contract (2026-11-15, DEV only)

Owner: 5/5 architect. Integration candidate: `integration/aiops2-convergence-20261114` / PR #713. This is a **review-only** contract, not a LIVE qualification, migration, or deployment instruction.

## Single P0 backlog (WIP 3/3)

| Priority / accountable owner | Consumer/producer boundary | Measurable acceptance (synthetic isolated) | Gate |
|---|---|---|---|
| 1 Correlation / 3/5 Core (review 2/5) | Source Event → tenant-scoped Incident → Run → GLPI xref → Evidence | Deterministic same-tenant IDs, source event ID, deduplication count and false-join count; 0 cross-tenant joins; conflicting/missing/stale links return UNKNOWN/CONFLICT/STALE, never VERIFIED | BLOCKED until exact-head tests + receipt |
| 2 Digital Twin / 1/5 (review 3/5) | Versioned CI/service dependency graph, provenance/freshness, Incident→impact | ACME SAN→Payments graph fixture: reproducible affected service set and blast radius by seed+graph version; missing edge/source yields UNKNOWN rather than asserted impact; report precision/recall against fixture ground truth | NOT_TESTED |
| 3 Analyst/Critic/RAG / 4/5 policy reviewer + 3/5 integration | Evidence references → hypotheses/citations → Critic → deterministic Policy/HITL | Every asserted hypothesis cites accessible tenant-scoped evidence; stale/missing/unauthorized citation fails closed; 0 unapproved effects; record grounded-answer rate, critic challenge coverage and abstention rate on fixed synthetic cases | NOT_TESTED |

Cockpit NOC and ITSM UX follow these contracts; do not create a competing backend, ticket authority or runtime. Owner 2/5 consumes canonical read-only contracts; 4/5 owns Policy/HITL, 5/5 owns gates and review.

## Contract rules

- Identity: never infer Incident↔Run↔GLPI ticket association from text/title; only canonical, verified, tenant-scoped xref with source, timestamp, version and actor.
- Impact: Twin prediction is **ESTIMATED**, not a verified outage; graph version, edge provenance and freshness are mandatory; GLPI remains CMDB/ITSM authority where qualified.
- Analysis: LLM/RAG is advisory, citations are independently checked, Critic is not approval; Policy/HITL fail-closed and LIVE NO-GO.
- Execution: DEMO/REPLAY/STORY/SIMULATION must be explicitly labelled and effect-free. Worker Temporal inspection `EXISTS_UNATTESTED` cannot attest original start, idempotency or verified postcondition. Timeout means UNKNOWN and reconciliation before retry.
- No edits to other teams' owned source files in this documentation increment. No merge, rebase, cherry-pick, deployment, cron, extra stack, SSH, Debian or LIVE operation.

## S1–S8 checkpoints (targets, not achievements)

S1 canonical source/tenant identity; S2 dedup + conflict tests; S3 Twin graph/provenance; S4 SAN→Payments impact benchmark; S5 cited Analyst/Critic; S6 Policy/HITL no-effect replay; S7 NOC/GLPI timeline using verified IDs; S8 isolated end-to-end acceptance + documented rollback. Every checkpoint requires exact HEAD SHA, executable command, observed test output, artifact link and owner signoff. Until then: NOT_TESTED.

## Risk register and stop conditions

| Risk | Owner | Mitigation / release decision |
|---|---|---|
| R1 fabricated cross-system correlation | 3/5 | Fail-closed xref; no tenant-leak; BLOCKED without negative tests |
| R2 stale or invented business impact | 1/5 | Version/freshness/provenance and benchmark; UNKNOWN otherwise |
| R3 unsupported LLM recommendation | 4/5 | Evidence-grounded critic and policy; no autonomous effect |
| R4 ambiguous Temporal start after timeout | 3/5 + 4/5 | Read-only inspection is unverified; reconcile before retry |
| R5 divergent branches/overlapping files | 5/5 | Single candidate #713; selective review, exact-head CI, no implicit merge |
| R6 LIVE/host assumptions | 5/5 + operator | No host evidence; LIVE NO-GO, rollback NOT_TESTED |

## Qualification and rollback

G0 source diff + exact SHA + static/unit/security CI; G1 isolated integration with tenant/actor boundaries; G2 same-SHA synthetic end-to-end; G3 Twin impact/ITIL; G4 install/upgrade/revert on disposable environment; G5 customer journey. A passing G0 is **not** G1–G5. Current gates: **NOT_TESTED for this documentation commit** until GitHub Actions returns a result. Rollback: revert only this isolated documentation commit on its own branch/PR; no runtime changes. No automatic merge or deployment.
