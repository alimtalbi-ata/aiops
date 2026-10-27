# AIOps 2.0 — Project Continuity Record

**Author:** Abdelhalim Talbi  
**Repository:** https://github.com/alimtalbi-ata/aiops  
**Default branch:** `main` (protected by workflow; work on branches and propose PRs)  
**Last updated:** 2026-10-19

## Why this document exists

This is the restart point for future ChatGPT sessions and contributors. Read it before proposing work. Update it whenever a material decision, architecture, interface contract, operational discovery, test result, or delivery changes. Do not rely on chat history as the only record.

## Current direction

Consolidate AIOps 2.0 around one coherent runtime and operations experience. Reuse proven historical AIOps v1 / V145 capabilities when they are faster and safer to adapt than to rebuild. Do not equate a directory, old demo, PID file, or running process with a qualified component: inspect source, contracts, dependencies, tests, and runtime behavior first.

## Known environment snapshot (reported 2026-10-19)

- Host: `SRV-DEB-05`, Debian 13; working root `/home/aiops`.
- AIOps 2.0 runtime families exist, including V8 clean deployment line, V28.3.x Command Center line, and later architecture/implementation investigations.
- Reported active services include portal, core, worker, policy, RAG, intelligence, Temporal, twin, copilot, simulator, evidence, integration, Prometheus and Grafana. Re-check live state before every deployment; this is a dated snapshot, not a current guarantee.
- Historical AIOps v1 source and evidence live under `/home/aiops/aiops-v1`.
- V145-related directories include decision intelligence, evidence fusion/matrix/acquisition/enrichment, semantic evidence engine, decision adapter, functional bridge, functional read model and decision cockpit.
- A first read-only audit was attempted on 2026-10-19. Its terminal paste/output is partially corrupted; module presence and file listings are useful leads, but the report does not qualify these modules or prove their behavior.

## Non-negotiable operating rules

1. **Protect production.** No restart, destructive cleanup, migration, config change, token rotation or production cutover without explicit scope, backup/rollback and a verified preflight.
2. **Preserve main.** Work in a dedicated branch, commit to GitHub, and open a PR. Do not claim a commit exists until GitHub confirms it.
3. **Keep evidence.** Every change must include tests run, exact outcomes, limitations, changed files, and rollback notes. Distinguish source inspection, static tests, integration tests, and live production verification.
4. **No false qualification.** Never label a demo, synthetic run, expected output, or unexecuted test as a real runtime proof.
5. **Fail closed.** Missing, stale, contradictory or unproven evidence is `UNKNOWN`; it must not be silently treated as healthy or successful.
6. **Security boundary.** Keep secrets out of Git, reports, screenshots, chat and logs. Never commit `.env`, tokens, private keys, database files or production exports.
7. **Cumulative handover.** Keep architecture, decisions, component catalog, compatibility/contracts, test evidence and release notes in the repository and update them with every significant delivery.
8. **Reuse before rebuild.** Compare historical v1/V145 code and contracts with current runtime responsibilities; adapt only where boundaries and tests can be made explicit.
9. **Do not silently fallback.** If a preferred adapter/tool is unavailable, report it and require a documented fallback decision.
10. **Do not break PC11K5 fencing guarantees.** Ownership, fencing, preconditions, effect, evidence and reconciliation invariants must remain intact.

## Required reading order for a new session

1. `README.md`
2. `docs/PROJECT-CONTINUITY.md`
3. `docs/ARCHITECTURE-AND-BOUNDARIES.md`
4. `docs/DECISION-LOG.md`
5. `docs/COMPONENT-CATALOG-AND-REUSE.md`
6. `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md`
7. Latest release notes and evidence manifests for the target version.

## Latest source review (2026-10-19)

