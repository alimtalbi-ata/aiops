# AIOPS2 — Quality gate evidence and integration handoff (2026-11-16 07:02 CET)

**Scope:** DEV documentation only, NO-GO LIVE. This document is a qualification snapshot, not authorization to merge, deploy, run a cron, change Debian, or perform an external effect. Integration candidate: `integration/aiops2-convergence-20261114`, observed HEAD `931cd107439c2180acb143f9198ed84649443b3f`, PR [#713](https://github.com/alimtalbi-ata/aiops/pull/713) DRAFT, `mergeable=false`. The SHA is an observation, not a moving-branch guarantee.

## New independently inspected evidence

The preceding architect PR [#760](https://github.com/alimtalbi-ata/aiops/pull/760) at **exact head** `45f4427b3bd9a673502de0e6a0daaaab1bd0c131` has one PR-triggered [quality run 43807312343](https://github.com/alimtalbi-ata/aiops/actions/runs/43807312343), `completed/failure` (GitHub commit workflow-run query). Its latest-attempt jobs show:

| Job | Observed result |
| --- | --- |
| `policy-and-static` | **FAIL** at step `Daily quality schedule contract` |
| `core-postgres-noc-real-integration` | **PASS** (job success, *not* business E2E qualification) |
| `grafana-real-integration` | **PASS** (job success, *not* LIVE Grafana qualification) |

This isolates a reproducible CI gating symptom; it does **not** prove the exact underlying assertion or root cause. **Core/CI owner** should inspect failing step logs and test/workflow representation, propose the smallest fix in a separate owned PR, and rerun quality on the resulting exact SHA. No additional workflow, schedule or cron is authorized. A prior diagnosis suggested literal `\\n` versus actual newlines; treat it as a **hypothesis** until confirmed by logs and source.

## Single P0 backlog (WIP 3/3)

| Order | Owner / PR | Exact observed head | Required product evidence / gate |
| --- | --- | --- | --- |
| 1 | Core 3/5 — [#718](https://github.com/alimtalbi-ata/aiops/pull/718) | `5f8a3fb00882d7cbfc1ca164ed4bf19173e6d404` | 0 cross-tenant correlation matches in negative fixtures; event→incident→run identity and dedup receipts, with test output |
| 2 | Twin 1/5 — [#715](https://github.com/alimtalbi-ata/aiops/pull/715) | `3da16e9177bf6afbacfd79742b7f910663e95c4d` | SAN→Payments graph path, source IDs, timestamps, freshness thresholds, stale/missing → UNKNOWN; measured impacted-service counts |
| 3 | Policy 4/5 — [#716](https://github.com/alimtalbi-ata/aiops/pull/716), [#720](https://github.com/alimtalbi-ata/aiops/pull/720) | `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2` / `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | Independently resolvable citations, Critic rejection on fabricated/contradictory evidence, HITL denial with zero effects and immutable receipt |

NOC [#719](https://github.com/alimtalbi-ata/aiops/pull/719) `16f79df6f8f55010d7f8a240f20cc627c9973170` and ITSM are downstream, not fourth/fifth P0. The incoming PRs have differing recorded base SHAs; **do not infer semantic compatibility or reuse another SHA's CI**. Verify schema versions, tenant identity, evidence provenance, mode, and authorization at each boundary. Owner retains file ownership; architect edits this new standalone document only.

## Risks and milestones

- **R1** tenant leak: BLOCKED until negative join tests; **R2** missing/double event identity: BLOCKED until idempotency proof.
- **R3** unsupported Twin blast radius: BLOCKED until source-backed graph path; **R4** stale evidence: BLOCKED until UNKNOWN negative case.
- **R5** unsupported Analyst citation: BLOCKED until independent verification; **R6** Policy/HITL side effect: BLOCKED until denial/no-effect receipts.
- **R7** CI quality contract failure: FAIL on #760 exact SHA, Core/CI owns diagnosis; **R8** divergent integration base / conflicts: BLOCKED, review without rebase/merge.
- **S1–S5:** BLOCKED (source/contract qualification); **S6–S7:** NOT_TESTED (end-to-end isolated journey); **S8:** BLOCKED / NO-GO LIVE.

**Next gate:** obtain Core/CI's failing assertion and minimal owned test fix, then collect per-owner negative-test commands, outputs, fixture digests, CI URLs and SHA. Re-evaluate only the SHA tested. No local tests or LIVE checks were performed for this document.
