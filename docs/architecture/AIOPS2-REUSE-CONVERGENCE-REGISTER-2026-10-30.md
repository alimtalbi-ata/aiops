# AIOps 2.0 — Reuse and convergence register

**Baseline:** GitHub inventory on 2026-10-30.  
**Purpose:** direct existing work to one target architecture; prevent parallel implementations and unreviewed promotions.  
**Evidence labels:** SOURCE_REVIEWED, CI_REPORTED, RUNTIME_REPORTED, NOT_VERIFIED. PR body claims are recorded as claims until independently rechecked against the exact current head.

## 1. Open work inventory

| Item | Observed state | Direction |
|---|---|---|
| #185 ACME integrated candidate | Open draft; 72 files, +10,233/-72. PR body reports prior 6/6 quality jobs, other qualification workflows, 8/8 source blob checks and deployment-kit checks. It explicitly says DEMO_LOCAL=GO and RELEASE_STABLE=NO_GO. | Use as the primary scenario/convergence candidate; inspect exact head and current CI before selective promotion. Do not merge the large diff as a unit without ownership/transport review. |
| #190 INGEST and Demo Studio artefacts | Open, non-draft. Body reports a previous syntax error and follow-up mock corrections; latest stated head requires full CI. | Re-run exact-head CI; prioritize if still failing the visible run/artefact consistency bug. |
| #192 Portal HITL inbox + GLPI read-only Copilot | Open draft; +448/-3, 7 files. Read-only proposal inbox and GLPI ticket context. | Reuse read-only surfaces and ticket adapter; align to verified identity and Core contract before exposing decisions. |
| #193 guarded GLPI→Copilot→HITL fastpath | Open draft; +243, 2 files. Creates PROPOSED record only for constrained synthetic LOW-risk action. | Reuse only after #192/#194 contracts align; proposal creation is not approval or execution. |
| #194 Temporal HITL / OIDC / outbox | Open draft; +1,572/-10, 17 files. Previous exact head `1fade3e` had all observed CI jobs green. | Reuse Core OIDC verifier, transactional decision outbox and LIVE-only Temporal barrier. Portal OIDC session integration and full runtime failure-injection remain gaps. |
| #188 scheduled qualification + Debian runtime smoke | Open non-draft. Daily full quality schedule plus 15-minute read-only smoke on repository-scoped self-hosted runner. | Preferred schedule candidate after review. It is inactive until merged to default branch and runner installed/online. |
| #189 scheduled quality checks | Open non-draft. Adds a two-hour quality cron and manual dispatch. | Duplicate with #188. Do not activate both; consolidate schedule definition and close/supersede only after owner review. |
| #187 Loki/Tempo/OTel | Open draft, 7 files, +322; explicitly untested on Debian. | Defer new stack until resource/retention/security/rollback review. Use existing Prometheus/Grafana and add instrumentation first. |
| #146 / #153 Debian auto-deploy / stable poller | Open drafts; 15-minute portal auto-deploy and 5-minute stable poller proposals. Not tested on Debian. | No automatic deployment in the 48h window. Require exact transport map, protected release branch, backup, rollback, health and applied SHA proof. |
| #177 Portal P0 UI | Open draft. Its body records historical Policy and Runtime E2E failures plus a deployer transport gap. | Do not promote whole branch. Selectively reuse tested routes/UI only after current CI and package-transport coverage. |
| #59 architecture + 12-week roadmap | Open draft; architecture/HLD and schedule are explicitly proposed and not runtime proof. | Keep as long-term program backlog; this 48h plan is a vertical slice and does not replace it. |

## 2. Existing components to reuse

