# AIOps 2.0 — Project Continuity Record

**Author:** Abdelhalim Talbi  
**Repository:** https://github.com/alimtalbi-ata/aiops  
**Default branch:** `main` (protected by workflow; work on branches and propose PRs)  
**Last updated:** 2026-10-20

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

## Core AI quality contract added (2026-10-19, branch feat/core-analysis-quality-v2)

New documents on the working branch:
- [Core analysis quality contract](CORE-ANALYSIS-QUALITY.md): analyst/critic schemas, evidence dimensions, prompt-injection boundary, deterministic gate, metrics and capitalization.
- [Core implementation gap analysis](CORE-IMPLEMENTATION-GAP-ANALYSIS.md): source-confirmed finding that Copilot currently returns deterministic summaries rather than performing LLM diagnosis; prioritized work to implement real provider-backed Analyst/Critic.
- [Decision, remediation and learning architecture](AI-DECISION-AND-LEARNING-ARCHITECTURE.md): canonical record separation, proposal/approval/effect/verification boundaries, PC11K5 invariant chain and staged roadmap.
- [Core qualification matrix](CORE-QUALIFICATION-MATRIX.md): test scenarios for core, AI quality, policy, remediation, learning and deployment. All new rows remain NOT RUN until executed.
- [Database schema catalog](DATABASE-SCHEMA-CATALOG.md): source-derived map of existing migrations and the proposed AI decision-ledger gap.
- [Stack deployment inventory](STACK-DEPLOYMENT-INVENTORY.md): source-derived service/network responsibility and deployment-kit acceptance criteria.
- [Accelerated rebuild plan](ACCELERATED-REBUILD-PLAN.md): prioritized build and release gates.
- [Deployment and recovery runbook](DEPLOYMENT-AND-RECOVERY-RUNBOOK.md): install, migration, backup/restore, package and model evaluation.
- [AI quality evaluation protocol](AI-QUALITY-EVALUATION.md): golden set, metrics and promotion gates.

The branch now includes the initial provider-backed Analyst/Critic, Worker wiring, explicit AI decision-ledger migration and Core APIs for normalized persistence, hash-bound remediation proposals, role-scoped human approval and curated learning ingestion. The Copilot itself still constructs a fixed evidence summary and is not the LLM diagnostic engine. Full stack image builds and clean PostgreSQL migration execution pass in CI; the upgrade runner is being qualified against a legacy-only schema. Actual model inference, full Temporal E2E and production runtime remain unqualified. Keep ACME twin/demo expansion behind these gates.

## Update rule

Every material change must update this record and the relevant architecture/decision/component/test documents in the same branch/PR. Add a dated entry to `docs/DECISION-LOG.md`; include commit/PR links after they exist. At session end, record exact next steps and unresolved risks here.


## Core Analyst/Critic adapter increment (2026-10-19)

- Added a separate FastAPI service under app/intelligence with an OpenAI-compatible chat-completions adapter, strict top-level Pydantic contracts, required internal-token authentication, bounded provider timeout, provider-unavailable behavior, and evidence-ID reference checks.
- Added the service to Compose on the internal control network and added optional LLM provider variables to the safe .env template.
- Added deterministic contract tests and wired them into the quality workflow.
- GitHub Actions run 39312217053 passed compileall, existing policy safety tests, new intelligence contract tests, secret preflight, static repository audit, and Compose configuration validation: https://github.com/alimtalbi-ata/aiops/actions/runs/39312217053
- Worker integration: the Worker now calls Analyst/Critic for DGX_ANALYST/DGX_CRITIC, stores structured outputs in run-event payloads, blocks on provider/contract failure, and derives the policy input from the returned analysis/critique. The synthetic OBSERVE stage creates two explicitly synthetic twin-simulator evidence records; generic stage markers are filtered out of the AI evidence input.
- The service remains unqualified against an actual local model endpoint. Runtime container build, model inference, Temporal E2E, persistence/replay behavior and the complete failure matrix remain untested. The latest GitHub Actions run 39313131331 passed compileall, policy tests, intelligence contract tests, secret preflight, static audit and Compose config: https://github.com/alimtalbi-ata/aiops/actions/runs/39313131331.
- No Debian host, production containers or live infrastructure were accessed. LIVE execution remains blocked.



