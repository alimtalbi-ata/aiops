# AIOPS2 — Integration gate for functional portal upgrade (2026-11-11)

## Purpose and status
**PROPOSED / NOT INTEGRATED / NOT DEPLOYED.** Incrementally upgrade the existing AIOPS2 Portal. No reconstruction, rootless Docker changes, production writes, or change to the five other stacks. Main baseline observed: `0e232c9fdf4a519de36ba8035b506621854e0277` (2026-11-08). This document is a controlled integration plan, **not** a claim of tests or runtime qualification.

## Verified PR topology at 2026-11-11 11:46 Europe/Paris
| Lane | PR / exact head | Base | Functional value | Integration note |
|---|---|---|---|---|
| HTTP security baseline | #538 `4615c05a3b` | main | Security headers on framework 405 responses | Independent first gate; test against main and candidate |
| Evidence filtering | #541 `a4a8a5f918` | agent/portal/461-operational-timeout-20261110 | Fail closed on conflicting evidence IDs | Stacked; inspect all ancestors before inclusion |
| Timeout/cancellation | #550 `9c3227195c` | agent/portal/537-timeout-cancel-consolidated-20261110 | Prevent spoofed timeout state | Stacked; avoid cherry-picking tip without ancestors |
| Prometheus history accessibility | #551 `31f735ae70` | agent/portal/548-history-accessible-context-20261110 | Accurate empty-history announcements | Stacked; audit history dependencies |
| Read-only transport diagnostics | #597 `e172c542fc` | portal/read-model-scalar-budget-20261111-0832 | Fail-closed 401/403/timeout | Additional security/ACL review required |
| Hostile descriptor hardening | #601 `148c868b8f` | portal/read-only-transport-diagnostics-20261111-0931 | Reject hostile transport descriptors | Depends on #597 |
| Negative transport boundary tests | #605 `ef3f09a15d` | portal/read-transport-own-descriptors-20261111-1033 | Read-only boundary contract tests | Depends on #601; specific Node test NOT_EXECUTED in PR body |

All above PRs were **open Draft** at inspection. A GitHub green workflow is not evidence that a specific listed Node test ran, that server actor/tenant ACL is qualified, or that Debian E2E passed.

## Integration sequence (no merge yet)
1. **Freeze exact heads and enumerate ancestry** using GitHub compare/changed-file lists for each stacked lane; refresh SHAs if moved. Do not silently treat branch tip as a standalone patch.
2. **Select smallest compatible functional slice**: HTTP 405/security header baseline (#538), then a coherent evidence UX/read-only slice with all required ancestors; keep history and transport diagnostics separate until their contracts are proven.
3. **Check overlapping files and behavior**: 401/403, timeout vs transport error, cancellation, stale response, EMPTY/ERROR/UNKNOWN, evidence IDs, Prometheus 1h/6h/24h, 404/405, CSP, keyboard/ARIA, no synthetic data shown as live.
4. **Run exact-head tests**, not only general workflows: `node --test app/portal/components/read_transport_diagnostics.test.mjs app/portal/components/read_transport_boundary_contract.test.mjs` on #605 head (or current equivalent); run Portal tests, Python offline preflight, CI and negative ACL/HITL cases on candidate SHA. Record actual command, exit code and logs; do not mark passed if not executed.
5. **Security gate**: server-derived actor and tenant scope must be qualified. Existing `TENANT_ACL_NOT_QUALIFIED` routes remain blocked. Never bypass Policy/HITL or expose credentials.
6. **Candidate branch + Draft PR only after gates 1–5**: assemble one minimal candidate with explicit ancestor provenance and a diff against current main. No main merge or deployment without explicit approval.
7. **Controlled rootless preflight (future, authorized only)**: `aiops` UID 1001, Docker context `rootless`, socket `/run/user/1001/docker.sock`, root `/home/aiops/.local/share/docker`; last operator proof 87 containers/210 images, main services Up. Do not use `sudo docker` as AIOPS2 evidence. Verify backups, health, E2E, rollback before any targeted update. No docker prune, compose up, data-root migration or reconstruction.

## Stop / rollback criteria
Stop candidate promotion on missing ancestor, conflicting files, failing test, unqualified ACL, absent backup/rollback, or unknown host E2E. Rollback of **this planning PR**: close Draft. Rollback of later code candidate: revert its isolated commits after confirming dependencies; do not roll back production without a separately approved plan.

## Evidence states
- CODE: PRs present, candidate **NOT ASSEMBLED**.
- CI: selected GitHub workflows successful for #605 head, but specific Node command **NOT VERIFIED**.
- DEBIAN: rootless daemon and container inventory confirmed by operator, **NO CANDIDATE DEPLOYED**.
- E2E: **NOT VERIFIED**.

Coordinate via issue #555 and docs/ops/HANDOVER-AIOPS2-CURRENT.md (documentation branch); #557 is the resolved rootful/rootless diagnostic confusion, not a recovery mandate.