A focused GitHub source audit is recorded in [SOURCE-AUDIT-2026-10-19.md](SOURCE-AUDIT-2026-10-19.md). The safety patch was merged via [PR #5](https://github.com/alimtalbi-ata/aiops/pull/5) at commit `493336fb51fcda41d1ece8fc1822bb13f1ef232c`: P1 escalates before evidence checks; policy no longer defaults critic validation to true and requires explicit freshness/precondition/fencing/approval inputs; the worker blocks LIVE runs before generating placeholder evidence and marks the Run BLOCKED. Added `tests/test_policy_safety.py` and `.github/workflows/quality.yml`; GitHub Actions run [39223403723](https://github.com/alimtalbi-ata/aiops/actions/runs/39223403723) passed compileall, policy unit tests and static audit. Container build, runtime qualification and synthetic E2E remain unrun. The current main branch includes this conservative guard; LIVE execution is still not qualified. Container build, runtime qualification and synthetic E2E remain unrun. A second hardening change merged via [PR #7](https://github.com/alimtalbi-ata/aiops/pull/7), commit `1bdd7235687f8b2c7081278e4dd86b8a17939ff3`: fresh installs generate random secrets, existing `.env` files are preserved, preflight rejects default secrets outside explicit demo mode, and the admin/internal tokens are checked for consistency. A third change merged via [PR #9](https://github.com/alimtalbi-ata/aiops/pull/9), commit `e6251c1ce195937b1af6019e389c9f6b3f68e2dc`: runtime credential fallbacks were removed, Compose now requires explicit secrets, the secure template is blank, and known demo values are isolated in `config/.env.demo.example`. CI run [39224781141](https://github.com/alimtalbi-ata/aiops/actions/runs/39224781141) passed Python compilation, policy tests, secret-preflight tests, static checks and `docker compose config`.

## Next work queue

- [x] Add deterministic policy safety tests and run them in GitHub Actions; preserve the run link in the source audit.
- [ ] Review and merge the LIVE safety patch only after tests pass and its diff is inspected.
- [ ] Run a corrected, truly read-only inventory of historical v1/V145 source, contracts, tests, and service ownership.
- [x] Audit and harden runtime secret fallbacks and Compose interpolation; merged via PR #9 with passing CI.
- [ ] Inspect current repository tree and deployment files; compare Git-tracked code to the host deployment without copying secrets.
- [ ] Build a reuse matrix: reuse unchanged / adapt behind adapter / replace / retire, each with evidence and owner.
- [ ] Establish one canonical incident/run/evidence/decision schema and versioned API contracts.
- [ ] Verify the complete event path from ingestion to correlation, CMDB enrichment, evidence acquisition, analysis/critic, policy gate, HITL, remediation, verification, rollback and learning.
- [ ] Test replay/simulation separately from LIVE execution, with explicit authorization and idempotency.
- [ ] Add deterministic E2E and failure-injection qualification before enabling any new live action.
- [ ] Produce cumulative deployment ZIP and updated docs/evidence for each version where a release is requested.

## Update rule

Every material change must update this record and the relevant architecture/decision/component/test documents in the same branch/PR. Add a dated entry to `docs/DECISION-LOG.md`; include commit/PR links after they exist. At session end, record exact next steps and unresolved risks here.

## Continuity update — 2026-10-27: ACME NOC, grounded AI, HITL, RAG and remediation lab

**Scope:** architecture and delivery direction only. This entry does not certify deployed functionality, integration compatibility or passing tests. Preserve all earlier operational snapshots and decisions.

### Product objective
Deliver an enterprise-grade, repeatable ACME incident journey: simulated business activity and topology → Checkmk/monitoring alerts and Thruk NOC presentation (subject to backend compatibility) → canonical Core incident → evidence-backed AI investigation and internal-only chatbot → authenticated human review → deterministic Policy gate → Temporal/Worker controlled simulated remediation → technical and business postchecks → GLPI ticket and append-only evidence report.

### Architectural reading order and source of truth
Read this file, `docs/ARCHITECTURE-AND-BOUNDARIES.md`, `docs/DECISION-LOG.md`, `docs/COMPONENT-CATALOG-AND-REUSE.md`, and `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md` before any substantial change. The architecture describes *target* responsibilities; repository source, tests and actual runtime evidence establish implementation status. Existing README and PC11K5 safety constraints remain binding.

### Priorities and next development queue
- **P0 functional baseline:** qualify Portal/Core/Temporal/Worker/Policy/GLPI event-to-run path and real synthetic E2E, no fabricated PASS or successful LIVE effects.
- **P0 investigator and scoped chatbot:** read-only retrieval of authorized ACME incident/CMDB/topology/telemetry/evidence; exact source citations, ACL/RBAC, freshness, missing-evidence abstention and prompt-injection resistance.
- **P0 human-controlled remediation:** authenticated and attributable approve/reject/request-changes decisions; policy validation of the exact immutable action, target, parameters and expiration; fail closed on changed/stale approvals.
- **P1 ACME enterprise twin:** realistic sites, services, dependency graph, user journeys, incident seeds, repeatable telemetry and known ground truth isolated from model inference.
- **P1 NOC:** assess Checkmk and Thruk/Livestatus version compatibility, adapters and licensing before introducing deployment changes; keep one canonical incident authority in Core.
- **P1 Remediation Lab:** catalog versioned Ansible, shell/Python, CLI and API recipes; run in isolated sandbox by default, record redacted inputs, pre/post checks and effect evidence; never execute LLM-generated arbitrary commands.
- **P1 Knowledge Hub:** ingest licensed/allowed official vendor docs plus internal architecture, implementation, operations, runbooks and postmortems, with provenance, version, ACL, update/retention rules; consider PostgreSQL full-text + pgvector only after sizing.
- **P1 Golden Demo:** show NOC alarm → investigation → cited knowledge → HITL decision → simulated action → technical and business verification → Evidence Studio and replay.

### Concrete acceptance evidence required
At minimum: a deterministic seeded incident with a stable CMDB CI and impacted business service; a documented runbook citation; a refused HITL request that produces zero effects; a valid approval for an exact action and target; a simulated execution record with real sandbox outputs (never fake LIVE success); a negative postcheck that cannot close the incident; an ACL-denied chatbot query; a no-evidence chatbot abstention; and an E2E test that exits nonzero on missing Portal visibility.

### Current status and handover
Architecture/documentation only in this change; no service deployed, no integration validated, no tests executed. Existing draft PR #37 addresses synthetic E2E run visibility separately and must not be assumed merged. Next engineer should inventory current branches and adapters, implement a narrow vertical slice behind feature flags, run deterministic tests, record actual results, and open a separate draft PR. No direct merge or production mutation.