## Accelerated rebuild increment (2026-10-19, same PR #21)

### Implemented on branch
- Added migration 009 for analysis, critique, policy decisions, proposals, approvals, effect receipts, verification, reconciliation, learning cases and model-evaluation runs.
- Added an explicit checksummed migration runner for already-initialized PostgreSQL volumes. It verifies a legacy-schema signature, records a baseline for 000–008 and fails closed on schema drift/incomplete schema.
- Added Core APIs to persist/query analysis, critique and policy records; proposal creation is bound to a validated analysis/critique and exact evidence IDs; approval is bound to immutable proposal hash and scope; CRITICAL approval requires two distinct actors/roles; synthetic runs cannot create real approvals.
- Added learning ingestion with reviewer identity/rationale, verification reference and database/application checks that prohibit synthetic or unreviewed cases from gold-set eligibility.
- Added repeatable synthetic model evaluation fixtures/runner, deployment/recovery runbook, full-stack database/volume backup and explicitly guarded restore scripts, diagnostic bundle, cumulative package manifest/checksums and CI artifact upload.
- CI now builds every application image, runs static/unit/security contract tests, applies the full SQL chain to disposable PostgreSQL, and separately exercises the upgrade runner against a legacy-only schema. Do not infer model quality or live safety from those checks.

### Current verified CI evidence
- Clean migration chain and full image build/package passed in run 39315470210: https://github.com/alimtalbi-ata/aiops/actions/runs/39315470210
- Upgrade runner initially exposed a CI startup race: PostgreSQL's temporary initdb socket reported ready before TCP startup. The workflow was changed to wait for TCP readiness; the new result must be checked before marking this gate PASS.
- Latest cumulative artifact from earlier successful CI is only a previous snapshot and should not be treated as the newest branch release until the post-change workflow produces a fresh artifact.

### Immediate next actions
1. Confirm latest CI jobs, especially migration-runner-upgrade and core-ledger contract.
2. Fix any remaining failures; regenerate the cumulative ZIP from the passing commit and verify SHA-256.
3. Review the generated package contents and ensure no .env, backups or diagnostics are present.
4. Add/execute disposable Temporal E2E with a deterministic fake provider and explicit provider timeout/malformed-output/retry tests.
5. Keep LIVE execution disabled; only then progress toward real evidence adapters and ACME twin qualification.

## RECONSTRUCTION MILESTONE — 2026-10-20 (supersedes earlier CI pending notes)

**Status:** latest verified release-producing commit `65ee946d31030c18ee554f572130295b9b82be46` on branch `feat/core-analysis-quality-v2`, draft PR #21. Do not interpret earlier “E2E not yet run” notes as current status.

### Actual qualification evidence
- **CI run 39371018120 PASS for all five jobs:** quality-build-package, database-migrations, migration-runner-upgrade, runtime-e2e and release-kit. https://github.com/alimtalbi-ata/aiops/actions/runs/39371018120
- Cumulative kit artifact `aiops2-core-deployment-kit`, GitHub artifact id `12241690507`, release file `AIOps-2.0.0-core-qualification.1-Core-Deployment-Kit-20261020T044458Z.zip`.
- Verified SHA-256 (actual ZIP) `145b31f3c26bc809df727b2d3b7f3ed2312658337692f6148a6d2abea11800e4`; outer checksum matches. ZIP CRC and all 146 manifest-listed payload files passed `tests/verify-package.py`.
- Cumulative package includes source and infrastructure, 10 SQL migrations, 18 deployment Shell scripts, 28 test files, documentation and integrated reports under `09-Qualification/`.
- Synthetic Temporal E2E run `RUN-A19102CAD44B972F`: run status RESOLVED, one persisted analysis, one persisted critique, one persisted policy decision, **zero actual effect receipts**; report PASS.
- Deterministic synthetic Analyst/Critic evaluation: 5/5 scenario cases successfully assessed; severity accuracy 1.0, grounding 1.0, freshness accuracy 1.0, action safety 1.0, injection fixture resistance 1.0, contradiction detection 1.0. Four strictly advisory proposals checked; evaluation saved in immutable PostgreSQL ledger, `ledger_persistence.status=PASS`.
- Docker Compose environment is configurable by `AIOPS_STACK_ID` and `COMPOSE_PROJECT_NAME`, distinct container/network/volume namespaces; host services default to loopback. Isolated deployment script `deploy/install-isolated.sh` configures `aiops2-rebuild` with separate ports and refuses unsafe clashes. Its `--configure-only` identity/port contract runs in CI without modifying a production host.
- New runbook: [Isolated deployment](DEPLOYMENT-ISOLATED-REBUILD-RUNBOOK.md). Execution roadmap: [Reconstruction plan](RECONSTRUCTION-EXECUTION-PLAN.md).

