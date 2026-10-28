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


## 2026-10-27 — HITL sandbox one-use approval lab (PR #49)

Added a local SQLite-only HITL library and tests on [PR #49](https://github.com/alimtalbi-ata/aiops/pull/49). Proposals bind incident/run/allowlisted recipe/target/parameter hash/mode; approvals require distinct human actor role, expire and are consumed once atomically. No shell or remediation executor is present. Returned postchecks and rollback are `NOT_EXECUTED`, never `PASS`. Local unit suite: 16 tests passed; GitHub Actions and runtime integration are separate gates. **NOT integrated** into authenticated Core/Temporal/Portal or Golden Demo; no LIVE qualification. See [HITL sandbox contract](architecture/HITL-SANDBOX-CONTRACT-20261027.md). Next micro-lot: authenticated Core facade and truthful Golden Demo states, then real isolated integration tests.


## 2026-10-27 22:25 — HITL Golden Demo en lecture seule (PR #49, second incrément)

- Extension du laboratoire HITL SQLite par `read_status` : lecture seule, audit cohérent, expiration et reçu mono-usage, projection expurgée sans token.
- `demo/hitl_golden_demo.py` produit trois états observés de la bibliothèque sandbox et un digest d'intégrité locale, sans appeler Core/Temporal, sans remédiation et sans fausse attestation.
- `app/portal/hitl_demo_read_model.py` apporte `/demo/hitl` et `/api/demo/hitl` au portail unique. Si aucun artefact n'est configuré : `NOT_CONFIGURED`. Sinon, lecture bornée et stricte d'un JSON de simulation monté en lecture seule, sans jeton et sans écriture backend.
- Tests négatifs `tests/test_hitl_story.py` ajoutés au workflow existant `quality.yml`; qualification CI à relever dans le journal du lot. La démonstration de la bibliothèque ne constitue **pas** une approbation authentifiée Core ni une remédiation réelle.
- Réutilisation ciblée : principe de réservation `SIMULATION_ONLY` de PR #36 `app/policy/execution_fence.py` et posture CSP du portail synthétique, sans dépendance au store d'autonomie ni fusion massive.
- Prochain lot : liaison à Core et à une identité RBAC authentifiée, écriture Evidence et projection du Run canonique, puis sandbox réellement isolée avec postchecks vérifiés. LIVE reste bloqué.


## 2026-10-28 03:20 Europe/Paris — HITL persisted binding hardening (stacked PR #79)

- Branch `fix/hitl-sandbox-stored-binding-20261028-0320` extends **only** draft PR #49, not `main`. Its `dry_run` now compares every stored incident/run/recipe/target/params-hash/mode field to the requested binding, checks the stored proposal TTL, and verifies the stored hash and one-use approval token before recording a receipt.
- Negative tests cover partially tampered SQLite proposals and extended expiry; a concurrent two-consumer test asserts one sandbox receipt. Tests are wired via the existing `quality.yml` HITL unit test step; confirm exact-head Actions status in the automation log.
- This is a local SQLite **sandbox integrity guard**, not proof against a malicious DB owner, a signed approval, authenticated RBAC, or permission for LIVE remediation. Core/Temporal/GLPI integration and real container E2E remain NOT_TESTED.
- Rebase/port this narrow patch after #49 is reconciled with main; never merge the entire divergent #36 candidate.


## 2026-10-28 04:23 Europe/Paris — HITL audit verification at sandbox consumption (stacked PR #84)

- In `app/shared/hitl_lab.py`, the same atomic SQLite transaction that consumes a one-use sandbox approval now checks stored proposer/approver separation and exact two-entry audit action/actor/timestamp consistency before recording a receipt.
- Negative regression tests in `tests/test_hitl_lab.py` reject forged approver identity, missing/extra audit rows, and modified audit actors/timestamps, with no receipt.
- Reuses PR #36's fail-closed, simulation-only admission principle; no mass merge. Existing `quality.yml` runs HITL tests; see `docs/automation-runs/20261028-0423-hitl.md` for actual CI status.
- PR #84 is stacked on #79 -> #49. It is not an authenticated RBAC boundary or cryptographic audit against a malicious DB owner; no LIVE action, no runtime qualification.
