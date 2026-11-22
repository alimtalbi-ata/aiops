# AIOPS2 integration — exact CI quality failure root cause (2026-11-16 08:02 CET)

Scope: DEV-only, read-only diagnosis; no runtime attestation. Target PR #713, integration branch `integration/aiops2-convergence-20261114`, observed head `931cd107439c2180acb143f9198ed84649443b3f`. No merge/deploy/SSH/Debian/cron or LIVE action authorized.

## Reproducible evidence (source inspection + GitHub CI, not a local test)

- PR #764 head `9075a6b6a6acbc4751d5e17039419b669026e453`; workflow run [43814206511](https://github.com/alimtalbi-ata/aiops/actions/runs/43814206511) completed FAILURE.
- Run job `policy-and-static` (ID `133122409859`) FAIL at step 6, `Daily quality schedule contract`. Other two jobs `core-postgres-noc-real-integration` (ID `133122409601`) and `grafana-real-integration` (ID `133122409891`) PASS **only for their configured checks**.
- Log assertion: `test_convergence_branch_pushes_run_quality_gates` at `tests/test_quality_schedule_contract.py:16` fails, `Ran 4 tests`, `failures=1`.
- Source inspection of `tests/test_quality_schedule_contract.py`: assertion string contains literal `\\n` sequences, while `.github/workflows/quality.yml` has actual line breaks and already lists the integration branch under `push.branches`. This is a **test expectation escaping defect**, not evidence that branch trigger is absent.
- The failing step causes most subsequent `policy-and-static` steps to be SKIPPED, so they are **NOT_TESTED**, not PASS. No assertion about LIVE or full E2E is supported.

## Minimal owner handoff (Core/CI 3/5, do not modify concurrently)

In `tests/test_quality_schedule_contract.py`, replace the literal backslash-n sequences in the `assertIn` expected value with actual newline escapes (`\n` in Python source) or use `splitlines()`/a structured YAML check. Preserve the existing `quality.yml` schedule and branch triggers; **do not add or activate a cron**. Owner must run:

```sh
python3 -m unittest discover -s tests -p 'test_quality_schedule_contract.py' -v
```

Record test output, exact new SHA, and terminal CI results; requalify all skipped steps on that new SHA. This document deliberately does not edit either shared test or workflow file.

## Single P0 board (WIP=3)

| Order | Owner / PR | Required acceptance evidence | State |
| --- | --- | --- | --- |
| 1 correlation | Core 3/5 / #718 `5f8a3fb00882d7cbfc1ca164ed4bf19173e6d404` | deterministic dedupe and zero cross-tenant joins, source IDs, negative tests | BLOCKED |
| 2 business-impact Twin | Twin 1/5 / #715 `3da16e9177bf6afbacfd79742b7f910663e95c4d` | SAN→storage→Payments source/time/freshness, missing provenance => UNKNOWN | BLOCKED |
| 3 Analyst/Critic/RAG | Policy 4/5 / #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`, #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | independently checked citations, Critic rejection, fail-closed HITL no external effects | BLOCKED |

UX #719 and ITSM are downstream; no fourth P0 workstream. Branch-base SHAs differ from #713 HEAD; **semantic compatibility remains UNKNOWN** even where paths do not collide.

## Risk register / milestones

R1 tenant leakage BLOCKED; R2 wrong correlation BLOCKED; R3 stale/unproven Twin impact BLOCKED; R4 unsupported AI citation BLOCKED; R5 Critic dependence BLOCKED; R6 Policy/HITL side effect BLOCKED; R7 base-SHA/interface drift BLOCKED; R8 misleading CI qualification BLOCKED (root cause identified, remediation pending).

S1 correlation BLOCKED; S2 canonical incident BLOCKED; S3 Twin impact BLOCKED; S4 Analyst/Critic/RAG BLOCKED; S5 Policy/HITL BLOCKED; S6 NOC synthetic journey NOT_TESTED end-to-end; S7 ITSM lifecycle NOT_TESTED end-to-end; S8 release/LIVE BLOCKED.

Next integration action: ask Core/CI owner to correct only the escaped expectation and supply terminal CI on its new SHA; then compare Core→Twin→Analyst/Critic→Policy→NOC contracts against #713 exact HEAD and require negative test receipts. All DEMO/SIMULATION isolated; unknown evidence stays UNKNOWN. **NO-GO LIVE**.