### Strict limitations, still unresolved
- **Real inference quality NOT RUN:** the CI provider is a deterministic synthetic fixture, not an actual DGX/Mistral/Qwen/other local LLM. No real-model accuracy claim.
- **Production Debian deployment NOT RUN:** CI tests use disposable GitHub runners. No production containers, databases or volumes altered.
- **LIVE actions/remediation NOT QUALIFIED and disabled** pending safe adapters, independent verification, HITL, effect fencing and dedicated qualification.
- The synthetic ACME fixture is not yet a fully calibrated, validated enterprise digital twin.
- The release is a core integration qualification, **not** a production-ready release or the completed full autonomy objective.

### Next engineering batch
1. Add nontrivial provider-fault fixtures and Temporal replay/retry/fencing/adversarial concurrency E2E; CI must report verified PASS/FAIL per case.
2. Qualify Analyst/Critic with a **real model endpoint** against larger holdout sets, track calibrated evidence quality and critic defect catch rate. No model self-certification or direct execution.
3. Implement read-only CMDB/monitoring/RAG adapters with source freshness, provenance, auth, timeouts, and integration tests.
4. Wire HITL approvals, immutable action hashes, fencing, verification and reconciliation for optional guarded action proposals (keep LIVE blocked until certified).
5. Expand ACME digital twin and produce an actual reproducible UI demonstration and video only after Core acceptance.
6. Continue using GitHub PRs/CI release ZIPs as source of truth; minimize chat-to-Debian round trips.

## 2026-10-20 — Core functional deep audit and target-driven redevelopment