| Capability | Source candidates | Reuse mode | Required validation |
|---|---|---|---|
| Canonical Run/Incident and stage ledger | Core API + PostgreSQL migrations | Reuse as single authority | schema chain, tenant scope, optimistic version, idempotency |
| Durable orchestration | Temporal/Worker | Reuse | retry, replay, restart, timeout, outbox signal delivery |
| ACME SAN→Payments scenario | Twin, simulator, Golden Payment fixture, PR #185 and existing locator | Adapt behind canonical source-backed relationship contract | exact CI edges, impact direction, source freshness, deterministic replay |
| Portal operator journey | Demo Studio V2, NOC/Timeline, PR #177/#190 | Selective reuse | routes, auth, no stale/foreign Run fallback, packaged source completeness |
| AI evidence ledger | Analysis/Critic/Policy records | Reuse | immutable evidence-set hash, provider/model/prompt versions, validated output |
| AI evaluation | `tools/evaluate_ai_core.py`, `eval/ai-core-cases.json`, `tests/test_ai_eval_harness.py` on HITL candidate branch | Port selectively | exact dependency and API compatibility; add usage/latency telemetry |
| Evidence | Evidence API + read-only refs + bundle auditor | Reuse | hash, provenance, freshness, source identity, tenant/run binding |
| Twin | ACME topology and impact read models | Reuse/adapt | source-backed graph, no fabricated edges, unknown stale state |
| GLPI | read-only adapter, ticket/run context, ITSM correlation branches | Adapt | authenticated read, canonical IDs, idempotency, reconciliation |
| Policy/HITL | Policy SIMULATE, proposal ledger, sandbox receipts, OIDC/outbox branch | Reuse and harden | role separation, immutable hash/scope, lease recovery, Policy recheck |
| Observability | Prometheus/Grafana already in Compose | Reuse | instrument Core/Worker/AI stage metrics; no duplicate collection |
| Debian release | existing install/upgrade/package/rollback scripts | Reuse | clean install, source transport, ownership fence, checksum, rollback |

## 3. Anti-duplication rules

- No second Run store, orchestration engine, AI ledger, Evidence repository, GLPI client, Portal shell or monitoring stack without ADR and measured need.
- PRs touching the same module are sequenced, not stacked blindly. In particular, reconcile Core `main.py`, Portal `main.py`, Worker `main.py`, migrations and Compose before merge.
- A PR is not a source of truth until its exact head SHA, diff, tests and current CI are reviewed.
- A prior green SHA does not qualify a newer head.
- Source/CI qualification does not prove Debian deployment. Runtime claims require timestamped, read-only evidence from the actual host.
- Historical V1/V145 directories are candidates, not deployable components. Inspect code, contracts, dependencies, tests and runtime ownership before reuse.

## 4. Integration order

1. Freeze scenario IDs and canonical contract versions.
2. Selectively converge #185 scenario and read models.
3. Resolve #190 stage/artefact correctness.
4. Align #192/#193 Portal/GLPI read context with #194 Core HITL/OIDC/outbox contract.
5. Add AI usage/latency telemetry to the existing evaluation harness.
6. Converge schedule #188 vs #189; leave Debian auto-deploy #146/#153 disabled.
7. Produce one cumulative package only after exact-head CI, artifact checksum and install/rollback gates.


## 5. Exact-head revalidation update — 2026-10-30 12:10 UTC

### PR #185 — strong scenario artifact, unsafe direct merge base

- Current PR head is `02dd3aa45a4adc0d3f7613f04288a71f77d9061e`; PR body still names the earlier `14b4e8b...` head and must be refreshed by its release owner.
- Current PR base is `feat/cron-stable-reconciled-20261028` at `e5c6b030c374e47f64678f425df78cd147335eec`, **not `main`**.
- Comparing that base branch with `main` reports `diverged`, 672 commits ahead and 43 behind. This is a material dependency and makes direct merge/promotion into `main` unsafe without a selective rebase/convergence plan.
- Exact current candidate CI run `41046204073`: 6/6 jobs SUCCESS; companion V2.8, Historical Trace and Offline Integrity runs also SUCCESS. The run has a `aiops2-core-deployment-kit` artifact (ID `12973100494`) plus runtime and DR reports.
- **Disposition:** keep #185 as the scenario/story and package evidence source; do not merge its 72-file branch into main as-is. Port the verified small commits into a clean main-based integration branch after mapping their dependencies. The candidate remains DEMO-local evidence, not Debian applied-sha or production release proof.

