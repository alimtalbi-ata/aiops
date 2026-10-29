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

## 2026-10-28 07:09 Europe/Paris — NOC signed tenant-scope refusal (draft)

On main starting SHA `88cb4ed01706ac09bb8e01fdceead422cab2590d`, a dedicated P0 draft adds a conservative tenant-scope fence to the existing signed NOC read-model bridge. HMAC verification authenticates bytes but cannot authorize cross-tenant reads with a shared operator token. Nested tenant/org/workspace/account/customer claims (including null, camelCase and Unicode compatibility spellings) now cause a redacted 503 instead of a silently unscoped projection. The scan is bounded. Unscoped signed DEMO read models remain read-only and unattested. Tests run via existing `quality.yml`; see `docs/automation-runs/2026-10-28-0709-p0-noc-signed-tenant-fence.md`. This is not a tenant ACL implementation, Checkmk/Thruk integration, Grafana observation or LIVE qualification. Next: authenticated tenant identity and Core ACL enforcement with real ephemeral services.

## 2026-10-28 08:16 Europe/Paris — NOC scope aliases after PR #99

After merging [PR #99](https://github.com/alimtalbi-ata/aiops/pull/99) at `aae50b02557143ea5a7f0f2633271a0602de8800`, the signed NOC tenant fence receives a narrow follow-up for indirect scope names (`ownerTenantId`, `projectTenantID`, `orgRef`, `accountRef`, etc.) before any projection. Tests cover rejection of validly HMAC-signed nested claims and non-regression for unrelated metadata. No authenticated Core tenant ACL or Checkmk/Thruk integration is claimed; all observed/LLM/LIVE qualification remains blocked. See `docs/automation-runs/2026-10-28-0816-p0-noc-scope-aliases.md`.

## P0 portail — navigation intégrations authentifiée (2026-10-28 09:09 Europe/Paris)

- [PR #103](https://github.com/alimtalbi-ata/aiops/pull/103) fusionnée par squash dans `main` au SHA `9ccbdd5a9e19826fd03f83bc071671473648c45a`, après tests GitHub Actions verts sur le dernier HEAD : [push 40654514583](https://github.com/alimtalbi-ata/aiops/actions/runs/40654514583), [PR 40654521757](https://github.com/alimtalbi-ata/aiops/actions/runs/40654521757) ; [CI post-fusion 40654630767](https://github.com/alimtalbi-ata/aiops/actions/runs/40654630767) également `completed/success`.
- `GET /api/portal/components` est protégé par le Bearer viewer partagé NOC ; l'HTML anonyme ne divulgue plus les URLs d'intégration ; la navigation utilise un jeton à usage unique, une requête sans cookies et un rendu DOM fail-closed. Les 4 tests Node DOM couvrent faux état LIVE, URL script, identité dupliquée, HTTP refusé et réponse tardive après effacement. Reprise ciblée du contrat de PR #36, sans merge massif.
- **Limites :** le portail historique lit toujours Core/Twin anonymement ; DEMO et Copilot ne sont pas encore protégés dans `main`. Les PR #74/#57/#70/#51 doivent être convergées, et #98 requalifiée comme chevauchement. Aucune qualification réelle des conteneurs, navigateur, Ollama/NGX, Debian, ni LIVE. Journal : [2026-10-28T0906-P0-portal-navigation-browser-contract.md](automation-runs/2026-10-28T0906-P0-portal-navigation-browser-contract.md).

## 2026-10-28 10:04 Europe/Paris — P0 Core/Twin anonymous shell and read gate (merged #114)

A small port from draft PR #74 replaces anonymous Core/Twin fetches with an UNKNOWN-only shell and adds explicit viewer Bearer bootstrap reads, reusing the merged PR #36 NOC token gate rather than duplicating auth. The one-shot browser view rejects malformed or falsely LIVE-attested envelopes. Tests are added to existing quality workflow. This is source/contract work only, not tenant ACL, container integration or Debian LIVE qualification. See `docs/portal/BOOTSTRAP-CONVERGENCE-P0.md` and the dated automation log. Next: converge DEMO/Copilot auth PR #57/#70, then tenant ACL and real container integration.

### P0 Core/Twin promotion — 2026-10-28 10:09 Europe/Paris

[PR #114](https://github.com/alimtalbi-ata/aiops/pull/114) merged at `cea1ed7b54ed34cf4b036b6d5f20bf968c9dac09` after green [push CI 40661742307](https://github.com/alimtalbi-ata/aiops/actions/runs/40661742307), [PR CI 40661749480](https://github.com/alimtalbi-ata/aiops/actions/runs/40661749480), and [post-merge CI 40661890151](https://github.com/alimtalbi-ata/aiops/actions/runs/40661890151). Core/Twin bootstrap now requires the shared viewer token and anonymous home is UNKNOWN-only. Tests are in-process plus synthetic DOM; only Grafana is tested as a real ephemeral container. DEMO/Copilot remain unsecured in main, no LIVE qualification. See the 10:04 automation journal.

## 2026-10-28 10:30 Europe/Paris — Policy LIVE HITL convergence (draft PR #118)

- `main` starting SHA `bb4665ab0eb41b43df43ea893e28ac86ef640863` still allowed LIVE mutating Policy `PASS/ALLOW` with a caller-controlled `human_approved=true`. The earlier draft #76 was conflicted with main. PR [#118](https://github.com/alimtalbi-ata/aiops/pull/118) ported only the two Policy code/test files from #76; merged at `b33f655695949d6fef9e7d72b537d9810859c494` after [PR CI #40664618475](https://github.com/alimtalbi-ata/aiops/actions/runs/40664618475) and [post-merge CI #40664759313](https://github.com/alimtalbi-ata/aiops/actions/runs/40664759313) succeeded. PR #76 was closed as superseded. No mass merge of #36 or #49.
- Four LIVE effect commands are denied independently of the boolean. Added HTTP in-process negative tests for forged approvals, invalid modes/commands and synthetic SIMULATE behavior; the existing quality workflow is reused. Verify the exact latest GitHub Actions run before merging; no container integration or LIVE proof is claimed.
- Remaining P0: Core-owned authenticated actor/RBAC, immutable incident/Run/recipe/target/params binding, expiring single-use approval consumption, append-only Evidence, Temporal resume and sandbox-only postchecks/rollback. Stack #49→#106 remains draft and must be reconciled selectively.
- No Debian/NGX access, deploy, production secret or LIVE command. See `docs/automation-runs/20261028-1030-hitl-policy-convergence.md`.

## 2026-10-28 11:01 Europe/Paris — P0 Golden DEMO operator RBAC (merged #122)

The legacy `POST /api/demo` no longer accepts anonymous writes. [PR #122](https://github.com/alimtalbi-ata/aiops/pull/122) was merged as `2253bd21bd948a349b9b7a4a941ecf1e3357d96c` after green [push CI](https://github.com/alimtalbi-ata/aiops/actions/runs/40668539080), [PR CI](https://github.com/alimtalbi-ata/aiops/actions/runs/40668555197), and [post-merge CI](https://github.com/alimtalbi-ata/aiops/actions/runs/40668685395). The operator token is separate from viewer/internal credentials, generated for new installs and passed explicitly via Compose. Upstream receipts are checked and projected as `DEMO_SUBMITTED_UNVERIFIED`, never LIVE. HTTP tests are in-process; only Grafana has a real ephemeral-container CI test. Existing `.env` files remain unchanged and must be configured manually. Core/Temporal, Copilot auth, browser captures and Debian/LIVE remain unqualified. See [automation journal](automation-runs/2026-10-28T1101-P0-golden-demo-operator-rbac.md).


## 2026-10-28 11:08 Europe/Paris — P0 NOC authenticated Core synthetic projection (draft)

Dedicated P0 branch from main `723ca6458c722a1aa0e57ddb5eee3374d20cc830`: shared tenant-scope refusal logic extracted from the existing signed NOC adapter into `app/shared/tenant_scope.py`; new Core-only `GET /api/noc/runs/{rid}` requires the internal Bearer token, joins the actual Incident in PostgreSQL, denies LIVE/non-synthetic/missing/tenant-scoped records and returns only four Run fields. The portal's signed NOC correlation now calls this bounded Core endpoint rather than the legacy anonymous full Run endpoint. No tenant ACL, observed Checkmk, RAG diagnosis, Grafana metric or LIVE attestation is claimed. The existing `quality.yml` is extended with real Core HTTP and PostgreSQL 16 ephemeral integration; no mocks in that integration. Tests/CI outcome and PR link: see the dated journal `docs/automation-runs/2026-10-28-1108-p0-noc-core-read-auth.md`. Legacy Core read endpoints remain outside this incremental change and require a separate access-control design.

## 2026-10-28 11:15 Europe/Paris — Worker simulation/Policy fence (draft)

Targeted reuse of the existing #72 / #36 `simulation_policy_contract` on current main. The Worker rejects invalid execution modes before Temporal connection or stage effects; DEMO/REPLAY/STORY send OBSERVE to Policy, not EXECUTE. LIVE continues to hit the existing emergency stop and Policy HITL refusal. The helper and AST regression tests are reused without a mass merge. This is unit/static qualification only; no Core/Temporal/Twin/Evidence integration or HITL approval claimed. See `docs/automation-runs/2026-10-28-1115-p0-worker-policy-mode.md` for exact CI status and follow-up.


## 2026-10-30 — GitHub scheduled qualification and Debian runtime smoke (candidate branch)

- Branch: `ops/automated-runtime-cron`. Existing `.github/workflows/quality.yml` now also runs daily at 02:23 UTC and supports manual dispatch; existing PR/push triggers remain.
- New `.github/workflows/runtime-smoke.yml` schedules read-only checks every 15 minutes on a repository-scoped self-hosted runner labelled `aiops2-runtime`. New `scripts/runtime-smoke.sh` checks the known Core/Worker/Policy/Evidence containers, HTTP health, the synthetic Golden Payment scenario, deployed Worker image and non-null `observed_at` code contract, plus Worker-to-Temporal TCP connectivity. It does not create Runs/incidents, write Evidence, call GLPI, restart services or remediate.
- Runner installation is a one-time operator action documented in `docs/automation/RUNTIME-CRON.md`. Until that runner is online and the PR is merged to main, the 15-minute runtime schedule is not active.
- Source/runtime divergence discovered: GitHub main Worker source differs from the deployed fixed Worker image on SRV-DEB-05. Do not rebuild/deploy main Worker over the deployed image until reconciled in a reviewed change.
- Qualification status at branch creation: source files committed to branch; GitHub PR checks and runtime smoke have not yet been executed. The old pilot `RUN-2646AF806DC7CB40` remains BLOCKED; no new pilot or LIVE qualification is claimed.