**Active development:** branch `feat/core-analysis-quality-v2`, [PR #21](https://github.com/alimtalbi-ata/aiops/pull/21). Current source of truth: [target architecture deep audit](TARGET-ARCHITECTURE-DEEP-AUDIT-2026-10-20.md). An isolated synthetic Core workflow + model-fixture evaluation + cumulative ZIP had passed at commit `a739676bc44974be7ba52cd101ff716d6c497dfe` in [CI #39371406277](https://github.com/alimtalbi-ata/aiops/actions/runs/39371406277). Subsequent hardening modifications MUST pass new CI before receiving their own PASS status.

**Confirmed improvements on the feature branch:** evidence freshness and duplicate/provenance guard; Analyst/Critic deterministic post-model quality checks; blind synthetic inference baseline not keyed to `case_id`; all-case denominators and separate critic/stale/contradiction scoring; synthetic Policy fail-closed; Evidence/Policy service authentication; Temporal workflow import isolation and non-blocking HTTP dispatch; semantic retry-safe event keys; removal of hardcoded secrets and destructive install defaults. Source existence is not qualification; inspect latest CI, exact SHA and artifacts.

**Known unqualified gaps:** real inference accuracy/calibration on DGX, real RAG/CMDB/observability read-only connectors, full conversation Copilot, per-scenario ACME twin isolation, LIVE effect/fencing/HITL recovery, chaos/load tests and Debian production acceptance. Leave LIVE effects disabled. The tiny deterministic CI suite is not a real-model accuracy benchmark.

**Next acceptance sequence:** (1) latest green CI including runtime+model+package gates; (2) frozen external model and prompt version, adversarial/held-out evaluation; (3) real read-only evidence/CMDB/RAG qualification; (4) HITL/fencing and safe remediation simulation; (5) ACME twin/chaos, then demo/recordings.

**Single-entry install:** `bash 00-Deployment/install.sh` delegates to `deploy/install-isolated.sh`; archives carry no shared development passwords. Never use legacy destructive Big Bang as the standard deployment path.

## 2026-10-20 — Core RC1.2 isolated lifecycle, secure diagnostics

- Release candidate: `2.1.0-core-rc1.2` on `feat/core-analysis-quality-v2`, PR #21. Do not merge to `main` or claim production qualification without explicit review.
- Isolation is the supported first installation path (`bash deploy/install-isolated.sh`). The installer and big-bang wrapper now reject `RETIRE_LEGACY=1` *before* any other operation; retirement remains a separate, explicit post-qualification decision.
- `tests/seed-demo.sh` verifies only the PostgreSQL service owned by the selected Compose project and requires populated topology.
- `tests/qualification.sh` verifies Compose project identity and container ownership, not merely container names or healthy-looking unrelated processes.
- `deploy/diagnose.sh` discovers containers by Compose service and project, sanitizes logs via `deploy/redact_logs.py` using known environment secret values and patterns, and writes a SHA-256 verification manifest. Bundles are private, not publication-ready.
- CI additionally executes `tests/test_redact_logs.py` and `tests/lifecycle-safety-contract.sh`. A cumulative RC1.2 ZIP must be obtained from the successful release-kit GitHub Actions artifact and include runtime and model evaluation reports.
- The verified CI for RC1.1 is GitHub Actions #39386565967, commit `4dc3032300452612f49e2ef98d44be29f835f9ca`. Its synthetic Temporal and model-fixture tests are PASS, **but it is not a real-model or server deployment acceptance result**.
- Next: validate RC1.2 CI and packaging checksum, then qualify an actual OpenAI-compatible model offline; expand CMDB/RAG and eventually the ACME Twin, after core exit criteria are met.

## 2026-10-20 — RC1.3 isolation, failure injection and distributable source kit

- **Branch:** `feat/core-analysis-quality-v2`, **PR:** #21; `main` is unchanged. The candidate version is `2.1.0-core-rc1.3`.
- `deploy/plan_isolation.py` validates the expected project name, container/network/volume prefixes, privileges, all published ports and loopback binding **before deployment**. It emits no secrets. The isolated installer invokes it before Compose operations. `tests/test_deployment_isolation.py` and `tests/isolated-deploy-contract.sh` exercise the contracts.
- `deploy/status.py` offers a bounded, read-only operational status/health report with no commands, environment values, tokens or raw logs. `tests/test_stack_status.py` covers Docker output variants, project mixing and secret filtering.
- `tests/test_ai_failure_injection.py` injects falsified evidence IDs, stale observations, client-controlled freshness, contradictory source reports and unauthorized requests; critical claims must fail closed.
- `deploy/package_tree.py` adds a fallback for **rebuilding a cumulative ZIP from an extracted kit without a Git repository**. `tests/test_package_tree.py` checks source completeness and exclusion of secrets, backups, caches, credential files and symlinks.
- `docs/CORE-RC13-QUALIFICATION-OPERATIONS.md` documents Windows-to-Debian transfer, isolated install, read-only status, model evaluation and dual SHA-256 verification.
- **Qualification status:** the previous reconstruction baseline passed full synthetic CI at GitHub Actions #39390130618. The RC1.3 candidate has new tests and awaits a successful full CI execution before its new cumulative ZIP may be called qualified.
- **Next decision:** inspect RC1.3 CI and artifact, qualify a real OpenAI-compatible model offline, then expand read-only context acquisition/RAG and human-approved guarded effects. LIVE remains disabled; no Debian production changes are authorized.

## 2026-10-20 — RC1.4 Docker resource ownership and CI isolation guard

- **Branch:** `feat/core-analysis-quality-v2`; **PR:** #21. `main` remains unmodified by this batch. Version advances from `2.1.0-core-rc1.3` to `2.1.0-core-rc1.4`.
- **Verified previous baseline:** GitHub Actions run #39399054380 passed all five jobs (quality/build, fresh database migration, legacy upgrade, runtime Temporal E2E, release-kit) and published the RC1.3 cumulative ZIP with machine-readable synthetic-qualification reports. This is not a host-specific Debian or real-model acceptance test.
- **New fence:** `deploy/check-docker-ownership.py` checks pre-existing containers, networks and volumes against `com.docker.compose.project`. It is called by `deploy/install-isolated.sh` after rendering the Compose model but before installation. Foreign-owned or unlabeled resources fail closed; no delete/retire/prune is attempted.
- **Regression suite:** `tests/test_docker_ownership.py` checks ownership mismatch, correct owner, absent resources and unreadable inspection data. It is release-blocking in CI.
- **Runbook:** `docs/CORE-RC14-RESOURCE-OWNERSHIP.md` specifies the fence, non-destructive installation and limitations.
- **Pending gate:** RC1.4 full CI and cumulative artifact qualification. Do not describe RC1.4 as qualified until the `release-kit` job succeeds on the exact commit; keep RC1.3 as the last verified release candidate until then.
- **Next priority:** run the isolated reconstruction from a fresh directory on the Debian host only after a qualified kit is available; check real inference service connectivity, Analyst/Critic grounding/abstention and policies, then advance read-only CMDB/RAG acquisition. Keep simulated evidence distinct from real evidence; do not enable LIVE remediation without independent end-to-end qualification.


## 2026-10-24 — NOC/Checkmk/Thruk and multi-vendor RAG archaeology

Historical Oct 16/19 container inventories recovered from Library establish that **Checkmk Community 2.5** and **Thruk** were already present in `/home/aiops/aiops-v1/stack/noc` (Compose project `aiops_noc`), with historic ports Checkmk 8119 and Thruk 8120. Do not redeploy duplicate NOC services; first verify whether the historical configuration and data volumes still exist. Historic HTTP reachability is not proof of functional data correctness.

The reference recovery document is `docs/architecture/AIOPS-NOC-STACK-HISTORICAL-RECOVERY-20261024.md`. Reconstruct the NOC with host/service state, acknowledgements, downtime, impact topology, multi-client scope, and a Demo Director synchronizing Checkmk/Thruk with Grafana, n8n and GLPI. The RAG plan `docs/architecture/AIOPS-RAG-OPS-CORPUS-AND-TRACE-CONTRACT-20261024.md` defines operations runbooks, SNMP/MIB/traps, vendor logs/traces, document provenance and evaluation. Synthetic diagnostic examples live in `demo/rag_ops_fixture_catalog.json` (not authoritative vendor specifications).

Prioritize recovery of original Compose, Thruk config, Checkmk state, RAG index, existing runbooks/observability dashboards from /home/aiops **read-only**, then reuse before rewriting. Continue isolated PR tests; never change Debian services or expose secret material without explicit authorization.


## Development status and blocker register — 2026-10-27

The current branch now has a consolidated status register: [AIOps development status, remaining work and blockers](release/AIOPS-DEVELOPMENT-STATUS-AND-BLOCKERS-20261027.md). It distinguishes source presence, synthetic/isolated tests, commit-specific CI evidence and live runtime qualification. Read it before choosing the next work package.

Key current blockers recorded: current PR-head CI status is unconfirmed by the available connector; the portal source does not mount the separate NOC integration route; GLPI/CMDB, n8n, Grafana/Prometheus/Alertmanager, Checkmk/Thruk, Temporal API, real DGX Analyst/Critic and RAG are not proven as live portal integrations; the ACME SAN P1 → Payments P2 scenario lacks an authentic E2E evidence set; global portal SSO/authentication is not qualified; deployed Git/image/config provenance and Debian runtime remain unverified. The four staggered CI workflows are in PR #36 and are not on a default branch, so their scheduled cadence is not active yet. No production changes, live remediation or automatic merge are authorized.

Status discipline: never mark a test PASS without a run tied to the exact commit; update this continuity record and the blocker register together after material work. Preserve synthetic/live provenance and report unknowns explicitly.
