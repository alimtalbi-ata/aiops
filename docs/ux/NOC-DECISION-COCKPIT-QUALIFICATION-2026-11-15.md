# NOC decision cockpit — exact-head qualification checkpoint (2026-11-15)

Owner: UX/NOC 2/5. Target: PR #719 against integration/aiops2-convergence-20261114 (#713). Source head inspected: `39ef284d592dba9601e2bca706c09cae3f536856`.

## Observed GitHub Actions evidence (not LIVE)

- AIOps2 synthetic qualification run https://github.com/alimtalbi-ata/aiops/actions/runs/43752258115: completed/success on the inspected SHA. This verifies its configured synthetic steps, **not** the standalone Chromium test.
- AIOps quality gates run https://github.com/alimtalbi-ata/aiops/actions/runs/43752258085: completed/failure on the inspected SHA. `policy-and-static` failed at `Daily quality schedule contract` before subsequent steps. The assertion expects an exact YAML substring without a blank line between `pull_request:` and `push:`, while the workflow has that blank line. Core/PostgreSQL and Grafana jobs succeeded independently. Do not call the full workflow PASS.
- `tests/test_aiops2_noc_browser.py` is present, but no job execution of this file or retained 320/768/1440 screenshots was found in these inspected job steps. Browser qualification: UNKNOWN.

## UX safety and provenance blockers

- `scripts/aiops2_noc_decision_cards.py` accepts `SOURCED_SYNTHETIC_PATH` if the path has >=2 nonempty node labels, **without checking evidence references, source identity, freshness or graph version**. A node list alone is not proof. Keep all impact labels explicitly synthetic/unattested; do not promote this state to verified impact.
- Analyst hypothesis and Critic disposition are displayed, but their evidence references are not rendered. Correlation count is structurally validated, not independently reconciled to source events. Next NOC action is text, not an authorized operation.
- No real route, tenant ACL, screen-reader audit, GLPI/Twin connector attestation, or host/runtime proof established. LIVE/HITL remain denied; NO-GO LIVE.

## Architect acceptance sequence

1. Reconcile #713 projection schema and require source-bound path/evidence references with explicit UNKNOWN on absent/stale/mismatched proof. Preserve SIMULATION and DENY_LIVE.
2. Fix the quality-schedule contract brittleness in its owning branch (prefer YAML semantic comparison), not by modifying shared workflow here.
3. Run `python -m pytest -q tests/test_aiops2_noc_decision_cards.py tests/test_aiops2_noc_decision_cards_contract.py tests/test_aiops2_noc_browser.py` in a disposable browser-enabled environment on the final exact SHA; retain 320/768/1440 screenshots and keyboard/assistive accessibility observations with SHA and checksums.
4. Architect decides route wiring only after source/contract review and exact-head gates. No merge/deploy by UX owner.

Rollback: omit this isolated report or exclude PR #719; no database, scheduler, deployment or LIVE changes.