### PR #195 / #196 — architecture and benchmark slices

- #195 architecture/ITIL/48h documentation branch passed its exact quality workflow `41052336091` (3/3 jobs success: Policy/static, Core/PostgreSQL NOC integration, Grafana real integration).
- #196 is stacked on #194 and implements per-invocation provider usage/latency telemetry and request/output caps. First run exposed two outdated HTTP test doubles without `status_code`; fixtures were corrected in commit `388b7c48a108f70315b9fae92de72d10ac399704`. Corrected quality tests for Intelligence contracts and AI evaluation passed; full Runtime E2E/release-kit remained in progress at this update.


## 6. 5/5 integration and exact-head CI delta — 2026-10-30 12:15 UTC

| PR | Exact observed head | Qualification / disposition |
|---|---|---|
| #185 | `5782d6fcece32cfd38ada0d50bfe68a8b74bd164` | Eight selective source blobs integrated; V2.8 [41053319372](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319372) **FAILED** (59 tests, one stale `gates.decision` mock). Quality [41053319020](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319020) in progress at snapshot; Historical/Offline SUCCESS. Not release-qualified. |
| #187 | `0d7b2310f7c04fff5090dd11a6748ef3f4ca6b49` | Quality SUCCESS; runtime resource/retention/security review missing; DEFER. |
| #188 | `7512fdd17f9e9cf1ab3a1d4acb7dc77c81ee532f` | Quality SUCCESS, unmerged. Daily `23 2 * * *` and 15-minute runtime smoke design; runner NOT_ATTESTED. Preferred over #189. |
| #189 | `233f4ed4158257f1df724e4280e00804b7ae53fb` | Quality SUCCESS, unmerged. Actual workflow cron `23 */2 * * *`, PR description's six-hour claim is stale. Duplicate, DO NOT ACTIVATE. |
| #190 | `2aa1e89dd5f8c0dd769d9ca4ca13fbe6df19f853` | Four exact-head workflows SUCCESS; correctness fix already selectively represented in #185. No automatic merge. |
| #192 | `8488e64c718ba887cb9b1e4a3b0161c8a435232f` | Four exact-head workflows SUCCESS; staged Core/Portal/GLPI contracts need reconciliation. |
| #193 | `e8f05d8c50045f4256e89ad0776424f4dad5bb61` | Quality [41024125286](https://github.com/alimtalbi-ata/aiops/actions/runs/41024125286) first failed on pip `IncompleteRead`, then targeted rerun 6/6 SUCCESS; stacked on #192, not an independent release. |
| #194 | `1fade3e5b3f07bdbd6b4fa8222bbb585012894ca` | Four exact-head workflows SUCCESS; HITL/OIDC/outbox not runtime qualified. |
| #195 | `48c83c17af51f193b4ed0bf0471622e019b196b7` | Architecture docs; latest CI queued at snapshot, no runtime implication. |
| #196 | `388b7c48a108f70315b9fae92de72d10ac399704` | Four exact-head workflows SUCCESS; reuses evaluator/provider telemetry, not yet integrated in scenario candidate. |

