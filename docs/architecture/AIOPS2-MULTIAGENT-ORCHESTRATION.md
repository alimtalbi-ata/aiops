# AIOps2 — autonomous multi-agent orchestration contract
Status: CANDIDATE, no production deployment. Source of truth: GitHub; operational truth: signed/timestamped Debian receipts. Existing five hourly ChatGPT automations are the orchestrators, not five newly created schedulers.

## Coordination and ownership
| Role | Cadence Europe/Paris | Owns | Must not modify without cross-role handoff |
| --- | --- | --- | --- |
| Integration | H:00 | release gates, manifests, architecture, handoff consolidation, Debian provenance | Core/Worker/Portal/Twin application source |
| Core | H:12 | Run, Incident, xref, Policy admission and DB contracts | Worker and Portal business logic |
| Worker | H:24 | Temporal, Analyst/Critic, action-bound HITL, Evidence handoff | Core DB schema and Portal UI |
| Twin | H:36 | isolated scenarios, topology/impact and negative E2E | live infrastructure and customer data |
| Portal | H:48 | read-only UX, trace, FS1113 cancellation and HITL views | Core xref writes and Policy authorization |

Every role uses its own branch/worktree and one issue per workpackage. Branch names: `agent/<role>/<issue-number>-<slug>`. Never share a writable worktree or commit directly to `main`, `deploy/aiops2-stable`, the audit branch, or `ops/debian-runtime-reports`. Existing role branches may be retained; do not silently rename. PRs target the agreed integration base and remain DRAFT. Do not auto-merge.

## Machine-readable handoff (one file per role)
Path `docs/handoffs/<role>/latest.md` in the role's own branch, or an issue comment if no branch write access. Fields: UTC timestamp; issue; role; branch and full SHA; changed paths; interfaces touched; dependencies/blocked-by; test commands and outcomes; GitHub Actions URLs and exact SHA; Debian receipt path, timestamp and freshness; E2E result; CODE/CI/DEBIAN/E2E statuses; risks/rollback; next owner and next action. `UNKNOWN` when unverified. Only Integration consolidates global continuity; no role edits the same shared canonical document concurrently.

## Issue-to-Codex handoff
A role creates/updates an issue with objective, exact source branches and reusable components searched, owned files, interface version, acceptance tests, dependency issues, risk, and stop conditions. Codex execution is **not automatic merely because an issue exists**. Use an explicitly connected Codex execution environment or a separately approved GitHub-to-Codex dispatcher; until then, schedules may inspect GitHub, commit to isolated branches and leave dispatch-ready issues. Never claim an agent ran without a job receipt.

## Gates and stop conditions
G0 source/CI: exact SHA, tests, security and compatibility checks. G1 provenance: running Debian image digest, Compose project, source/build mapping and fresh reporter receipt. G2 isolated integration: PostgreSQL, authenticated GLPI readback, idempotence, concurrent delivery, Policy denial and HITL fences. G3 real E2E: event → Core → Intelligence/Critic → Policy → Temporal/Worker → Evidence → Portal → ITSM with independently verifiable evidence. G4 customer install/rollback qualification. Gate progression is never inferred from PR text, CI alone or image tags.

No writes to live GLPI, PostgreSQL, Debian, crontab, Compose, containers or volumes; no ticket duplication, HITL bypass, Policy/Critic override, auto-merge or deploy without separate explicit approval. Preserve 44 existing FS1130 links and five Compose stacks. A safe denial is not a failure. If evidence is stale or missing, fail closed.

## Parallelism / collision policy
Before writing, search all branches and open PRs for existing implementation. Declare touched paths in issue. If another active issue owns a path or contract, stop and request Integration arbitration; never force-push or overwrite. Prefer additive, independently testable work. CI must distinguish tests in synthetic fixtures from real Debian observations. Integration selects an integration order based on dependency DAG, not schedule completion time.

## Reporting
Five role handoffs are inputs; Integration produces **one** user-facing hourly summary with new SHA/PR, CI, Debian receipt freshness, E2E and blockers. Other roles should not send redundant user summaries. Schedules do not constitute a real-time background Codex dispatcher. No new cron or GitHub Actions workflow is introduced by this contract.
