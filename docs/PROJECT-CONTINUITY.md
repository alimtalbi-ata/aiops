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


## 2026-10-27 — P0 portal integration/navigation increment (PR #46)

- Ported only `app/portal/platform_registry.py` from PR #36 (source blob `969b5f7fdc4f654cca5f6d3b6ed6e2a004f5fd8d`), with separate operator-configured external navigation and `GET /api/portal/components`.
- `GET /api/portal/bootstrap` and the portal homepage now treat failed/malformed Core dashboard, Run list and Twin summary reads as `UNKNOWN`/`null`, not fabricated empty healthy data. The response state `READABLE_UNVERIFIED` is not runtime attestation.
- Compose external portal port defaults to `17777` (override `AIOPS_PORTAL_HOST_PORT`); qualification/static checks and synthetic E2E default were aligned. This is source configuration only, not a claim about Debian runtime.
- External links to n8n, Thruk, Checkmk, Grafana, GLPI are disabled until explicitly configured. No proxy, RBAC qualification, live screenshots or service integration proof. Evidence/incident dedicated read models await access-control design.
- Targeted tests are in `tests/test_portal_integrations.py` and `tests/test_portal_read_models.py`; quality workflow is reused. Initial PR head `dbdbfbe0113e862d9428c69af14ca278a84aa2e8` passed [GitHub Actions 40574864665](https://github.com/alimtalbi-ata/aiops/actions/runs/40574864665), including compilation, portal unit tests, static audit and Compose config. This is not container E2E or Debian qualification.
- Full operator configuration, limitations and next steps: `docs/portal/INTEGRATION-NAVIGATION-P0.md`. Continue with authenticated RBAC read models and real ephemeral integration services; preserve UNKNOWN and LIVE fencing.


## 2026-10-27 — NOC authenticated read-model seam (draft PR)

A targeted port from PR #36 adds `app/portal/noc_runtime.py` with signed/HMAC-verified read-only NOC snapshots, operator Bearer auth and an explicitly UNKNOWN portal NOC panel. The source and tests are not runtime qualification. Full configuration, trust and multi-tenant limitations are documented in `docs/architecture/NOC-SIGNED-READMODEL-BRIDGE-20261027.md`. Next: real Checkmk/Thruk upstream provider and correlation to canonical Core Run/Incident, then evidence-grounded Analyst/Critic via NIM/Ollama adapter PR #44. No Debian or LIVE access performed.

## 2026-10-27 — P1 ACME SAN → Payments synthetic impact (draft PR #50)

A targeted port of PR #36's fixture, dependency DAG validator and read-only impact view adds `GET /api/demo/acme-impact` and `GET /demo/acme-impact` to the canonical portal, with a visible navigation link. Source SAN P1 incident `ACME-DEMO-SAN-001` and Payments P2 impact `ACME-DEMO-PAY-002` are stable synthetic fixture IDs; derived run and ticket labels are not Core/Temporal or GLPI IDs. No real GLPI ticket or runtime capture is claimed. Tests are wired into existing quality workflow; verify latest PR #50 check conclusion before merging. Next: authenticated correlation of real Core Run/Incident/GLPI IDs, preserving mode and evidence provenance. See `docs/demo/ACME-SAN-PAYMENTS-IMPACT-20261027.md`.

## 2026-10-27 — NOC signed payload to canonical Run read-only correlation (candidate)

The P0 NOC track adds `app/portal/noc_correlation.py` and a guarded portal drilldown in a dedicated draft PR. It reuses the PR #36 / merged PR #47 signed NOC read-model contract without importing synthetic RAG fixtures into the runtime. Exact Run/Incident identity is compared with the independently fetched Core Run; mismatches are UNKNOWN. A matching identity is explicitly MATCHED_UNATTESTED and does not establish live monitoring, Grafana or RAG quality. DEMO/REPLAY/STORY remain synthetic; LIVE is unqualified. No DB writes or remediation.

**Known blockers:** no verified real Checkmk/Thruk or Grafana integration, no per-tenant Core/portal read ACL, no runtime attestation or actual model grounding. The inspected Core GET endpoint is unauthenticated; do not expose it publicly. See `docs/architecture/NOC-CANONICAL-RUN-CORRELATION-20261027.md` and the corresponding dated automation run log for tested scope and limitations.


## 2026-10-27 23:16 Europe/Paris — P0 NOC correlation merged, synthetic RAG fixture drilldown (PR #54)

- PR #52 was reviewed against main SHA `b85383f201c976397a512c9beb31857ddf7c1638` and GitHub Actions quality run [40585273487](https://github.com/alimtalbi-ata/aiops/actions/runs/40585273487), which reported completed/success for the correlation test and existing quality gates. It was merged with squash commit `81ab8ae2bfae8f8b5767578b8fcd772f82fffe82`. This proves unit/static/Compose-config checks, **not real Checkmk/Thruk or Core integration**.
- Merged [PR #54](https://github.com/alimtalbi-ata/aiops/pull/54) (squash SHA `b44b7f2ffcddecaf5229a4e5fd4c745e038a0c98`, verified green [CI run 40594299546](https://github.com/alimtalbi-ata/aiops/actions/runs/40594299546)) ports only PR #36's six synthetic RAG reference cases into the canonical portal. `GET /api/noc/demo-rag` requires the operator read token and returns exact asset citations with SHA-256, `SYNTHETIC_REFERENCE_ONLY` or `UNKNOWN`; the NOC panel offers an explicit DEMO drilldown. There is no actual LLM inference, NIM/Ollama call, Grafana observation, source runtime attestation or LIVE action.
- Security and qualification: no multi-tenant Core/portal ACL yet; the shared read token is **not tenant-scoped**. The synthetic endpoint must not be promoted to real RAG without pre/post-retrieval ACL, authoritative citations, source freshness and canonical Run binding. Existing `quality.yml` runs the new offline contract tests; PR #54 Actions are green for static/contract/Compose checks only; no real service integration is qualified. See `docs/architecture/NOC-SYNTHETIC-RAG-DRILLDOWN-20261027.md` and `docs/automation-runs/2026-10-27-2316-p0-noc-rag-fixture.md`.

## 2026-10-28 — P0 component registry read authorization (draft PR)

The portal component navigation JSON endpoint is being hardened with the existing
`AIOPS_PORTAL_READ_TOKEN` Bearer viewer contract already used by the signed NOC
read-model adapter (targeted PR #36 reuse). Anonymous, invalid and unconfigured
requests must fail closed before building navigation. No link or registry state
attests runtime availability; configured links remain `CONFIGURED_UNVERIFIED`.
The legacy HTML home page can still render configured links anonymously and is
**not** globally authenticated: this micro-lot does not claim complete portal RBAC.
Unit HTTP tests are wired into existing `quality.yml`. Real container integration,
NGX, Debian and LIVE qualification are `NOT_TESTED`. Merge only after GitHub
checks and conflict review; rollback is reverting this route-only patch.
