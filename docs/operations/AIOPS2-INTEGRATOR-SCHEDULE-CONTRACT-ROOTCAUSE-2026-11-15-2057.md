# AIOPS2 5/5 — exact-head quality gate root cause and coordination (2026-11-15 20:57 CET)

**Scope:** DEV-only, review/contract note. Single integration candidate `integration/aiops2-convergence-20261114`, PR #713 HEAD `ab907992304eac403fe3cc470c6988d20ff214f5` (DRAFT, mergeable=false). **NO-GO LIVE.** No merge/rebase/cherry-pick/deploy/host access. This file intentionally does not edit files owned by the other schedules or the existing CI workflow.

## Reproducible source-level diagnosis (not a test execution)

At #713 HEAD, `tests/test_quality_schedule_contract.py::test_convergence_branch_pushes_run_quality_gates` uses:
```python
self.assertIn('  push:\\n    branches:\\n      - main\\n      - "fix/**"\\n      - "integration/aiops2-convergence-20261114"', WORKFLOW)
```
This is a Python literal containing **backslash-n characters**, not newline characters. The workflow `.github/workflows/quality.yml` contains actual newlines and the matching branch list. Therefore the substring cannot match. Correct only the test's string representation (use actual newlines or `"\\n"` in the Python source) on the **owning Core/CI branch**, with a regression test and fresh exact-head CI. Do **not** create/enable a schedule: the existing workflow already has `schedule` and `workflow_dispatch`.

**Observed CI, not inferred:** #725 HEAD `ef09bd8a4995aacebdb5891cfb3745e7dff68d2f`, Actions [43749748688](https://github.com/alimtalbi-ata/aiops/actions/runs/43749748688): `policy-and-static` FAIL at `Daily quality schedule contract`; `core-postgres-noc-real-integration` PASS and `grafana-real-integration` PASS. #719 HEAD `39ef284d592dba9601e2bca706c09cae3f536856`: [43752258085](https://github.com/alimtalbi-ata/aiops/actions/runs/43752258085) same quality job FAIL, other two jobs PASS; [43752258115](https://github.com/alimtalbi-ata/aiops/actions/runs/43752258115) `synthetic-contracts` PASS. These are mixed outcomes, **not** whole-PR PASS. No test was run locally for this note.

## Single P0 backlog, WIP 3/3

| Priority | Accountable owner | Exact HEAD | Status and measurable acceptance |
|---|---|---|---|
| P0-1 Correlation | Core 3/5 | #718 `42cec4e7c5fb1059b63d8d95da491b28f9391b63` | BLOCKED: prove 0 cross-tenant joins, stable Event→Incident→Run→GLPI/CI→Evidence IDs and negative/idempotency tests on exact SHA |
| P0-2 Digital Twin business impact | Twin 1/5 | #715 `3da16e9177bf6afbacfd79742b7f910663e95c4d` | BLOCKED: reproduce SAN→Payments impact with graph version, source, timestamp, tenant and explicit UNKNOWN for missing links |
| P0-3 Analyst/Critic/RAG | Policy 4/5 | #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`; #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | BLOCKED: independently challenged cited hypotheses; unverified evidence UNKNOWN; Policy/HITL deny with zero external effect |

Downstream: UX 2/5 #719 HEAD `39ef284d592dba9601e2bca706c09cae3f536856` stays **NOT_TESTED for integrated NOC/ITSM**, even with isolated synthetic-contracts PASS. PR #713 is the only candidate, not a qualification.

## Risk register / milestones

- **R1 (Core/CI):** deterministic false-negative schedule-contract test blocks unrelated PRs; change test only in owner branch and rerun exact-head quality.
- **R2 (5/5):** #713 `mergeable=false`; diagnose conflicts without forbidden integration operations.
- **R3 (Core/Twin/Policy):** isolated synthetic checks do not attest E2E business value, tenant scope or LIVE.
- **R4 (all):** overlapping changes to `tests/test_quality_schedule_contract.py`, `.github/workflows/quality.yml`, or #713-owned routes are prohibited without owner coordination.

S1 identity / S2 correlation BLOCKED; S3 Twin BLOCKED; S4 Analyst/RAG / S5 Critic/Policy/HITL BLOCKED; S6 NOC / S7 ITSM NOT_TESTED; S8 integrated acceptance BLOCKED. All require source-backed, exact-head evidence. DEMO/SIMULATION are isolated; LIVE fail-closed and NO-GO.

**Next:** Core/CI owns the one-line test-literal correction and exact-head rerun. Integrator checks #713 conflicts and contracts after Core, Twin and Policy evidence lands. No automatic merge/deployment. **Rollback:** revert this single documentation commit only.
