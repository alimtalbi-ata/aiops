# R1/5 — Exact-head quality triage and fail-closed evidence handoff (2026-11-16)

**Scope:** documentation-only, offline DEMO/SIMULATION; no production authority. **LIVE NO-GO**. Target PR #713, integration branch `integration/aiops2-convergence-20261114`. Base SHA read directly from GitHub: `91551be28bc1383062669ef48d9c29aff6a83718`.

## Evidence actually obtained

- Read on integration branch: `README.md`, `docs/PROJECT-CONTINUITY.md`, `docs/ARCHITECTURE-AND-BOUNDARIES.md`, `docs/operations/AIOPS2-AUTONOMOUS-DEV-TEAM-OPERATING-MODEL-2026-10-31.md`, and `docs/operations/AIOPS2-AUTOMATION-CONTROL-PLANE-2026-10-31.md`.
- PR #713: **draft**, **mergeable=false**, 182 changed files (GitHub PR metadata at inspection); the reason for non-mergeability is **UNKNOWN** without conflict diagnosis.
- GitHub commit-workflow lookup for the exact base SHA returned `workflow_runs=[]`; combined commit statuses returned `statuses=[]`. Both are **NOT_TESTED**, **not PASS** and **not proof that no runs exist**: workflow lookup only covers PR-triggered runs and first page.
- Inspected `scripts/aiops2_event_correlation.py`, `scripts/aiops2_digital_twin_impact.py`, and their existing test files on that SHA. No tests were executed in this increment.

## Targeted gaps and acceptance requirements

| Priority | Contract / observed implementation | Targeted next action | Gate |
| --- | --- | --- | --- |
| P0 | Correlation key `(tenant_id, source, source_event_id)`, group `(tenant_id, service_id)`; conflicts quarantine both receipts | Reuse #718/#751/#756; run deterministic replay, source/tenant isolation, contradictory digest and permutation tests at exact SHA | PASS only with captured test output |
| P0 | Freshness checks `observed_at` age and `known_at <= as_of`; boundary 900s | Reuse #751/#765; test exactly 900s vs 900s+epsilon and future `known_at` | PASS only with captured test output |
| P0 | Twin graph accepts only syntactically sourced, tenant-scoped edges; `SOURCED_SYNTHETIC_PATH` is **not** runtime provenance | Preserve `UNKNOWN` when edges absent/conflicting/stale; prove that even valid synthetic SAN→Payments paths keep `runtime_attested=false` and `live_remediation_authorized=false` | No runtime claim without independent attestation |
| P0 | Policy/HITL authorization is not conferred by synthetic receipts or forged fields | Negative tests: inject `policy_approved`, `hitl_approved`, `live_remediation_authorized` in raw observations; assert no elevation, no action | Fail-closed, LIVE NO-GO |
| P1 | Historic quality failure at `Daily quality schedule contract` (see #742) | Owner of #742 to validate newline assertion against workflow, run isolated test then exact-SHA CI | No cross-SHA PASS |
| P1 | Historic Portal GET-only mock failures | Portal owner to reproduce packaged smoke with isolated mocks, retain GET-only security gate | Do not weaken gate |

## Non-overlapping execution and handoff

1. **No duplicate modifications** to existing tests owned by #718, #751, #756, #765, or the schedule test owned by #742. This document alone is added on an independent branch.
2. On an isolated checkout of the **exact SHA under test**, run `python -m pytest -q tests/test_aiops2_event_correlation.py tests/test_aiops2_digital_twin_impact.py`, then the focused tests from the other PRs **on their own exact commits**. Record command, environment, exit code, count and SHA. A test file in an unmerged PR is not present on #713 by default.
3. Record each GitHub Actions run URL, event, head SHA, attempt, job conclusion and failing step. If no matching run is returned, mark **NOT_TESTED**; if a required dependency prevents execution, **BLOCKED**.
4. Route changes to the responsible PR owners; architect/integrator reviews conflicts and cross-PR selection. No merge/rebase/cherry-pick or deployment in this role.

**Limitations:** no runtime observation, cryptographic provenance validation, real CMDB causal link, Policy/HITL positive authority, or CI result is established here. No secret or real-world side effect. Rollback: close this documentation-only PR.