**Overlap map:** `.github/workflows/quality.yml` (#185/#188/#189/#194); `app/core/main.py` (#185/#190/#192/#194); `app/portal/main.py` (#185/#190/#192/#194); `compose.yml` (#185/#192/#194); `app/portal/glpi_run_context.py` (#192/#193). Keep #185 the only scenario release candidate, #195 the documentation review PR and #196 a stacked telemetry workstream; do not mass merge.

**Deployer audit:** `deploy/aiops2-stable` is identical to `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (0/0). The stable `deploy/deploy-demo-studio-v2.sh` copies `demo_v2.py` and its test and locally patches `main.py`. The candidate `deploy/poll-approved-deploy.sh` accepts only the stable branch and refuses nontransported paths; it is not the four-image release mechanism. Actual cron installation, `applied.sha`, GLPI read, Compose ownership, smoke and rollback remain NOT_ATTESTED. **RELEASE_STABLE=NO_GO.**


## 6. Five-schedule handoff — 2026-10-30 12:20 UTC

The four focused schedules delivered additional commits after the initial candidate convergence:

| Lot | Current branch / head | Local targeted tests reported by schedule | Main ancestry comparison | Disposition |
|---|---|---:|---:|---|
| 1/5 ACME Core/Twin | `feat/p0-acme-core-run-locator-20261029` / `f50d3dac3182fd5d7c2bc5cb9ba8cf1bbba486ca` | 70/70 PASS | diverged 711 ahead / 43 behind | Source/evidence identity hardening; selective port only |
| 2/5 Portal | `feat/p0-portal-nested-run-scope-20261030-1150` / `ca6feab123d552c32ea707620a9176757b88b822` | 62/62 PASS | diverged 740 / 43 | Nested event/run scope rejection; selective port only |
| 3/5 NOC/Evidence/GLPI | `feat/p0-noc-evidence-provenance-readonly-20261030` / `18ff72e312d5af5c2df239b646de18c16c4c534c` | 2 commits reported; UTC timestamp fail-closed correction | diverged 736 / 43 | Evidence/GLPI provenance hardening; re-run targeted tests and selective port |
| 4/5 Policy/HITL | `feat/p0-policy-simulate-failclosed-20261030` / `901c5bb86922504ef447609e5a286c783cf8060b` | 48/48 targeted + 195/195 convergence suite | diverged 739 / 43 | SIMULATE timestamp/actor validation; selective port only |

These are schedule-reported targeted tests, not GitHub Actions qualification. No Actions run was found for the exact four commits at this update. The compare operation reports up to 300 changed paths due the divergent ancestry; do not copy complete branch trees or workflow files. Request commit-level/file-level diffs and port only the intended lot's minimal source + tests into a fresh main-based integration branch, then run full CI.

The immediate 5/5 automation run was still in progress. Schedule 5/5 was updated to enforce base-branch checks, prohibit direct merge of divergent branches and coordinate a clean main-based selective integration.


## 7. CI/package completion addendum — 2026-10-30 12:20 UTC

- #185 `5782d6f` Quality **6/6 SUCCESS**, Offline/Historical SUCCESS, but V2.8 **FAILED** (legacy gates fixture, one error in 59). Exact deployment-kit artifact `12975971501`: sidecar SHA256, 445 CRC, 395 file checksums and eight source blobs all verified; **253/253** selected tests PASS on extracted archive; **14/14** isolated read-only Portal GET 200, POST 405, missing run 404. Source/packaging qualification does **not** override V2.8 or runtime gates.
- `main` versus #185 base `feat/cron-stable-reconciled-20261028`: **diverged**, 672 ahead / 43 behind. #185 is not safe for direct merge into main.
- #196 is the existing telemetry implementation; no separate provider usage engine will be created by 5/5. Model invocations, cost and budget enforcement are still NOT_TESTED.


## 7. PR #185 latest candidate and package divergence — 2026-10-30 12:25 UTC

- Current head `5782d6fcece32cfd38ada0d50bfe68a8b74bd164`; base remains `feat/cron-stable-reconciled-20261028`, 672 ahead / 43 behind main.
- Quality `41053319020`: 6/6 SUCCESS; Offline `41053318999`: SUCCESS; Historical `41053319033`: SUCCESS; V2.8 `41053319372`: FAILED (58 pass / 1 error).
- Failure is `test_demo_live_trace_is_source_backed` expecting `response["gates"]["decision"]`; new portal contract uses `gates.items`. Fix the test fixture, not the fail-closed code.
- Package artifact `12975971501` inner SHA `af627c8af804eec25e643e7b3a7169bb6e513ee6cae8687c18bc4c47c2c0aa5d`: 445 entries, 395/395 checksums valid, but no migration 011, no OIDC verifier, no AI per-call telemetry.
- The separate #196 package `12974884559` contains migration 011, OIDC and telemetry but lacks the new architecture docs and the latest ACME fixes. Both packages are valid individually but not cumulative. Build one final kit only from a clean integrated source SHA and verify actual contents, not artifact label.
