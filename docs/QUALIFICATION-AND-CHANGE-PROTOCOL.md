# AIOps 2.0 — Change and Qualification Protocol

**Author:** Abdelhalim Talbi

## Before a change

- Identify target runtime/version, source branch/commit and production impact.
- Inspect current service state, repository status, relevant contracts and active dependencies.
- Create a timestamped backup of files/configuration to be changed; do not bundle secrets into Git or chat.
- Define preconditions, expected result, stop conditions and rollback procedure.
- Confirm DEMO/REPLAY/LIVE mode and credentials scope.

## Test evidence labels

1. **Source inspection:** code read; no execution implied.
2. **Static:** lint, type checks, static audit or contract-shape checks.
3. **Unit/contract:** isolated deterministic tests.
4. **Integration:** cooperating services in an isolated environment.
5. **Synthetic E2E:** full flow using explicitly synthetic events and data.
6. **Live verification:** actual deployed service/API verified; report timestamp, endpoint, status and redacted result.
7. **Production qualification:** approved test window, safety checks, observed results, audit trail and rollback readiness.

Always list failed, skipped and not-run tests. Expected output is not evidence of actual execution.

## Change and promotion gates

- No direct main changes: branch → tests → commit → pull request.
- No automatic merge unless separately authorized.
- No production restart/cutover as a side effect of documentation or source changes.
- No live mutation from synthetic/demo flows.
- High-risk actions require policy authorization and human approval where policy requires it.
- Check fencing/ownership, current preconditions, idempotency, effect evidence, verification and reconciliation.
- Test partial failure after external effect, timeout, duplicate delivery, worker restart, stale evidence and rollback failure.
- Keep all logs and reports secret-safe.

## Release/handover checklist

- [ ] Component and API contracts updated.
- [ ] Architecture and decision log updated.
- [ ] Reuse matrix and catalog updated.
- [ ] Automated tests and exact outcomes recorded.
- [ ] Version, changelog, manifest and hashes updated where applicable.
- [ ] Install/upgrade/rollback steps tested or explicitly marked untested.
- [ ] Cumulative ZIP includes required source/scripts/docs/evidence, without secrets or runtime databases.
- [ ] Commit and PR verified on GitHub.
- [ ] Next steps, unresolved risks and current runtime snapshot recorded in `docs/PROJECT-CONTINUITY.md`.

## Additional gates — ACME NOC / HITL / RAG / Remediation Lab (2026-10-27)

### Design and implementation
- Document source version, exact API contract, canonical state owner, target CI, security scope and rollback before enabling a new adapter.
- Checkmk/Thruk: prove actual edition/version/backend compatibility, REST/Livestatus semantics, read-only monitoring path, permissions, deduplication and downtime/ack mapping; do not assume they are installed.
- RAG: ingest only licensed/authorized content; record provenance and doc version; validate ACL before retrieval and before citation; test deletion/reindexing, poisoning, stale/conflicting documents and abstention. Never treat vendor docs as evidence of live ACME state.
- Chatbot: restrict to read-only user-authorized ACME sources; test no-evidence questions, cross-role/tenant access, malicious retrieved instructions, hidden secrets and hallucination refusal.
- HITL: require authenticated actor, role, distinct approver where necessary, exact recipe/target/parameters/version, expiry, reason and immutable audit. Reject, revision, replay and expiry must not trigger effects.
- Remediation: versioned allowlisted recipes, typed parameter validation, sandbox by default, explicit mode/credentials boundary, preconditions, dry-run, bounded timeout, idempotency, compensation/rollback, technical and business postchecks.
- Demo: record seed, expected ground truth (not fed to investigator), CMDB snapshot, event correlation IDs, source citations, approval receipt, execution mode and postcheck results. Missing visibility, invalid citations or failed postchecks must fail tests.

### Mandatory negative test matrix
| Test | Expected result |
|---|---|
| Missing or stale CMDB/document evidence | UNKNOWN / abstain / no unsafe action |
| Unauthorized NOC chatbot user | No data disclosure, logged denial |
| Prompt injection inside retrieved document | Ignored as instructions; policy unchanged |
| HITL reject / expired / changed proposal | No remediation effect |
| Duplicate approval or Temporal retry | At most one authorized effect; reconcile |
| Sandbox action attempts LIVE network/credential access | Blocked |
| Remediation timeout / partial effect | Explicit state, reconciliation, compensation where possible |
| Failed technical or business postcheck | No false RESOLVED or successful evidence |
| Thruk backend incompatibility | Report limitation, no invented NOC integration |
| Golden Demo Portal run ID absent | Nonzero E2E failure |

### Evidence requirements
Every PR should state: files changed; source inspections performed; exact tests invoked and their exit codes; tests not run; CI URLs if available; security impact; rollback and deployment prerequisites. Documentation-only changes require link/format review but do not imply runtime qualification. Never merge automatically or perform production remediation.
