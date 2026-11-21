# AIOPS2 — Cross-team acceptance gate, 2026-11-15 23:56 CET

**Owner:** 5/5 architect. **Scope:** review-only, no effects, no merge. **Candidate:** `integration/aiops2-convergence-20261114` / PR #713, inspected head `84704e4d0603738d34aac63d733e77d52f2f7783`. All evidence below is GitHub-hosted, not Debian/LIVE. DEMO/SIMULATION are never production evidence.

## P0 single backlog, WIP 3/3

| Order / accountable owner | Exact contribution HEAD | Observed exact-head checks | Acceptance before promotion |
|---|---|---|---|
| 1 Correlation / Core 3/5 | #718 `5f8a3fb00882d7cbfc1ca164ed4bf19173e6d404` | adversarial correlation [43767943571](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943571) **PASS**; synthetic qualification [43767943556](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943556) **FAIL**; synthetic NOC [43767943551](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943551) **FAIL**; quality [43767943576](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943576) **FAIL** | **BLOCKED**. Show same-tenant join, cross-tenant rejection, idempotency, provenance and freshness UNKNOWN on the same input fixture. Explain *each* failed workflow, do not substitute one green job. |
| 2 Twin impact / Twin 1/5 + Core contract review | #715 `3da16e9177bf6afbacfd79742b7f910663e95c4d` | synthetic [43742358029](https://github.com/alimtalbi-ata/aiops/actions/runs/43742358029) **PASS**; quality [43742358010](https://github.com/alimtalbi-ata/aiops/actions/runs/43742358010) **FAIL** | **BLOCKED**. Show SAN→storage→Payments graph, tenant-scoped edges, source IDs, observed_at, expiry, deterministic impact and explicit UNKNOWN for missing/stale/contradictory evidence. Fixture-supplied attested flag is not LIVE authority. |
| 3 Analyst/Critic/RAG / Policy 4/5 | #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`; #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | #716 quality [43732445942](https://github.com/alimtalbi-ata/aiops/actions/runs/43732445942) **FAIL**, synthetic [43732446134](https://github.com/alimtalbi-ata/aiops/actions/runs/43732446134) **FAIL**; #720 synthetic [43737651757](https://github.com/alimtalbi-ata/aiops/actions/runs/43737651757) **FAIL**, quality [43737651704](https://github.com/alimtalbi-ata/aiops/actions/runs/43737651704) **FAIL** | **BLOCKED**. Cite independently resolvable evidence, reject invented/cross-tenant/stale citations, independent Critic, explicit HITL denial, zero external effects. |

**Downstream only:** cockpit #719 `16f79df6f8f55010d7f8a240f20cc627c9973170`: synthetic NOC [43769423138](https://github.com/alimtalbi-ata/aiops/actions/runs/43769423138) **PASS**, synthetic qualification [43769423068](https://github.com/alimtalbi-ata/aiops/actions/runs/43769423068) **PASS**, quality [43769423108](https://github.com/alimtalbi-ata/aiops/actions/runs/43769423108) **FAIL**. Do not open a fourth P0. ITSM follows gated end-to-end evidence.

## Interface handshake and file ownership

Core publishes tenant_id, source_event_id, incident_id, run_id, evidence_refs, source/observed timestamps and UNKNOWN semantics; Twin consumes the same tenant and evidence provenance and emits a versioned impact read, never a remediation instruction. Analyst consumes correlation + Twin read receipts; Critic must reject missing/stale/mismatched citations; Policy/HITL is an independent effect gate. UX consumes read-only projections and may not infer approval from a synthetic receipt. Owners retain their files; architect edits only this dedicated document. API/schema compatibility and negative E2E tests remain **NOT_TESTED** until run on exact candidate HEAD.

## Risk register and S1–S8

R1 cross-tenant correlation (Core), R2 fixture-only Twin authority (Twin), R3 fabricated/expired citations (Policy), R4 HITL bypass (Policy), R5 divergent quality workflow contract (Core/CI), R6 concurrent candidate drift (Architect), R7 cockpit green synthetic mistaken for LIVE (UX), R8 missing runtime attestation (host operator). All are **OPEN** until linked negative test + exact SHA.

S1 identity/correlation **BLOCKED**; S2 provenance/CMDB **BLOCKED**; S3 Twin impact **BLOCKED**; S4 Analyst/Critic **BLOCKED**; S5 Policy/HITL **BLOCKED**; S6 NOC/ITSM **NOT_TESTED** end-to-end; S7 DEMO replay **NOT_TESTED** end-to-end; S8 LIVE **BLOCKED / NO-GO**.

## Qualification and rollback

This file is a review artifact, not an implementation claim. No local tests or host checks executed for this document. Its own CI is **NOT_TESTED** until the exact new SHA returns a terminal result. Rollback is a revert of this single documentation commit only. Never merge, deploy, alter V1 :7777/V30 :7788, add cron/stack, expose secrets or make external effects. No LIVE approval without explicit independent receipts.
