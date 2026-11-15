# AIOPS2 — Exact-head CI triage and integration handoff (2026-11-15)

Owner 5/5; DEV documentation only. Integration candidate #713 HEAD `d1763c90595f0714347c86cd55f86e60f44e236c`. No LIVE, deployment, merge or host access.

## Verified regression

PR #717 previous HEAD `3a0a0e8f9256dc73d60abcba3602812934715b89`: [Actions 43733506668](https://github.com/alimtalbi-ata/aiops/actions/runs/43733506668) **FAIL**. Job `policy-and-static` failed at `Daily quality schedule contract`: `test_quality_schedule_contract.py::test_convergence_branch_pushes_run_quality_gates` asserted a workflow push-branches text fragment not found. Jobs `grafana-real-integration` and `core-postgres-noc-real-integration` succeeded on CI runner; not Debian/LIVE evidence. No local tests executed. Investigate workflow/test mismatch on exact SHA; do not disable tests or add cron.

## Single P0 WIP 3/3 and owner handoff

| Order | Owner / candidate PR HEAD | Acceptance |
|---|---|---|
| 1 Correlation | Core 3/5, #718 `4385ee22c02e104e6701785024706d832968a947` | Exact-head negative tests, zero cross-tenant joins, deterministic dedup, UNKNOWN on missing/stale xref |
| 2 Twin impact | Twin 1/5, #715 `c2881cfa13d17f7b67c96dbae4959dccc15f3909` | Resolve reported mergeability conflict via owner, graph version/provenance, reproducible SAN→Payments impact, UNKNOWN if missing |
| 3 Analyst/Critic/RAG | Policy 4/5, #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a`, #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | Compare changed-file overlap; cited evidence, negative tests, zero unapproved effects; Policy/HITL fail-closed |

Downstream only: UX 2/5 cockpit #719 `912440fc73588d363feabc09cecda052532d55e4`, pending upstream contracts. All five PRs observed DRAFT; no independent exact-head CI for these heads asserted here. S1–S8 are targets, NOT_TESTED, not completed milestones.

## Risks / rollback / next action

R5 branch divergence (#715 mergeable=false); R6 host attestation UNKNOWN / LIVE NO-GO; R7 #717 CI FAIL. Next: quality owner diagnoses assertion without altering scheduler semantics; Core/Twin/Policy provide exact-head test evidence and interfaces; 5/5 checks file collisions and selects only qualified increments. Rollback: revert this documentation commit on #717 branch; no runtime changes.
