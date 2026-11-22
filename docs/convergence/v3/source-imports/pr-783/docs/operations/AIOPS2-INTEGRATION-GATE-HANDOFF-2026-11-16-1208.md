# AIOPS2 — Integration gate handoff (2026-11-16 12:08 Europe/Paris)

Scope: DEV-only, documentation, no production access or action. Baseline: `integration/aiops2-convergence-20261114` at `91551be28bc1383062669ef48d9c29aff6a83718`; canonical candidate PR #713 remains DRAFT, mergeable=false. This document is a snapshot, not a CI or runtime certificate.

## Single P0 queue — WIP 3/3

| Order | Accountable owner | PR / exact head | Contract gate | Verdict |
|---|---|---|---|---|
| 1 Correlation | Core 3/5 | #718 `5f8a3fb00882d7cbfc1ca164ed4bf19173e6d404` | Tenant/actor/source-event identity; dedup idempotency; reject cross-tenant joins; trace Event→Incident→Run→Evidence | BLOCKED |
| 2 Twin business impact | Twin 1/5 | #715 `3da16e9177bf6afbacfd79742b7f910663e95c4d` | SAN→storage→Payments graph, CI/service provenance and observed-at/freshness; stale/missing evidence => UNKNOWN | BLOCKED |
| 3 Analyst/Critic/RAG | Policy 4/5 | #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`; #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | Evidence IDs and independently checkable citations; Critic challenges Analyst; Policy/HITL fail-closed, no external effect | BLOCKED |

NOC #719 (`16f79df6f8f55010d7f8a240f20cc627c9973170`) and ITSM remain downstream, not a fourth P0. No overlapping owner edits authorized.

## Fresh exact-head evidence and limitations

- #779 head `ab5f6a14dfac4f7d40e4dc55afac8ad46b233ddf`: GitHub Actions run [43847709109](https://github.com/alimtalbi-ata/aiops/actions/runs/43847709109) reports `completed/failure`. **FAIL**, not PASS. Individual failed assertion not established by this run-level result.
- #713 head `91551be28bc1383062669ef48d9c29aff6a83718`: no new exact-head workflow run inspected in this handoff; **NOT_TESTED** here.
- Local tests, contract E2E and actual LIVE connectors: **NOT_TESTED**. No CI outcome for this document until its own exact-head run completes.
- Incoming PR base snapshots (#718/#715/#716/#720) differ from #713 current head; interface compatibility **BLOCKED**, not established by non-overlapping paths.

## Negative acceptance receipts required

1. Core: same source-event ID replay creates one canonical identity; different tenant cannot join even with identical CI/event keys; missing tenant/actor yields deny/UNKNOWN. Record fixture, command, exit code, expected and observed output.
2. Twin: assert sourced SAN path degradation impacts Payments only along versioned graph edges; remove or stale-date an edge and observe UNKNOWN, not inferred business impact.
3. Analyst/Critic/Policy: missing/stale/mismatched citation rejected; Critic independently records disagreement; HITL missing approval, stale fencing or contradictory evidence blocks action, with zero outbox/external effects.
4. For every receipt include PR URL, exact SHA, CI run/job URL, fixture digest, environment label DEMO/SIMULATION, timestamp and outcome PASS/FAIL/BLOCKED/NOT_TESTED. Never promote partial synthetic success to LIVE.

## Risks R1–R8 and milestones S1–S8

R1 tenant leakage; R2 dedup drift; R3 Twin stale provenance; R4 unsourced impact; R5 hallucinated citations; R6 Critic/Policy bypass; R7 unauthorized HITL effect; R8 divergent base/CI drift. All open pending owner receipts.

S1 identity, S2 correlation, S3 Twin, S4 Analyst/Critic, S5 Policy/HITL: **BLOCKED**. S6 NOC and S7 ITSM E2E: **NOT_TESTED**. S8 LIVE release: **BLOCKED / NO-GO**.

Next: Core/CI identify exact failed assertion from run #43847709109 and publish a minimal owner-owned fix with tests; Twin and Policy attach negative receipts on exact heads; integrator reviews diffs, ownership and interface schema before any later promotion. No merge, rebase, cherry-pick, deployment, SSH, Debian access, V1/V30/LIVE modification, new stack or cron. Rollback: revert this one documentation commit only.
