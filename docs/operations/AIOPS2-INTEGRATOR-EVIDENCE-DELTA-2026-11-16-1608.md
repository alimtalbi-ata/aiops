# AIOPS2 integration evidence checkpoint — 2026-11-16 16:08 CET

Scope: DEV documentation only. NO-GO LIVE. Base: `integration/aiops2-convergence-20261114`; controlling PR: #713. This checkpoint does not integrate code or assert runtime behavior.

## Exact evidence (observed via GitHub API)

- #796 commit `e45de78d54ca8c5e8d909bab729e8f53b8a1b19d`: GitHub Actions run [43886891171](https://github.com/alimtalbi-ata/aiops/actions/runs/43886891171) completed **FAIL**. Failed step/log and root cause **NOT_TESTED** in this checkpoint. This supersedes the previous **NOT_TESTED** CI status for #796 only.
- #713 is open, DRAFT and `mergeable=false` in the API response. Its changed-file inventory contains 182 paths. Exact HEAD and CI not recorded here unless separately revalidated.
- Changed-file inventory: #718 (2 paths), #715 (3), #716 (3), #720 (3), #719 (7). No exact path collision across these five contributions and #713 at the time of inspection; semantic/API compatibility **BLOCKED**. Absence of path collision does not imply safe integration.

## Single ordered P0 backlog (WIP=3/3)

| Order | Owner / contributions | Measurable acceptance | Gate |
|---|---|---|---|
| 1 | Core / #718 | Zero cross-tenant correlations in negative fixture; same source event re-ingestion yields one canonical incident and traceable IDs | BLOCKED: exact-head test receipts and API schema compatibility required |
| 2 | Twin / #715 | SAN→Payments impact with CI/service edge provenance, graph version and observation time; stale or absent evidence produces UNKNOWN | BLOCKED: dated trace and negative test receipts required |
| 3 | Intelligence/Policy / #716, #720 | Every Analyst citation resolves to evidence; Critic independently rejects fabricated citations; HITL denial produces zero external effects | BLOCKED: isolated negative tests and exact-head receipts required |

NOC #719 and ITSM are downstream, not a fourth P0 item. No code, workflow, cron, runner, deployment or LIVE change is authorized.

## Interface acceptance matrix

1. Core → Twin: tenant, incident_id, source_event_id, CI IDs, observed_at, graph_version; reject cross-tenant joins and stale identity mapping.
2. Twin → Analyst: impact must carry source edges, timestamps and uncertainty; UNKNOWN must survive serialization and UI.
3. Analyst → Critic → Policy: cited evidence IDs, provenance, immutable verdict, explicit negative/uncertain status; model confidence never substitutes for policy approval.
4. Policy → HITL → NOC: mode, actor, approval scope, expiry, fencing/preconditions, effect receipt and verified postcondition; deny/missing input means no external effect.

## Risks R1–R8 and milestones S1–S8

R1 cross-tenant joins (Core); R2 duplicate event effects (Core); R3 stale graph/provenance (Twin); R4 unsupported impact claims (Twin); R5 fabricated citations (Intelligence); R6 Critic self-validation (Policy); R7 unauthorized HITL effect (Policy); R8 divergent bases/CI evidence (Integrator). All remain open until exact-head negative evidence.

S1 identity/correlation BLOCKED; S2 tenant isolation BLOCKED; S3 Twin provenance BLOCKED; S4 Analyst/Critic grounding BLOCKED; S5 Policy/HITL BLOCKED; S6 no-effect E2E NOT_TESTED; S7 NOC/ITSM journey NOT_TESTED; S8 LIVE BLOCKED/NO-GO.

## Next owner actions and rollback

Core/CI: inspect failing job/step of run 43886891171; submit minimal fix in owned branch with exact assertion and tests, without new schedule. Core: deliver tenant/idempotence negative receipts. Twin: deliver dated SAN→Payments or UNKNOWN. Policy: deliver invalid-citation rejection and HITL-denial zero-effect receipts. Integrator: compare API contracts and exact-head CI before any promotion.

Verification of this documentation-only increment: GitHub commit SHA and PR creation are repository evidence, not test PASS. Local tests **NOT_TESTED**; new PR CI **NOT_TESTED** until a terminal result is observed. Rollback: revert only this new document commit after review; no automatic action.
