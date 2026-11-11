# AIOPS2 differential acceptance — CI failure boundary (2026-11-12 00:07 Europe/Paris)

## Provenance
GitHub PR #660, head `21ce7d161d4d29308905f2925e6df92b4612988b`, Draft; source main blob `ac58f73c725f5e088081bffed4478ea18585ef5c`. GitHub Actions run 43109660723 completed **failure**. Job evidence: `core-postgres-noc-real-integration` success; `grafana-real-integration` success; `policy-and-static` cancelled. A cancelled job is not a passed test, and run failure alone is not proof of an application regression. Inspect workflow job logs, cancellation origin and test-step coverage before attributing cause. No Debian access or E2E attestation.

## Before/after acceptance matrix
| Capability | Main source / observed CI | Candidate #660 | Runtime v28/V145 |
| --- | --- | --- | --- |
| Dashboard/Core/Twin/Runs global read status | `Object.values(data.states)` permits unknown keys to influence summary | explicit dashboard/runs/twin allowlist | NOT VERIFIED |
| Runs visibility | up to 100 accepted, first 15 rendered | unchanged; P1 truncation open | NOT VERIFIED |
| NOC | real Core/Postgres/NOC CI job success | unchanged | NOT VERIFIED |
| GLPI/Copilot | ACL/HITL independent, not covered by this change | unchanged | NOT VERIFIED |
| Evidence | no LIVE attestation by bootstrap | unchanged | NOT VERIFIED |
| Navigation/v28/V145 routes | not compared in this cycle | unchanged | NOT VERIFIED |
| CI | #660 run failure, policy-and-static cancelled | candidate cannot be accepted as green | not a host signal |

## Negative / non-regression protocol C-023
1. Checkout exact #660 SHA in isolated CI or local disposable worktree; no production credentials or runtime.
2. Run `node --test tests/portal/test_bootstrap_states_whitelist.cjs`. Inject recognized dashboard/runs/twin states UNKNOWN and extra `evidence`/`copilot` states READABLE_UNVERIFIED; assert global remains UNKNOWN.
3. Mutate one recognized state to READABLE_UNVERIFIED with a valid read-model payload and assert global READABLE_UNVERIFIED but never LIVE. Mutate tenant ACL flag false and assert fail-closed UNKNOWN.
4. Run the normal quality gates at the same SHA. Record per-job outcome, first failing step and logs; if a job is cancelled, mark its assertions NOT EXECUTED.
5. Compare routes, ACL/HITL, Core/Twin/Runs, NOC, GLPI, Copilot, Evidence and navigation against v28/V145 only with captured baseline and candidate artifacts; unknowns remain UNKNOWN.

**Acceptance:** all required negative assertions pass; no cancelled or skipped required gate; route parity and tenant/HITL protections verified. Current status: **NOT EXECUTED / NOT ACCEPTED**.

## Rollback and boundary
Close this Draft PR or revert its documentation-only commits on this branch. Do not merge, deploy, modify main, Debian, Docker, cron, secrets, PG/GLPI or other stacks. #557 remains a rootful-vs-rootless diagnostic error per operator proof (aiops UID 1001, rootless socket, 87 containers / 210 images at observation time); no storage recovery. Host freshness and E2E remain unverified.
