# AIOPS2 R1/5 — exact-head qualification and safe convergence handoff (2026-11-16 10:27 Europe/Paris)

Status: SOURCE_REVIEWED; CI NOT_TESTED on the current integration head; LIVE NO-GO. This is an offline review receipt, not runtime attestation.

## Identity and evidence

- Repository: alimtalbi-ata/aiops
- Integration PR: #713 (Draft, open, mergeable=false)
- Current observed head_sha: `91551be28bc1383062669ef48d9c29aff6a83718` (GitHub PR metadata, 2026-11-16).
- PR base: main; metadata base_sha `48deddadf365ac8a7cf71c7067f1c6cd740c32b6`.
- Exact-head GitHub Actions query: `fetch_commit_workflow_runs` returned zero PR-triggered runs. Combined commit status returned zero statuses. **NOT_TESTED**, not PASS and not proof no other run exists (API first page, PR-event filter).
- No tests executed locally during this review. No runtime, Debian or LIVE observation.
- Earlier QA branches #718, #742, #751, #756, #765, #770 are **separate heads**. Their historical CI results cannot qualify the new #713 SHA.

## Minimal coverage and ownership matrix

| Gate | Existing isolated proposal | Unverified / targeted next action |
| --- | --- | --- |
| Multisource correlation + dedup | #718 and Q01–Q02 in #770 | Execute permutation tests and inspect exact receipt identities |
| Tenant and source namespaces | #756 and Q03–Q04 | Run tenant leakage and cross-source ID tests on current integration code |
| Conflicting provenance | #718/#751 and Q05/Q08 | Assert both contradictory receipts rejected; digest alone is not authenticated provenance |
| Freshness and known_at | #751/#765 and Q06–Q07 | Freeze clock; boundary, timezone equivalence and future timestamp cases |
| SAN P1 → Payments P2 | Q09 in #770 | Require sourced Twin edge and graph version; otherwise causal relation UNKNOWN |
| Forged authority / Policy / HITL | #765 and Q10–Q11 | Assert DENY/BLOCKED and effects_allowed=false; independent decision proof absent |
| Packaged Portal negative navigation | Q12 in #770 | Portal owner to inspect mocks and GET-only route registration; preserve enforcement |
| Quality schedule assertion | #742 | CI owner to test newline assertion fix on its exact SHA; do not alter cadence |

## Reproduction plan (not executed)

1. In an ephemeral offline checkout pinned to the target SHA, run `python -m unittest discover -s tests -p 'test_aiops2_correlation*contract.py' -v`; record actual discovered tests and outcomes, not assumed counts.
2. Run `python -m unittest discover -s tests -p 'test_quality_schedule_contract.py' -v` separately; check whether the asserted newline block matches the actual workflow.
3. Inspect failing job logs for the precise step and traceback before changing code. For `InvalidEvent: duplicate impact route`, construct one identical duplicate path and one contradictory path; do not relax contradictory-route rejection.
4. For packaged Portal negative tests, ensure mocks reach intended navigation failure **after** GET-only guard passes; no real HTTP endpoints.
5. For each new SHA, record `run.id`, `run.head_sha`, `event`, `attempt`, `conclusion`, job steps and test counts. Never transfer PASS across SHAs.

## Integration risks and decision

PR #713 has a broad diff (GitHub metadata: 182 changed files, 685 commits) and mergeable=false; cause not independently established in this review. Avoid overlapping changes to files already owned by #718/#742/#751/#756/#765/#770. Seek integrator review of overlap, resolve conflicts in an explicitly approved separate change, and requalify the resulting SHA. No merge, rebase or cherry-pick here.

Source boundaries read: README.md; docs/PROJECT-CONTINUITY.md; docs/ARCHITECTURE-AND-BOUNDARIES.md; docs/operations/AIOPS2-AUTONOMOUS-DEV-TEAM-OPERATING-MODEL-2026-10-31.md; docs/operations/AIOPS2-AUTOMATION-CONTROL-PLANE-2026-10-31.md. Treat their dated runtime inventories as historical, not current proof.

## Safety, dependency, rollback

DEMO/SIMULATION isolated; missing evidence UNKNOWN; Policy/HITL fail-closed; no LIVE actions. No secrets, new stack/cron, Debian/SSH, V1 :7777, V30 :7788, deployment, database writes or real external effects. This increment adds only this review file; rollback is close its draft PR or revert its single commit after review. Next: exact-SHA CI triage and test execution, then coordinate targeted corrections with owners.
