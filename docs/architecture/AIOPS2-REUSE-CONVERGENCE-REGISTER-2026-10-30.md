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


## 2026-10-30 12:30 UTC — 5/5 scoped-gates regression repair — exact-head overlaps and integration order

| Slice | Exact head | Verified CI and disposition |
|---|---|---|
| #185 scenario spine | `2b2af9cd21e48be741a3906b7a12cfffa3371f7b` | V2.8 41055650146 SUCCESS; Offline/Historical SUCCESS; Quality 41055650123 pending at snapshot; 741 ahead / 43 behind main — **do not merge** |
| #197 Evidence UTC preflight | `d9d09813b822a1e4bfd33f139eafc882be85bd49` | Quality 41054823119 SUCCESS; main-based, isolated adapter only |
| #198 Core Run locator | `8f48b1b5a94960ce4ddcc1ca35bf206302543e94` | Quality 41054868177 SUCCESS; main-based; bearer Evidence refs endpoint absent |
| #199 Policy SIMULATE fixture | `e0fc68f7b2f947c75d4eed035d682a45c88a78a0` | Quality 41055154260 SUCCESS; main-based, no LIVE authority |
| #195 architecture docs | `f1bd3ee90b01ea627a3adba4d74f153fc88d93d1` (before this update) | Quality 41054940809 SUCCESS; main-based |
| #196 AI telemetry | `6b6a3b3991e8a4b5b83ff4c6534dfa4b34f72932` | Quality 41055287795, V2.8 41055287705, Offline 41055287588, Historical 41055287726 all SUCCESS; stacked on #194, not main-based |

**Diff conflict hotspots (changed-path intersections, not proof of semantic compatibility):** #185/#190 five files (`app/core/main.py`, `app/portal/main.py`, `app/shared/domain.py`, `tests/test_demo_v2.py`, `tests/test_initial_stage_state.py`); #185/#194 four (`quality.yml`, Core/Portal main, `compose.yml`); #192/#193 two (`app/portal/glpi_run_context.py`, its test); #194/#196 three (Intelligence main, Compose, intelligence contract test); #188/#189 one (`quality.yml`). Keep one integration owner for Core/Portal/Compose and a single schedule. #188 preferred; #189 duplicate inactive. #187 deferred; #146/#153 disabled.

**Next candidate gate:** build from a **single clean main-based SHA** after selective conflict resolution, including ACME + migration 011/OIDC/HITL + AI per-call telemetry + architecture/ITIL/benchmark docs + configs/migrations/tests/rollback. Audit inner ZIP members, SHA256 and exact source blobs; test install/upgrade/rollback in isolation. Neither existing RC1.4 artifact is cumulative. `applied.sha` and Debian runtime remain NOT_ATTESTED; stable NO-GO.

### 2026-10-30 13:12 UTC — refreshed PR source/overlap matrix

#185 `2b2af9c` draft: 741 ahead/43 behind main; #196 `6b6a3b3` stacked on #194: 837 ahead/43 behind. #195 docs `6a6b80d` main-based and Quality 41056179605 SUCCESS. Main-based #197 `bd86faa` (UTC Evidence preflight), #198 `8f48b1b` (Run locator), #199 `e0fc68f` (SIMULATE fixture plus Quality YAML) each have exact-head Quality SUCCESS, but no combined CI and no main-based Demo Studio route for 2/5.

Exact-head Quality SUCCESS separately: #190 `2aa1e89` (41019332417), #192 `8488e64` (41022029419), #193 `e8f05d8` (41024125286), #194 `1fade3e` (41050718293), #196 `6b6a3b3` (41055287795). Overlaps from changed filenames: #185/#190/#192/#194 on Core/Portal `main.py`; #185/#192/#194/#196 on `compose.yml`; #192/#193 on `glpi_run_context.py`; #188/#189/#194/#199 on `.github/workflows/quality.yml`. Resolve contracts manually, no blind cherry-pick. #188 preferred over duplicate #189, both unmerged; #146/#153 auto-deploy prohibited, #187 deferred.

## 2026-10-30 14:00 UTC — first main-based integration stage

| Workstream | Exact source | Stage in #201 `2ceda14c` | Still blocked |
|---|---|---|---|
| 1/5 ACME | #198 `8f48b1b5` | 2 exact Git blobs (locator + tests) | protected Core Evidence-refs endpoint and tenant/runtime proof absent on main |
| 2/5 Portal | no main-based routable run-detail handoff | **NOT_INCLUDED** | source-backed `run_id` deep link + scoped nested collection guards |
| 3/5 NOC/Evidence | #197 `57194371` | 2 exact blobs (UTC preflight + tests) | no authenticated Core/GLPI join, source/freshness proof |
| 4/5 Policy | #199 `e0fc68f7` | 2 exact blobs (SIMULATE fixture + tests) | no verified HITL approval/outbox/executor |
| 5/5 Architecture | #195 `f9617b09` | 14 README/docs exact blobs, one new release note | benchmark/model and cumulative kit unqualified |

Quality workflow from #199 extended with 1/5 and 3/5 offline test steps. [Combined CI 41068355452](https://github.com/alimtalbi-ata/aiops/actions/runs/41068355452) was **IN_PROGRESS**, not yet a green gate. #185 (741 ahead/43 behind main) remains scenario source only; #194/#196 (divergent) need dependency-aware selective port. #188 preferred cron, #189 duplicate, #146/#153 disabled, #187 deferred.


## 8. Architecture-led reorientation — 2026-10-30 14:46 Europe/Paris

### Exact-head convergence status

| PR / lane | Base → head | Latest verified result | Architectural disposition |
|---|---|---|---|
| #195 architecture | `main` → previous `f9617b09` | Quality 41061315909 SUCCESS (3/3); current documentation commits have triggered a new exact-head run | Canonical architecture/ITIL/48h baseline; keep as the single architecture ADR/documentation PR |
| #196 AI telemetry + real-model benchmark | `feat/temporal-hitl-v1` → current benchmark branch (newer than `6b6a3b39`) | Previous head `6b6a3b39`: Quality 41055287795, Offline 41055287588, Historical 41055287726, V2.8 41055287705 all SUCCESS; new Ollama benchmark files/tests/workflow are awaiting fresh CI | Reuse existing Intelligence, evaluator, telemetry and dataset; new Qwen3 4B/8B CPU experiment is not yet executed |
| #197 NOC/Evidence preflight | `main` → `571943714` | Quality 41066639506 SUCCESS | UTC fail-closed preflight only; not a GLPI connector, Evidence attestation or tenant ACL |
| #198 ACME Run locator | `main` → `8f48b1b5` | Quality 41054868177 SUCCESS | Read-only synthetic source locator; missing authenticated Core Evidence-refs endpoint keeps Evidence attestation UNKNOWN |
| #199 Policy SIMULATE fixture | `main` → `e0fc68f7` | Quality 41055154260 SUCCESS | UTC/actor validation for SIMULATE only; no approval or execution authority |
| #194 HITL/OIDC/outbox | `feat/glpi-hitl-proposal-fastpath` → `1fade3e5` | Quality 41050718293, Offline 41050718284, Historical 41050718256, V2.8 41050718393 SUCCESS | Valuable source for selective port; stacked base and overlapping Core/Portal/Compose prevent blind merge |
| #185 ACME integrated candidate | `feat/cron-stable-reconciled-20261028` → `2b2af9cd` | Quality 41055650123, V2.8 41055650146, Offline 41055650247, Historical 41055650640 SUCCESS | Scenario/story and test source only; branch is about 741 ahead/43 behind main and its ZIP is not cumulative |
| #44 Ollama adapter | old main `92108b3b` → `2d3157e0` | Quality 40571362224 SUCCESS; branch comparison diverged 8 ahead/42 behind main | Reuse the Ollama/Qwen3 4B/8B experiment pattern, not the old branch wholesale. PR #196 now calls the actual existing Analyst/Critic evaluator through Ollama instead of a standalone READY smoke. |

### Current deterministic AI evidence

Exact runtime report artifact #12976497171 from #196 Quality run 41055287795:
- Dataset SHA `fdf45a4f89b6867bd172116648f53194d460c832cb2d133f2dc4fdbf30d1493a`; 5 synthetic cases / 10 model calls.
- Severity, grounding, freshness, safety, injection, contradiction, stale detection and Critic disposition each 1.00 on defined denominators.
- Proposal actionability and target/action/evidence/precondition/postcondition/rollback scores each 1.00 over four proposal cases.
- Provider usage coverage 10/10; 20 fixed placeholder tokens; latency P50 3.01 ms / P95 4.54 ms; zero retries.
- Cost UNKNOWN; fixed deterministic usage and latency are not real-model economics.
- Temporal run `RUN-6A6924688ABCD0B4`: DEMO RESOLVED, 12 Evidence, Policy PASS/SIMULATE, HITL_SIMULATION_SKIPPED, zero effect receipts.

### New benchmark work

PR #196 adds:
- `tools/summarize_ai_benchmark.py` and tests that require matching dataset/prompt identity, reject LIVE/effect-enabled reports, and preserve null usage/cost.
- `.github/compose.ollama-benchmark.yml` for isolated local Ollama access to the existing Intelligence service.
- `.github/workflows/ollama-ai-benchmark.yml` plus a quality-workflow call restricted to PR #196, with Qwen3 4B and 8B and three repeats by default.
- The workflow is an experiment runner, not a model-promotion gate: it preserves model evaluation PASS/FAIL in artifacts while requiring a valid report. It has not yet produced real-model results at this update.

### Schedule redirection

All five existing ChatGPT schedules have been reoriented to the architecture/48h plan and immediate runs have been requested. 2/5 Portal was re-enabled after being paused. Exclusive ownership is ACME/Twin, Portal, NOC/Evidence/GLPI, Policy/HITL, and architecture/benchmark/release. No sixth schedule was created.

### Release and host constraints

- #188 remains the single preferred scheduled full-quality + read-only runtime-smoke proposal; #189 remains duplicate. Neither is enabled on main.
- #146/#153 Debian auto-deploy remain disabled; #187 observability expansion remains deferred in favor of existing Prometheus/Grafana.
- No Debian cron, runner, Docker service, `applied.sha`, stable branch, live DB, GLPI record, SSH or sudo operation was performed. Host access is not available through this GitHub session.
- No direct main/stable push, merge, LIVE approval or production claim. Cumulative kit and Debian runtime remain NO-GO until a single main-based source SHA and clean install/upgrade/rollback evidence exist.

## 2026-10-30 14:16 UTC — 5/5 cumulative-kit guard, exact main-based staging

Draft [#201](https://github.com/alimtalbi-ata/aiops/pull/201) now contains an **integrator-owned** fail-closed ZIP/source inventory gate: `tools/check_cumulative_release_kit.py`, `tests/test_cumulative_release_kit_gate.py`, and a dedicated Quality step; HEAD `03a5b0cce44e56d7ae315ee7df16e850a5e35b11`. Two new files matched their local Git blob hashes (2/2); offline tests **10/10 PASS**, Python compile PASS. Exact-head Actions **PENDING/NOT_OBSERVED** at this recording, not green by inheritance from previous #201 SHA `0bd8b4c` (Quality 41069069510 SUCCESS 3/3).

The gate checks ZIP CRC, all file SHA256 entries, duplicate/unsafe/symlink paths, mandatory Core/Portal/HITL/AI/ITIL/docs members, a manifest `git_commit` matching an exact expected SHA, and source-tree HEAD + mandatory-file byte identity. It is **not** a kit builder or an install/rollback rehearsal. On the previously supplied #185 inner ZIP (395/395 hashes), the gate reports missing migration 011, OIDC, telemetry, new Portal/Policy/Evidence components and architecture docs; the old CI merge manifest SHA does not match #185 PR HEAD. The supplied local directory was not a Git checkout, so source-tree attestation was unavailable. **CUMULATIVE_KIT=NO_GO**. #194/#196 remain stacked and unported; no parallel engine or owner module edited.

## 2026-10-30 14:23 UTC — latest head and convergence boundary

- One main-based integration staging [#201](https://github.com/alimtalbi-ata/aiops/pull/201) HEAD `84f6cf1c3656c8c9b74acaf6036cc0c443827aad`, [Quality 41071155614](https://github.com/alimtalbi-ata/aiops/actions/runs/41071155614) SUCCESS 3/3; 12/12 release-kit inventory negative tests PASS. New checks reject dirty tracked checkout and non-root source path. No cumulative ZIP or rollback attestation.
- #194 HEAD `40d38705cf2bde3be6052340442c117a81908f65`, Quality #41070849469 6/6 jobs SUCCESS, V2.8/Offline/Historical SUCCESS. #196 HEAD `48b353b1f674f4e952d34d92d072fe4202f1989e`, V2.8/Offline/Historical SUCCESS, Quality #41070920303 had unfinished Ollama CPU/runtime jobs at inspection. Its PR base remains older #194 SHA `1fade3e5`; both are stacked and excluded from #201. No real-model benchmark conclusion is inferred.
- #188 preferred daily full quality and optional approved runner read-only smoke; #189 OPEN redundant, never activate both. #146/#153 disabled, #187 deferred, #185 historical divergent source only.

## 2026-10-30 14:28 UTC — selective Portal convergence and corrected HITL status

- [#201](https://github.com/alimtalbi-ata/aiops/pull/201) now has a **single main-based integration head** `178bbf71f5884c5a8b54f38ca815c6f76ea0ffb9` (parent `84f6cf1c`). The integrator transported only four Git blobs from [#202](https://github.com/alimtalbi-ata/aiops/pull/202) exact head `cd17c44d47ecdf5ced2306edf169befcb2eff8ac`: `app/portal/acme_run_detail.py`, `app/portal/portal_run_link_client.js`, and their two targeted tests. All four previous #201 blobs were identical to #202 ancestor `6c72000e` (**4/4**); no Portal main.py, Compose, config, or Quality workflow was overwritten. Exact combined-head Quality is **IN_PROGRESS**, not yet PASS.
- #202 exact-head [Quality 41071596535](https://github.com/alimtalbi-ata/aiops/actions/runs/41071596535) **3/3 SUCCESS**; policy/static job log confirms `python -m unittest discover -s tests -p 'test_portal_run_detail.py' -v` **21/21 PASS** and `node --test tests/test_portal_run_link_client.cjs` **6/6 PASS**. The read-only cookie is Run-ID scoped and invalidated on viewer-token rotation; GLPI relation and source freshness remain explicitly UNKNOWN. This is not OIDC/tenant-ACL qualification.
- Corrected stale risk: #194 exact head `40d38705cf2bde3be6052340442c117a81908f65` already checks `lease_until > now()` under row lock for outbox ACK. The old missing-lease-guard assertion is **obsolete**. [#204](https://github.com/alimtalbi-ata/aiops/pull/204) supplies failure-injection tests on a stacked base; its latest Quality is still **IN_PROGRESS** and is not a runtime proof.
- #192/#193 GLPI text-derived Run-ID is **not** authoritative; [issue #203](https://github.com/alimtalbi-ata/aiops/issues/203) tracks a Core-verified tenant-scoped ticket/Run link. #196 benchmark head `48b353b1` Quality still has two Ollama CPU jobs IN_PROGRESS; no real-model results claimed. #188 preferred; #189 redundant, both unmerged. No host or LIVE action.

## 2026-10-30 15:10 UTC — exact-head ACME fixture port and benchmark status correction

- Single main-based [#201](https://github.com/alimtalbi-ata/aiops/pull/201): selectively ported only `tests/test_acme_san_payments_fixture_contract.py` from [#198](https://github.com/alimtalbi-ata/aiops/pull/198) blob `675a0af6cd240549d1af92fbcf7a06ec2d2bd638` in commit `5043622ac976da67f83292acb50716a4010d4bb6`; pinned seed `db/migrations/005_seed_acme.sql` matched blob `67f0124a2c3b450e5249165e719a5d943fdd7237`. CI step added in `7474c74c9e6a79c5d28d6624f7b9be2100a792ac` to actually run six offline tests. #198 source reported 6/6 PASS; #201 exact-head CI must be observed separately. Reverse traversal is **synthetic fixture only**, not live Payments impact, tenant scope or authenticated Core/Evidence proof.
- [#196](https://github.com/alimtalbi-ata/aiops/pull/196) exact HEAD `48b353b1f674f4e952d34d92d072fe4202f1989e`, [Quality 41070920303](https://github.com/alimtalbi-ata/aiops/actions/runs/41070920303) completed SUCCESS **8/8 jobs**, **but both Ollama benchmark jobs recorded evaluator_exit=1 on all three repeats each**. qwen3:4b and qwen3:8b each produced `MODEL=unavailable|PASS=0/3|P50=None|P95=None|TOKENS=None|COST=None`; Intelligence logs show `ReadTimeout`. Workflow currently captures evaluator exit without failing the job. Thus workflow green **must not** be interpreted as real-model benchmark success. Require a fail-closed exit-code gate after artifact upload, a bounded timeout/resource diagnostic, then re-run isolated benchmark. No cost/tenant budget claim.


## 2026-10-30 16:11 Europe/Paris — architect's exact-head re-audit and work redirection

This section supersedes earlier status notes where the same PR has since advanced. The live 48-hour task board is `docs/planning/AIOPS2-48H-EXECUTION-CONTROL-BOARD-2026-10-30.md`.

### Exact source/CI observations

| PR | Exact head / base | Observed Actions | Current architectural disposition |
|---|---|---|---|
| #195 | `65842ed2` / main | Quality `41078216626` SUCCESS | Architecture/ITIL/benchmark/reuse baseline; addenda are docs-only and must keep current release caveats |
| #201 | `7474c74c` / main | Quality `41077972849` SUCCESS | Primary clean-main selective integration candidate; T0 only, not a full T1/T2 release |
| #185 | `2b2af9cd` / `feat/cron-stable-reconciled-20261028` | Quality `41055650123`, V2.8 `41055650146`, Offline `41055650247`, Historical `41055650640` all SUCCESS | Scenario/story and exact-blob source only; 741 ahead / 43 behind main; never merge wholesale |
| #194 | `40d38705` / `feat/glpi-hitl-proposal-fastpath` | Quality `41070849469`, V2.8 `41070849246`, Offline `41070849257`, Historical `41070849437` all SUCCESS | Stacked HITL/OIDC/outbox implementation; selective contract reuse only |
| #204 | `dabfeb6f` / #194 `40d38705` | Quality `41074914860`, V2.8 `41074914892`, Offline `41074914893`, Historical `41074914877` all SUCCESS | Stacked Temporal positive-revision fence and offline failure-injection tests; runtime Temporal restart/lost-ACK qualification remains separate |
| #196 | `48b353b1` / #194 `1fade3e5` | Quality `41070920303` SUCCESS (8/8 jobs) | Telemetry/evaluator source is reusable; **real-model experiment failed all six repeats** (qwen3:4b and qwen3:8b, ReadTimeout, zero scored calls, no usage/latency/cost). Green workflow previously masked evaluator exits |
| #202 | `922aed2b` / main | Quality `41074573704` SUCCESS | Portal read-only Run detail and nested Run-scope tests; session capability is not OIDC or tenant ACL |
| #205 | `7f2d2bea` / main | Quality `41075269257` SUCCESS | Core ITSM↔Run xref is a pure mock-only contract; no socket, Core GET, GLPI connector or Portal wiring |
| #188 | `7512fdd1` / main | Quality `40974112404` SUCCESS | Preferred daily full-quality + 15-minute read-only runtime-smoke proposal; runner not attested |
| #189 | `233f4ed4` / main | Quality `40975318062` SUCCESS | Duplicate two-hour full-quality cron; do not enable alongside #188 |

### AI benchmark correction

The prior #196 experiment ran qwen3:4b and qwen3:8b for three repeats each. All six evaluator runs exited non-zero due to `ReadTimeout`; the workflow incorrectly ended green because it captured exit codes but never failed after artifact upload. The reports had no usable model score, provider token usage, latency or cost.

The architecture owner has applied a corrective change on #196 branch:
- CPU comparison becomes qwen3:1.7b and qwen3:4b.
- Default first diagnostic run is one repeat per model; 3/5 repeats only after the baseline completes.
- Per-call timeout is 300 seconds; workflow timeout is 120 minutes.
- Experimental output cap is 2,048 tokens and request cap is 65,536 bytes.
- Reports and exit codes are uploaded before the final gate; missing repeats or any non-zero evaluator exit fail the job.
- Tests pin the fail-closed workflow behavior.

These changes require a fresh Actions run and artifact inspection. No model quality, token efficiency, cost or production throughput claim is made until the new run produces evidence. A failed model gate is a benchmark result, not a successful model.

### Integration order now enforced

1. Treat #201 as the one clean-main source integration candidate; do not add the entire #185/#194/#196 branch histories.
2. Keep #197/#198/#199/#200/#202 as narrowly scoped main-based contracts; verify exact current heads before selecting blobs.
3. Port #194/#204 HITL and #196 AI telemetry only after dependency, migration, Compose, Core/Portal/Worker conflict and security review. Preserve immutable Core ownership and no-effect synthetic mode.
4. Implement one T2 customer journey over the clean-main candidate; no more parallel story or Portal prototypes.
5. Add ITIL lifecycle evidence (N1/N2/N3, P1 rationale, SLA/OLA, incident commander, Problem/PIR/Change/Knowledge) only where backed by explicit synthetic records and clearly labelled.
6. Build one cumulative package from a clean source tree with exact commit, manifest, migration inventory, image references, checksums, clean install/upgrade/rollback tests.
7. Keep #188 as the only future schedule candidate; do not activate #189. Keep #146/#153 disabled and #187 deferred.

### Explicit unavailable surfaces

The current GitHub session can inspect and change repository source and GitHub Actions. It does not provide Debian SSH/Docker access or a ChatGPT Lab control surface. Therefore no Debian cron/runner/systemd/volume/image/applied-SHA change is performed or claimed. The five existing ChatGPT schedules remain the work lanes; Schedule 5/5 owns architecture/release convergence and no sixth schedule is created.


## 2026-10-30 16:30 Europe/Paris — ITIL customer-story vertical slice

- #201 was extended on its clean-main branch with 14 explicit synthetic ITIL checkpoints in `app/portal/acme_impact_read_model.py`, projected by `app/portal/acme_explore_story.py` and rendered by `app/portal/acme_explore_story_client.js`.
- Each checkpoint now names ITIL practice, owner role, handoff and evidence required. It covers NOC L1/L2, Service Desk N1, Incident Manager N2, Incident Commander, SRE/N3, Knowledge, Problem, Change Manager, authorized approver, simulator, independent verifier, closure and continual improvement.
- Every checkpoint remains `MISSING`; no runtime capture, GLPI ticket, SLA breach, approval or remediation is asserted. Runtime, production and LIVE flags remain false.
- Exact head `890977be` CI run `41081252003` failed only in the synthetic DOM test harness because its old three-step response fixture did not include the newly required ITIL metadata. The Python API/model contract test passed. The JS fixture has been updated in commit `c00ceb11`; exact-head Quality run `41081496981` is now IN_PROGRESS. Do not mark this slice qualified until that run passes.

## 2026-10-30 15:36 UTC — selective convergence and CI regression

- #201 `main@27deb9b1` remains the only clean-main draft integration candidate; 14 synthetic ITIL checkpoints introduced in Portal were not matched by the nine-step Chromium/qualification fixture. #201 `c00ceb11` Quality 41081496981 FAILED; 5/5 added test-only `2dafb007` with the remaining 14-step expectation and forged ITIL metadata negatives. New exact-head Quality 41082175476 pending. Do not copy old nine-step contracts or weaken `MISSING`/identity/source checks.
- #196 `135328f5` remains stacked on stale #194 base `1fade3e5`; 1.7B and 4B Ollama artifacts show evaluator_exit=1, 0/5 cases and ReadTimeout. Push 41080394263 model jobs now FAILURE (correct fail-closed behavior). No real model metrics may be reused as a PASS. Keep selective migration/OIDC/outbox/telemetry dependency audit before port to #201.
- #188 preferred future schedule remains unmerged; #189 duplicate, #146/#153 unauthorized, #187 deferred. No Debian or LIVE claim.

### 2026-10-30 15:40 UTC — verified selective #202 reuse

[#201](https://github.com/alimtalbi-ata/aiops/pull/201) `5f2feb08` passed [Quality 41082437029](https://github.com/alimtalbi-ata/aiops/actions/runs/41082437029) 3/3 and Chromium 6/6 with all 14 ITIL checkpoints MISSING. 5/5 then selectively ported #202 `5fe17abd` security response changes into the same #201 candidate, HEAD `59ba22f1761c35ed46b92ffe5a3c4d050ed4f7c6`, preserving exact `acme_run_detail.py` blob `14729a4a8c3b54757e5e78e12a8043202adb7caa` and adding the negative header tests without wholesale replacement of divergent test history. #202 own [Quality 41082145661](https://github.com/alimtalbi-ata/aiops/actions/runs/41082145661) SUCCESS, but combined [#201 Quality 41082715412](https://github.com/alimtalbi-ata/aiops/actions/runs/41082715412) QUEUED. No session/OIDC/tenant/runtime promotion.

<!-- convergence-5of5-477da60-20261030 -->
## 5/5 selective transport register — 2026-10-30T16:15:33.055Z

**Audit UTC:** 2026-10-30T16:15:33.055Z. **Release candidate:** [#201](https://github.com/alimtalbi-ata/aiops/pull/201), base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, exact HEAD [`477da60d92dc777e1e635eea4c5510c350a5d90c`](https://github.com/alimtalbi-ata/aiops/commit/477da60d92dc777e1e635eea4c5510c350a5d90c), **28 ahead / 0 behind**, draft and unmerged. [Exact-head Quality 41088096834](https://github.com/alimtalbi-ata/aiops/actions/runs/41088096834) **QUEUED** at audit; previous #201 [Quality 41082715412](https://github.com/alimtalbi-ata/aiops/actions/runs/41082715412) **3/3 SUCCESS** on old `59ba22f1`, not on this new SHA.

| Source lane / exact head | Transported paths and Git blob prefixes | Scope / remaining gap |
|---|---|---|
| 1/5 #198 `0504b1c4` | `tools/find_acme_demo_run.py` `0b2cad84`; `tests/test_find_acme_demo_run.py` `a41b6d97` | Fail-closed canonical/epoch-bounded UTC Evidence metadata; **not** independent Evidence attestation, tenant ACL or real Core probe |
| 2/5 #202 `6a0403b7` | `app/portal/acme_run_detail.py` `b77645bc`; `tests/test_portal_run_detail.py` `3a88d1b3`; `app/portal/portal_run_link_client.js` `fb1f133d`; `tests/test_portal_run_link_client.cjs` `3eda6543` | Four-field Core read remains SYNTHETIC_ONLY; reject extra authority, show 401/403/503, no SSO/OIDC or tenant proof |

All six blobs were inserted into #201's existing tree, preserving its Portal story, `app/portal/main.py`, `compose.yml`, `app/core/main.py` and Policy. GitHub Actions **queued** for new head; previous green does not transfer. #205 remains a mock-only GLPI↔Run xref design; #194/#204 OIDC/outbox and #196 AI telemetry remain stacked and unported. Do not merge #185 wholesale or enable #188/#189 together; #146/#153 deploy disabled and #187 deferred.

## 5/5 exact-blob Portal correction — 2026-10-30 17:08 UTC

[#201](https://github.com/alimtalbi-ata/aiops/pull/201) base `main@27deb9b1`, head `1d3a902877d556549425a95cd4cef792c5c000c8`: only `app/portal/main.py` updated from blob `e7aaed065425478937fb534f15bea5b9f0bc05a7` to **`0dac60be551f58e8a2bf578178a4ff298aef5118`**, identical to #202 exact source `6a0403b7939b6739cf664dec1cf4d78eec65faaf`. Reused the existing home route and response injection, not a new Portal. Adds `Cache-Control: no-store`, Pragma, CSP `frame-ancestors 'none'`, `X-Frame-Options: DENY`, nosniff and referrer policy, preserving direct `home()` callers. Fixes #201 prior exact-head [Quality 41088096834](https://github.com/alimtalbi-ata/aiops/actions/runs/41088096834) failing `test_existing_home_cockpit_is_no_store_and_anti_framing`; **new-head Quality 41096370024 pending**. Do not infer T1/T2 authentication from these mock tests.

Latest #198 `0091cc56` has offline fixture Quality 3/3, locator 16/16, fixture 6/6; #196 `747f0df4` has 2/8 Ollama job failures, qwen3:1.7b ValidationError / qwen3:4b ReadTimeout (3/3 evaluator failures each). #194/#204 migration 011, OIDC/HITL/outbox and #196 telemetry remain **not ported** to #201; #193 title-derived GLPI links remain unsafe. No parallel engine or duplicated module work.

### Source collision review and CI resolution — 2026-10-30 17:11 UTC

#201 head `1d3a902877d556549425a95cd4cef792c5c000c8` [Quality 41096370024](https://github.com/alimtalbi-ata/aiops/actions/runs/41096370024) **SUCCESS 3/3**; Portal 26/26 Python, 7/7 JS. Exact `app/portal/main.py` source blob matches #202.

Selective port must first reconcile **#194 ↔ #201** overlaps `.github/workflows/quality.yml`, `app/core/main.py`, `app/portal/main.py`, `compose.yml`; **#196 ↔ #201** overlaps `.github/workflows/quality.yml`, `compose.yml`, `config/.env.example`; **#204 ↔ #201** overlaps `.github/workflows/quality.yml`. #194 and #196 also both modify `app/intelligence/main.py` and `tests/test_intelligence_contract.py`. Treat these as contract/implementation collisions, not cherry-pick-ready files. Require dependency-aware minimal diff, migration 011 ordering, identity/tenant/outbox failure tests, no LIVE and exact-head CI before adding to #201.

## Exact-source Portal identity-fence port — 2026-10-30 18:xx UTC

#202 `9c462f0c6ff0e665220a3bc30247e2847b94900a` is main-based and [Quality 41101417585](https://github.com/alimtalbi-ata/aiops/actions/runs/41101417585) SUCCESS. #201 selectively imported **two** source blobs only: `app/portal/acme_run_detail.py@2500b19deff5fba79001c639c335d05c5acd7152` and `tests/test_portal_run_detail.py@d0cc63acf753de0b4ad511006eab9383d9da68c7`. Commits `3356aac5` and `7bc825b3`, #201 new HEAD `7bc825b30e13c9a685192fde7486cad5632061fe`, base `main@27deb9b1`. [Exact-head Quality 41104533241](https://github.com/alimtalbi-ata/aiops/actions/runs/41104533241) QUEUED when recorded. Strictly require the four Core NOC Run fields (`run_id`, `incident_id`, `mode`, `status`); unknown authority/ticket/policy claims fail HTTP 503 UNKNOWN. This is a read-only synthetic guard, **not** tenant ACL, OIDC, Evidence authority or GLPI correlation.

Fresh stacked sources: #204 HEAD `1d030724` (four workflows SUCCESS, still stacked #194), #196 HEAD `747f0df4` (Quality FAILURE due Ollama evaluators, companions SUCCESS), #205 HEAD `2964fdbb` (mock-only Quality SUCCESS). Do not mass-merge #194/#196 or replace overlapping Core/Portal/Compose/quality files. Next isolated port must reconcile migration 011, identity/outbox revision fencing and telemetry dependencies; preserve fail-closed tests and exact SHA. No parallel engine/store/Portal.


### 2026-10-30 19:10 UTC — exact-blob reuse checkpoint

- #202 `2e8e90371e89d8760fdfc98736dad7531acf9a3c` (main-based): [Quality 41109683748](https://github.com/alimtalbi-ata/aiops/actions/runs/41109683748) SUCCESS 3/3. Ported **only** `app/portal/acme_run_detail.py` (blob `fe55bd199398eb92593d43deabea3d2cce6ae2b2`) and `tests/test_portal_run_detail.py` (blob `587578bf99dfc42bec10500f193cc16f0b59ef64`) to #201 via commits `70203a0f`, `7e4cbe9d`. Added permanent SYNTHETIC story-context disclaimer across HTTP 200/401/403/503. This does not authenticate the Run, tenant, Evidence or GLPI.
- #201 now `7e4cbe9d75aedccf2078ca50d052e6d0796c284e`, base `main@27deb9b1`, 33 ahead/0 behind; **new exact-head CI NOT_OBSERVED**. Previous #201 `7bc825b3` [Quality 41104533241](https://github.com/alimtalbi-ata/aiops/actions/runs/41104533241) SUCCESS 3/3, but not transferable. #204 `f19473ac` stacked on #194, all four workflows SUCCESS; failure tests offline only. #196 `747f0df4` stacked on older #194, Quality FAILURE; real-model qualification blocked. #185 remains divergent story-only. No wholesale merge, alternate Portal, or second ledger.


### 2026-10-30 ~20:08 UTC — canonical status selective reuse

#202 HEAD `d623c173b1414649298a31bc87e1948dde775395`, main-based, [Quality 41117705285](https://github.com/alimtalbi-ata/aiops/actions/runs/41117705285) SUCCESS 3/3, contains one additional two-file delta since `2e8e9037`: validate Core Run `status` against `shared.domain.STATUSES`, with negative tests for forged strings, malformed values and seven canonical statuses. Main/#201 already have `app/shared/domain.py` blob `aa7401ac12ec185a138aeaa526da7cb1b9aa06fb`; no new dependency required. Ported **exact blobs** to #201: `app/portal/acme_run_detail.py` source `28a7604ede814664c101e7748878060aed4ce7e6` (commit `81f9645d646e3c838450402ef84031391cff8c5d`); `tests/test_portal_run_detail.py` source `b1f51b1d0b613da88a7e5e980ca3c17465f7cf7b` (commit `8236c93460a160914247aaca8141253ebddf3aac`). New #201 HEAD `8236c93460a160914247aaca8141253ebddf3aac`, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, 37 ahead/0 behind; [Quality 41120972224](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224) QUEUED at posting. No identity/tenant/GLPI/Evidence authority granted.

#204 `b17f8a5c` stacked on #194 `40d38705`: [Quality 41118324370](https://github.com/alimtalbi-ata/aiops/actions/runs/41118324370) SUCCESS and 36/36 offline HITL/outbox/contract tests, but source changes to Core overlap #201 and must be reviewed contract-by-contract before any port. #196 `747f0df4` still stacked on older #194 `1fade3e5`; Quality FAILURE and no qualified real-model benchmark. #185 remains divergent story-only. Do not mass-merge.

## 2026-10-30 21:10 UTC — exact source collision checkpoint (5/5)

Candidate [#201](https://github.com/alimtalbi-ata/aiops/pull/201) `8236c93460a160914247aaca8141253ebddf3aac` on `main@27deb9b1`: Quality [41120972224](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224) **SUCCESS 3/3**, 37 ahead/0 behind. The Chromium artifact [13007279749](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224/artifacts/13007279749) is a synthetic screenshot ZIP (SHA256 `083ec62ececcbb11e2c47ef777619e86c7c5d9bfa11d9ff67713e4502d5718dc`), not a cumulative package.

**Git blob dependency comparison (read-only):**

| Path | #201 | #194 / #204 or #196 | Port decision |
|---|---|---|---|
| `app/core/main.py` | `ef5cb542c637` | #194 `fedf63c07557`; #204 `a04001ae34ff` | collision; reconcile API/ledger first |
| `app/worker/workflow.py` | ABSENT | #194 `aa53a808e965`; #204 `3039f0b63922` | needs orchestration dependency graph and tests |
| `db/migrations/011_hitl_decision_outbox.sql` | ABSENT | #194/#204 `b096af57cb19` | migration ordering and sandbox upgrade/rollback gate |
| `app/core/hitl_identity.py` | ABSENT | #194/#204 `f22edf6b3feb` | identity provider and tenant/actor proof required |
| `app/shared/hitl_identity.py` | ABSENT | #194/#204 `fbdba0138ce5` | no unverified approval authority |
| `app/intelligence/main.py` | ABSENT | #196 `e5568c4af6bf` | requires full Intelligence contract/dependencies |
| `tools/evaluate_ai_core.py` | ABSENT | #196 `d8dbdec23f75` | preserve deterministic vs real-model separation |
| `compose.yml` | `679fca072bb5` | #196 `7682e9edb4d0`; #204 `926dfdc4bfae` | manual selective service reconciliation |
| `.github/workflows/quality.yml` | `c67429b3e1ae` | #196 `5de1992a445f`; #204 `456d38453b7b` | do not overwrite exact-head quality gates |

[#204](https://github.com/alimtalbi-ata/aiops/pull/204) new HEAD `7372be2098ef955db9a4e14f2b94340ac447d509` has four exact-head workflows SUCCESS, but remains stacked on #194. [#196](https://github.com/alimtalbi-ata/aiops/pull/196) `747f0df4b8bae0fa0265b6dc568558a6a9057ad1` Quality FAILURE due to Ollama; no model PASS. Do not mass-merge #185/#194/#196/#204. Port exact blobs only after dependency and collision review, with test command, N/N and new combined-SHA CI.

## 2026-10-30 ~22:27 UTC — tenant read boundary and #204 delta

- **#201 exact HEAD** `8236c93460a160914247aaca8141253ebddf3aac`, `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, Quality [41120972224](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224) SUCCESS 3/3. The `app/portal/acme_run_detail.py` projection (blob `28a7604ede814664c101e7748878060aed4ce7e6`) currently returns a Run/Incident/status under a shared internal bearer with `tenant_acl_qualified=False`; **do not accept as tenant-authorized cockpit**. Core-owned actor+tenant scoped exact-Run read and negative cross-tenant HTTP/API/HTML tests are the blocking contract. Preserve UNKNOWN/UNAUTHORIZED until verified.
- **#204 exact HEAD** `b8f0c24c1bb1c31b90d46a6d7d8977883ef6792c`, stacked on #194 `40d38705cf2bde3be6052340442c117a81908f65`. [Quality 41136324582](https://github.com/alimtalbi-ata/aiops/actions/runs/41136324582) 6/6 SUCCESS; V2.8 41136324660, Offline 41136324565, Historical 41136324639 SUCCESS. Compared with `7372be20`, three commits changed `app/worker/workflow.py` blob `2e6edd7195a9dba9c9c9f4a23b26ea97ef14f0db`, `tests/test_hitl_failure_injection.py` blob `a91237a99d79e2c93aae3517dc8fb9237775e01a`, and `tests/test_hitl_outbox_failure_injection.py` blob `cafef790ab3bcb659b983f1dcc77569aefdc530f`. Nine Worker return paths explicitly fence `execution_allowed=false`, `effect_allowed=false`; offline negatives for revoke/forged actor and malformed lease/ACK. 4/5 handoff reports 42/42 offline PASS; runtime PostgreSQL/Temporal/OIDC still NOT_TESTED/NOT_ATTESTED. **Do not transplant Worker without Core, migration 011, identity, Policy version, tenant/SoD and Compose reconciliation.**
- **#195 previous exact HEAD** `5034be415aac0029ba5cf6b8f2bf68b9f607dd59`, Quality [41129279978](https://github.com/alimtalbi-ata/aiops/actions/runs/41129279978) SUCCESS 3/3. **#196** `747f0df4` Quality 41083049858 FAILURE; zero qualified real-model repeats. #185 still divergent; #188 preferred and #189 redundant.
- **Package evidence distinction:** #204 Quality artifact `13015508690` named `aiops2-core-deployment-kit` is from a stacked SHA, not #201. Its contents and install/rollback were not inspected in this checkpoint. No main-based cumulative release kit qualified.

## 2026-10-31 5/5 — selective Portal tenant disclosure fence

#202 `f3943020d0d66d60c92dbf9b0d0c3fbb7913789e` is main-based and [Quality 41142124145](https://github.com/alimtalbi-ata/aiops/actions/runs/41142124145) SUCCESS 3/3. Compared with #201 previous `8236c934`, its Portal implementation blob `3b85f6d6e97e774b0d2379fc88ca4da1d8352bae` and test blob `029ef4b12988732bbd407a55edd48763205a6ecb` remove four-field Run/Incident/status disclosure under shared bearer. Both were ported byte-for-byte in #201 new HEAD `f38014c92b85763be8ac3f72042b50a48dbba95c` on `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, without replacing Core, Compose, Worker, Policy or Quality. Source CI green does not transfer to combined SHA; #201 exact-head CI pending at port. The fix is fail-closed (503 UNKNOWN) **not** a Core tenant authorization implementation. Next dependency is Core-owned actor/tenant exact-Run read with negative cross-tenant API/HTML and T1 tests.

#204 latest `c1fc37c16024ca3ae8b31aad7b604f71993eebcd` stacked on #194 `40d38705` has [Quality 41141963825](https://github.com/alimtalbi-ata/aiops/actions/runs/41141963825) 6/6 SUCCESS, V2.8 41141963842, Offline 41141963817, Historical 41141963895 SUCCESS; delta from `b8f0c24c` changes Worker main/workflow and HITL failure test, **not** safe for wholesale transplant. #196 `747f0df4` remains Ollama Quality FAILURE. #185 still divergent. Keep #188 only scheduling candidate; #189 duplicate.


### 2026-10-31 5/5 — Portal read contract requires non-enumerability

#202 HEAD `f3943020d0d66d60c92dbf9b0d0c3fbb7913789e` and #201 HEAD `f38014c92b85763be8ac3f72042b50a48dbba95c` share Portal blob `3b85f6d6e97e774b0d2379fc88ca4da1d8352bae`. It correctly redacts Run/Incident/status under unqualified tenant ACL but still distinguishes valid Core Run (`connection_state=CONNECTED`, reason `TENANT_ACL_NOT_QUALIFIED`) from missing/unavailable/unqualified responses, including in HTML. This is a **source-review finding**, not a demonstrated runtime exploit. [Handoff to 2/5 #202](https://github.com/alimtalbi-ata/aiops/pull/202#issuecomment-6536560492): make unauthorised Run responses indistinguishable, test valid/absent/foreign/error API and HTML, then hand off exact blobs/CI for selective #201 port. Core server-derived actor+tenant exact-Run authorization remains a separate prerequisite. #201 [Quality 41145124544](https://github.com/alimtalbi-ata/aiops/actions/runs/41145124544) SUCCESS 3/3 and #195 previous [Quality 41145381815](https://github.com/alimtalbi-ata/aiops/actions/runs/41145381815) SUCCESS 3/3 do not qualify T1/T2. No merge or LIVE effect.

## 2026-10-31 UTC — selective Portal bootstrap convergence

- Source #202 `d42e47e7d68a5150dab86005e9272c4d51f37a1a`, [Quality 41153039207](https://github.com/alimtalbi-ata/aiops/actions/runs/41153039207) SUCCESS 3/3. Six exact Git blobs ported to clean-main #201 `e6f9ad656d3b6f92ef065f7aec13f3d1b2ca3d74`: `app/portal/main.py` `799edbe91c15fc847e47dc0c9045ca9a38a156f9`; `app/portal/portal_bootstrap_client.js` `cae5dbe8d00b92c996f0bfb41bc124b83ffc39d8`; `tests/test_portal_bootstrap_auth.py` `6d813d8d12944caf98720eb13ffd5cb70bb49b3a`; `tests/test_portal_bootstrap_client.mjs` `0ceb5029a423c21ef7f492ee5d101532677bd686`; `tests/test_portal_run_detail.py` `3fe3b9468fef299bd0570e68b554e00e4e3d8d36`; `tests/test_portal_run_link_client.cjs` `9f894556b54243f68b739d95a8c0b7d4adb913ea`. Each destination blob matched source; #201 exact-head [Quality 41155594473](https://github.com/alimtalbi-ata/aiops/actions/runs/41155594473) IN_PROGRESS at observation. No wholesale merge.
- #202 bootstrap containment forbids unscoped Core/Twin reads under a shared bearer; this is not OIDC, tenant authorization, or permission to expose a Run. Remaining exact-Run connection-state oracle and NOC correlation tenant scope require Core-owned actor+tenant authorization and indistinguishable denial tests.
- #204 stacked `8aded617fc01c3b599c172b755921579f6257d95`: [Quality 41153751242](https://github.com/alimtalbi-ata/aiops/actions/runs/41153751242) FAILURE in real Temporal runtime-e2e, artifact `13024756054` reports RUNNING with 0 Analyst, 0 Critic, 0 Policy records, 1 Evidence, 0 effects. Source/CI green on previous heads does not transfer. Do not port full Worker/migration tree until failure and 2.1.0/2.2.0 Policy contract collisions are resolved.
- #196 real Ollama 1.7B/4B still has zero qualified repeats. #185 remains divergent and scenario-only. `RELEASE_STABLE=NO_GO`.

### Exact-head CI recheck — 2026-10-31 UTC

#201 `e6f9ad656d3b6f92ef065f7aec13f3d1b2ca3d74`: [Quality 41155594473](https://github.com/alimtalbi-ata/aiops/actions/runs/41155594473) **COMPLETED SUCCESS 3/3 jobs** (policy-and-static, core-postgres-noc-real-integration, grafana-real-integration). Logs: Portal bootstrap HTTP **6/6**, Run API/HTML **32/32**, Run-link JS **8/8**, bootstrap DOM JS **5/5**, Chromium synthetic **6/6**, cumulative-kit guard **12/12**. T0 **GO limited** on this exact head; **T1 still BLOCKED**, T2 NOT_QUALIFIED, T3 NOT_ATTESTED, T4/T5 NO-GO.

[Artifact 13024589352](https://github.com/alimtalbi-ata/aiops/actions/runs/41155594473/artifacts/13024589352) downloaded and inspected: ZIP 237,689 bytes, SHA256 `451544e07a6da6a5284705fad6947cf5c1be3b917c1a1dfbb7e6fe93c9ea5b87`, 2/2 ZIP members CRC PASS; screenshot PNG SHA256 `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca` matches metadata. `source_head_sha=e6f9ad65…`, `base_sha=27deb9b1…`, `checkout_sha=58c8d9b5…`, `runtime_authenticated=false`, `glpi_ticket_id=null`, `production_qualified=false`. This is a CI-simulated screenshot, **not** a T2 runtime receipt or cumulative kit.

### 2026-10-31 02:28 UTC — #204 recovered runtime branch, selective-port boundary

- **Source:** #204 `fb05a75e48827fec38d30a15532a6549492ebf45` stacked on #194 `40d38705cf2bde3be6052340442c117a81908f65`. Compared with failed `8aded617fc01c3b599c172b755921579f6257d95`, exactly 2 commits and 2 modified paths: `app/worker/main.py` (+24/-3) and `tests/test_hitl_failure_injection.py` (+63/-0). [Quality 41158324110](https://github.com/alimtalbi-ata/aiops/actions/runs/41158324110) SUCCESS 6/6; separate Offline/Historical/V2.8 SUCCESS. [Runtime artifact 13026113139](https://github.com/alimtalbi-ata/aiops/actions/runs/41158324110/artifacts/13026113139) SHA256 `58186c794a3e90a7e63b2b1f48e4bc4e20b15468b548e1873de07597b66d34f2`, 2/2 CRC PASS. One synthetic Run RESOLVED, analysis/critique/policy 1/1/1, Evidence 12, effects 0. This is **stacked-branch runtime recovery**, not proof of main-based integration or tenant authorization.
- **Selective reuse rule:** inspect the exact `app/worker/main.py` change and failure tests against #201 `e6f9ad656d3b6f92ef065f7aec13f3d1b2ca3d74` before port; preserve Core-owned ledger, migration 011 ordering, Temporal fencing, no-effect SIMULATE, and do not mass-merge #194/#204. Core/Worker/Compose/Portal and migration collision review remains open. T2 on #201 is NOT_QUALIFIED.
- **Portal source:** #202 `eb7bd709106695e05fd80e241cdd6a22265ba535` [Quality 41158529106](https://github.com/alimtalbi-ata/aiops/actions/runs/41158529106) SUCCESS, but `app/portal/acme_run_detail.py` blob `3b85f6d6e97e774b0d2379fc88ca4da1d8352bae` matches #201 and retains unqualified Run existence oracle. T1 BLOCKED. **AI:** #196 `747f0df4` real Ollama FAILURE, zero scored repeats; deterministic CI evaluation is separate.


### 2026-10-31 03:27 UTC — exact #201 response-oracle fix; reuse boundary

#201 HEAD `a5bdb5bfeb8a05bd761cba7268b9c6ffc8fc3b95` (main base `27deb9b1a66faf27df8d69b137a63451f7649d80`) now contains a **targeted two-file response normalization**: `app/portal/acme_run_detail.py` blob `33b8e2ea2728d8b357ad33355a9e87cc8cf8042b` and `tests/test_portal_run_detail.py` blob `a12ae7fa3153a3a349885c9f23902158054c8487`. 503 valid/absent/foreign/malformed/timeout API and HTML responses use one UNKNOWN tenant-unqualified projection, without `CONNECTED` existence indication. Upstream 401/403 remain intact; Core actor+tenant exact-Run authorization is **not** implemented and timing non-enumerability is not attested. Exact-head CI PENDING at write; previous #201 `e6f9ad65` Quality 41155594473 SUCCESS 3/3 is not transferable. Source #202 HEAD `2f49443e` Quality 41162565031 SUCCESS 3/3 still carries older Run detail blob `3b85f6d6e97e774b0d2379fc88ca4da1d8352bae`; lane 2/5 may selectively reuse these two exact #201 blobs after independent review, not mass-merge.

#204 latest stacked HEAD `b4198e1e4a7fb763f632d1cd4d5a78b7db92f74e` Quality 41162880436 SUCCESS 6/6; latest four commits since `fb05a75e` touch `app/core/main.py` and `tests/test_hitl_outbox_failure_injection.py`, not a clean-main port. #196 `747f0df4` remains Ollama Quality FAILURE, 0 scored repeats. T1/T2/T4/T5 remain blocked or unqualified. Do not cherry-pick #194/#204/#196 stack wholesale; review migration 011, Core/Worker/Compose/Portal ownership and exact tests first.

### 5/5 2026-10-31 UTC — embedded release-manifest integrity guard

#201 main-based `e116d04c791b6f5a5028d6f2cc3797a547b460ec` adds only `tools/check_cumulative_release_kit.py` and `tests/test_cumulative_release_kit_gate.py` (four new negative cases). The gate now cross-checks embedded `manifests/MANIFEST.json` entries (path, byte size, SHA256), checks release-version agreement and rejects missing/malformed embedded manifest; it does not repair the package generator or attest installation. [Quality 41169101273](https://github.com/alimtalbi-ata/aiops/actions/runs/41169101273) IN_PROGRESS at observation. #204 stacked `7b7db90b71897b070deb20ca58dab62082bf0f80` [Quality 41166983844](https://github.com/alimtalbi-ata/aiops/actions/runs/41166983844) SUCCESS 6/6, but newly audited artifact 13029760540 still has **30/68 embedded SHA256 mismatches**, despite 406/406 FILES-SHA256SUMS PASS; release `8.0.0` vs `2.1.0-core-rc1.4`. #202 `4c1ffed2` now shares exact Portal Run/test blobs with #201; actor+tenant Core ACL remains missing. #196 real Ollama benchmark remains FAILED. **Do not port or merge the stacked #204 package as a cumulative kit. T1/T2/T4/T5 not qualified.**


### 2026-10-31 06:27 Europe/Paris — source-specific release inventory repair (stacked only)

- #204 new HEAD `f3ee9e104f3bcbb7466a8de9b68f132fe0851022`, base #194 `40d38705cf2bde3be6052340442c117a81908f65`: [Quality 41171155211](https://github.com/alimtalbi-ata/aiops/actions/runs/41171155211) SUCCESS 6/6. Delta from `7b7db90b` touches `app/worker/main.py`, `app/worker/workflow.py`, `tests/test_hitl_failure_injection.py`, not the package generator.
- #206 draft `020a05dfc186d20561ed7770b229088bc5c72238` is **stacked on #204** and modifies exactly four packaging/verification paths: `deploy/refresh_release_inventory.py` (new), `deploy/package.sh`, `tests/verify-package.py`, `tests/test_package_verification.py`. It proposes regenerating the staging-only embedded manifest and checking independent SHA256, byte size and version. Its historical V8 source metadata is preserved as provenance; do not treat the source V8 inventory as a 2.1.0 release receipt. Initial CI [41172832388](https://github.com/alimtalbi-ata/aiops/actions/runs/41172832388) QUEUED; no repaired artifact or rollback attested.
- Selective porting rule: review #206 exact four-file diff and fresh artifact against #201 main-based `e116d04c791b6f5a5028d6f2cc3797a547b460ec` before integrating. #201's stronger independent source/inventory guard remains authoritative; do not weaken it, do not mass-merge #204/#194. #196 remains real-model FAILED; actor+tenant ACL and combined T2 remain absent. T4/T5 NO_GO.


**#206 exact-head source qualification (2026-10-31 06:38 Europe/Paris):** `516e32b1540077ab059f651d78020c2b365b3fd4`, [Quality 41172956555](https://github.com/alimtalbi-ata/aiops/actions/runs/41172956555) SUCCESS 6/6, package verifier 13/13. [Artifact 13031961877](https://github.com/alimtalbi-ata/aiops/actions/runs/41172956555/artifacts/13031961877) independently audited: embedded 68/68 digests/sizes, FILES-SHA256SUMS 407/407, extraction/repack 408/408, ZIP CRC PASS. This closes the **stacked package manifest semantic mismatch**, not main-based #201 cumulative kit, source/checkout SHA separation, SBOM, install/upgrade/rollback, T1/T2 or LIVE. **Reuse only the exact four-file #206 patch after a clean-main dependency review. T4/T5 remain NO_GO.**

### 2026-10-31 07:27 Europe/Paris — #206→#201 selective source dependency gate

[Draft #207](https://github.com/alimtalbi-ata/aiops/pull/207) is based on #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec` and proposes three paths only: `deploy/refresh_release_inventory.py`, `tests/test_release_inventory_refresh.py`, `.github/workflows/quality.yml`. Source helper #206 blob `16687be3e857f4b1601972293aa2399e76bca909` is adapted to reject symlink parents in a disposable staging tree. Exact #207 HEAD `0d0984cd2c8cf9fd5e934a4efb455d788cd5c6af`; 11 offline tests newly authored, CI NOT_OBSERVED at initial check. The legacy #201 package script blob `526c74dc55324650193017698fe450939b496a6a` cannot be replaced by the stacked #206 package script without VERSION, package_tree, migration 011, Worker and other dependency review. No package generator wired, no main-based kit or T4 qualification. Source #206 `516e32b1540077ab059f651d78020c2b365b3fd4` Quality 41172956555 SUCCESS 6/6 remains a separate stacked qualification. Core actor+tenant ACL, combined T2, real Ollama and rollback remain blocked/unqualified.


**#207 qualification closeout:** exact `0d0984cd2c8cf9fd5e934a4efb455d788cd5c6af` [Quality 41176811268](https://github.com/alimtalbi-ata/aiops/actions/runs/41176811268) SUCCESS 3/3; 11/11 staged inventory tests, 16/16 existing kit guard. Source #206 helper is now available on a targeted PR to #201, with an additional symlink-parent fence; no generator integration. [Synthetic Chromium artifact 13033831546](https://github.com/alimtalbi-ata/aiops/actions/runs/41176811268/artifacts/13033831546) CRC PASS, SHA256 `438abee56ab02f01bf8f68bf947579c071e8d695fd55607f23526a80511fcc2b`, no runtime auth or GLPI. No T4 promotion, no package install/rollback.


### 2026-10-31 ~08:30 Europe/Paris — #208 exact-source guard and #204 semantic kit recheck

- [#208](https://github.com/alimtalbi-ata/aiops/pull/208) draft from #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec`, HEAD `dd308475e17e1c5315da6b3caf73fba42e0e647a`: two changed paths (`tools/check_cumulative_release_kit.py`, `tests/test_cumulative_release_kit_gate.py`); checks every archive member against tracked Git HEAD, not only mandatory paths, while keeping generated release/checksum manifests independently checked. Three new source-integrity regressions. [Quality 41181004360](https://github.com/alimtalbi-ata/aiops/actions/runs/41181004360) in progress at source checkpoint; no PASS claim. Target is read-only inventory qualification, not a new packager or deployment engine.
- #207 `0d0984cd2c8cf9fd5e934a4efb455d788cd5c6af` (base #201) [Quality 41176811268](https://github.com/alimtalbi-ata/aiops/actions/runs/41176811268) SUCCESS 3/3, 11/11 staged helper tests; helper still unwired to #201's legacy `deploy/package.sh@526c74dc55324650193017698fe450939b496a6a`. Do not merge #206's stacked packager wholesale.
- #204 new stacked `d5926feab3be7ff4496af23377541bab53dc1d70` [Quality 41179273364](https://github.com/alimtalbi-ata/aiops/actions/runs/41179273364) SUCCESS 6/6, but independently inspected artifact 13033619597 has 30/68 stale embedded SHA and size entries. #206 `516e32b1540077ab059f651d78020c2b365b3fd4` fixed this in its **own** stacked artifact 13031961877 (68/68), not in #204 or #201. Reuse source blobs only after exact-base compatibility tests.
- Source-integrity gate remains separate from runtime qualification. T1 tenant ACL BLOCKED, T2 single-Run ACME NOT_QUALIFIED, T3 Debian NOT_ATTESTED, T4 kit/rollback NO_GO, T5 LIVE NO_GO; `RELEASE_STABLE=NO_GO`.

### 2026-10-31 ~09:40 Europe/Paris — main-based generator/guard collision resolved in targeted draft, CI pending

[#209](https://github.com/alimtalbi-ata/aiops/pull/209) is based on #207 `0d0984cd2c8cf9fd5e934a4efb455d788cd5c6af` (which is stacked on #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec`), not on divergent #204. HEAD `9d515aee54a809bf06d81d63609b06d7b7a7e571`, changed paths `tools/check_cumulative_release_kit.py` and `tests/test_cumulative_release_kit_gate.py`; exact source #208 `dd308475e17e1c5315da6b3caf73fba42e0e647a`, blobs `18a553715169db2d8bb7a81bf60702afa2881f9c` / `cef7a51db40258beb386e6d3754e23ed316be8e0`. The generated embedded manifest may differ from Git only if the full JSON equals the deterministic source-derived refresh; all other ZIP source members retain exact-Git provenance. Three new negative/positive tests; [Quality 41185345014](https://github.com/alimtalbi-ata/aiops/actions/runs/41185345014) IN_PROGRESS, no PASS yet. This fixes a compatibility blocker between #207's helper and #208's strict source gate; **not** a main-based package or T4 proof.

#204 current `aa24982c8c93f017b710dc7658e66728ad86fbde` [Quality 41182602889](https://github.com/alimtalbi-ata/aiops/actions/runs/41182602889) SUCCESS 6/6 but new artifact 13035548118 independently audited 30/68 embedded SHA and sizes FAIL, 407/407 sidecar PASS, version mismatch 8.0.0 vs 2.1.0-core-rc1.4. Keep #206's corrected generator selective, not mass-merge. T1 Core actor+tenant BLOCKED, T2 combined ACME NOT_QUALIFIED, T3 NOT_ATTESTED, T4/T5 NO_GO. `RELEASE_STABLE=NO_GO`.


### 5/5 release inventory stop-line — 2026-10-31 10:31 Europe/Paris

- Refreshed #195 main-based `26436048ade4ff4ac20878d33dc89057c32cb2be`, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, [Quality 41185495625](https://github.com/alimtalbi-ata/aiops/actions/runs/41185495625) SUCCESS 3/3. #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec`, [Quality 41169101273](https://github.com/alimtalbi-ata/aiops/actions/runs/41169101273) SUCCESS 3/3. #209 `9d515aee54a809bf06d81d63609b06d7b7a7e571`, [Quality 41185345014](https://github.com/alimtalbi-ata/aiops/actions/runs/41185345014) SUCCESS 3/3, 22/22 source kit tests, 11/11 staged inventory tests. These are T0 contracts, not a main-based cumulative kit.
- **New audit finding:** #209 `tools/check_cumulative_release_kit.py` accepted `deploy/aiops_release.py` as both installation and rollback entrypoint, even though that script's `main()` refuses deploy/rollback and permits read-only audit only. It also accepted `deploy/deploy-acme-p0.py`, a partial four-service transaction, and did not require a separate upgrade entrypoint. File presence could falsely satisfy the entrypoint inventory gate; it never demonstrated exercised install/upgrade/rollback.
- **Targeted [draft #210](https://github.com/alimtalbi-ata/aiops/pull/210):** base #209 `9d515aee54a809bf06d81d63609b06d7b7a7e571`, HEAD `929ce398f5a3ea5660a834baf8bdb63e0bbda8ac`, changes only `tools/check_cumulative_release_kit.py` and `tests/test_cumulative_release_kit_gate.py`. Requires separate explicit install, upgrade and rollback entrypoint families; three negative regression tests cover read-only audit, partial P0 and install-only. [Exact-head Quality](https://github.com/alimtalbi-ata/aiops/actions/runs/41189139337) **IN_PROGRESS at this snapshot**; expected 25 tests, **N/N NOT_YET_OBSERVED**. This is a stricter source inventory gate, not an implemented rollback or a release package.
- #204 stacked current HEAD `08706694d73e7c2a05f7a26d25807e5e4868525d`, [Quality 41186634005](https://github.com/alimtalbi-ata/aiops/actions/runs/41186634005) SUCCESS 6/6 and other observed workflows green. 4/5 reports offline HITL 60/60 and synthetic Temporal E2E, but neither qualifies #201 T2, Core actor+tenant ACL, source provenance or T4 rollback. Latest previously audited #204 package still has 30/68 stale embedded digests; a new package on current #204 HEAD has **NOT** been independently audited here.
- **Gates:** T0 GO_LIMITED #201/#209, #210 PENDING exact CI; T1 BLOCKED actor+tenant Core/Portal; T2 NOT_QUALIFIED one integrated ACME Run; T3 NOT_ATTESTED Debian; T4 NO_GO main-based kit, install/upgrade/rollback; T5 LIVE NO_GO. `RELEASE_STABLE=NO_GO`. No main merge, runner/cron/host, GLPI write or LIVE action.

### 2026-10-31 11:33 Europe/Paris — exact-source reuse and ownership delta

| Owner / contract | Exact current source and evidence | Selective reuse decision / dependency |
|---|---|---|
| 1/5 ACME fixture/story | #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec` Quality 41169101273 SUCCESS 3/3 | Retain single ACME Incident/Run; no D2 same-SHA browser/API traversal attested; missing checkpoints remain SYNTHETIC/MISSING |
| 2/5 Portal actor+tenant | #202 `4c1ffed252051ad630d309339de59f85e41b63a9` Quality 41166571473 SUCCESS; #201 unchanged | Read-token and indistinguishable 503 are not Core actor+tenant authorization. Protect copilot/NOC/Run endpoints; negative cross-tenant/no-upstream tests before D1 |
| 3/5 Core ITSM xref | #205 `c3037d84f53cf2ff4846b479936ab9685f278955` Quality 41191517941 FAILURE; `app/shared/core_itsm_xref_read.py@6433f417d4e5b1b7a9d38092b3a116624a257987` and 17/17 mock contract tests PASS | CI blocked later by Playwright 1.55 unsupported Ubuntu 26.04 runner; rerun full browser test on supported runner, do not skip. No real connector/tenant-scoped Core readback; no merge by proxy |
| 4/5 Policy/HITL / PG16 | #204 `fe25a4a816cebb9ae2122a09946751ed4be926f0` stacked #194 `40d38705cf2bde3be6052340442c117a81908f65`; Quality 41191668178 SUCCESS 6/6; PG16 DR tables=32 PASS; isolated HITL 66/66 PASS | Reuse matching PostgreSQL 16 client wrapper, outbox fences and failure tests by exact blobs only. Still no Core tenant/SoD/OIDC runtime attestation, real concurrent restart or #201 D2 |
| 5/5 kit / benchmark | #206 `516e32b1540077ab059f651d78020c2b365b3fd4` corrected stacked generator; #210 `929ce398f5a3ea5660a834baf8bdb63e0bbda8ac` strict main-based source gate; #196 `747f0df4b8bae0fa0265b6dc568558a6a9057ad1` Quality FAIL | Never wholesale merge #206 into #201. New #204 artifact 13038908385: 408/408 sidecar PASS, **30/68 embedded SHA/size FAIL**, version drift. No D3 sandbox install/upgrade/rollback, no qualified Ollama repeats |

Three P0 tracks only: actor+tenant ACL, cumulative release kit, PostgreSQL 16/HITL restore. Release stays `NO_GO`; revert a targeted change by reverting its own commit/PR, never by resetting main.


### 2026-10-31 ~12:32 Europe/Paris — selective reuse, no merge by proxy

| Owner / contract | Fresh exact source and CI | Reuse decision / dependency / revert |
|---|---|---|
| 1/5 ACME fixtures/story | Canonical synthetic ACME source retained; no new same-SHA runtime receipt qualified in this cycle | Keep fixture source, service path and P1 label explicitly SYNTHETIC. Do not promote GLPI/impact/SLA or source SHA as runtime proof. |
| 2/5 Portal ACL/UI | #201 `c19ef9143cdbe51b5c2516cf82421bbfd2526628` → `main@27deb9b1a66faf27df8d69b137a63451f7649d80`; [Quality 41195184054](https://github.com/alimtalbi-ata/aiops/actions/runs/41195184054) SUCCESS 3/3 | Copilot/NOC/Grafana 503 UNKNOWN/no upstream; shared viewer token not actor+tenant. Only re-enable after Core server-derived exact-resource ACL and negative cross-tenant tests. Revert targeted #201 security commits, never all #202. |
| 3/5 Core read-only xref | #205 `692649cc9cb1bdbac85d8d5ee5f7ebcf33663089` → `main@27deb9b1a66faf27df8d69b137a63451f7649d80`; [Quality 41195560516](https://github.com/alimtalbi-ata/aiops/actions/runs/41195560516) FAILURE (Playwright/ubuntu26.04); Core/Postgres SUCCESS | `app/core/itsm_xref.py`, `app/core/main.py`, `db/migrations/009_itsm_xref_read.sql`, two test files. 12/12 mock HTTP, 17/17 read projection, 5/5 PostgreSQL HTTP. Port #211 runner stanza and rerun full exact-head browser. Reconcile migration `009_itsm_xref_read.sql` vs stacked `009_ai_decision_ledger.sql`; no wholesale port. Env-generated disposable CI credentials must be masked in logs. Revert own xref PR only. |
| 4/5 Policy/HITL/PG16 | #204 `4626f321e76d45fa5e8ab4ed83c5891fa486376f` stacked #194 `40d38705cf2bde3be6052340442c117a81908f65`; [Quality 41195151800](https://github.com/alimtalbi-ata/aiops/actions/runs/41195151800) SUCCESS 6/6 | PostgreSQL 16 disposable DR 32 tables PASS, outbox SQL 5/5. [DR 13040556044](https://github.com/alimtalbi-ata/aiops/actions/runs/41195151800/artifacts/13040556044), [outbox 13040546020](https://github.com/alimtalbi-ata/aiops/actions/runs/41195151800/artifacts/13040546020). Port only fenced worker/PG16 test contracts after migration/Policy version collision review; no real OIDC/SoD or in-flight restart proof. |
| 5/5 CI/release | #195 workflow-only fix `ea1a4aa1f4cea42cbe434f00d080eb0f76ce38a8` from #211 `9d3eb77c6de5f88e341103870fc06f0788f82d56` | Policy/static runner Ubuntu 24.04, Chromium E2E remains required; #195 exact-head CI pending observation after docs commits. Revert single workflow commit if broken. #206 repaired stacked manifest but #210 only source gate; neither qualifies main-based D3. |

**D0:** #201 GO_LIMITED, #204 isolated GO_LIMITED, #205 FAIL; **D1/D2:** NOT_QUALIFIED; **D3:** NO_GO (no semantic kit + 0/0/0 install/upgrade/rollback); **D4:** NOT_ATTESTED. #196 real Ollama benchmark remains 0 qualified repeats / Quality FAIL. `RELEASE_STABLE=NO_GO`.


### 2026-10-31 14:28 Europe/Paris — exact-head selective port and migration-ordinal fence

| Owner / source | Verified exact head and CI | Reuse decision / dependency |
| --- | --- | --- |
| 1/5 ACME #198 | `e909dbf2207fbb36efa36b27cef6734d43468e6d`; [Quality 41203462873](https://github.com/alimtalbi-ata/aiops/actions/runs/41203462873) 3/3 SUCCESS | Keep fixture-only synthetic replay, no fake Core Incident/Run, Evidence or GLPI. Port selected fixture blobs after D1 contract; rollback fixture commit only. |
| 2/5 Portal #201 | `920c6a38864257f1841a63030bf7a9074e7068f0` -> `main@27deb9b1a66faf27df8d69b137a63451f7649d80`; [Quality 41203864514](https://github.com/alimtalbi-ata/aiops/actions/runs/41203864514) 3/3 SUCCESS | Sole main-based integration candidate. Shared viewer bearer is not actor+tenant authority. Unsafe stacked GLPI/Copilot paths refused; UNKNOWN 503 before upstream. Await trusted Core exact-Run ACL. |
| 3/5 Core #205 | `1c16d8e74b60fabf69c9b8419f65be1ae245b814` -> same main; [Quality 41204020714](https://github.com/alimtalbi-ata/aiops/actions/runs/41204020714) 3/3 SUCCESS; 13/13 HTTP, 17/17 projection, 5/5 PG16 | Tenant-scoped ticket→Run xref contract only. Source SQL `db/migrations/009_itsm_xref_read.sql` **collides** with #194 `009_ai_decision_ledger.sql`. Port SQL under a new ordinal **provisionally 012 after 011**, with explicit history review, ordered disposable PG16 apply/rollback and exact-source tests. No direct copy of both 009. |
| 4/5 HITL #204 | `c915fd637149150d64e0b03061348f980e4b2560` -> #194 `40d38705cf2bde3be6052340442c117a81908f65`; [Quality 41203620344](https://github.com/alimtalbi-ata/aiops/actions/runs/41203620344) 6/6 SUCCESS plus V2.8/Offline/Historical SUCCESS | Disposable PG16 restore and CI-only Temporal server in-flight restart/REJECT sink replay observed, effects=0. Do not promote to real IncidentWorkflow/HITL identity or T2. Selective Worker/outbox source only after 009/010/011 migration and Policy/Core version reconciliation. |
| 5/5 release #210 | `809ba94a583c4dacb2c8296547fa97731cc0790f` -> #209 `9d515aee54a809bf06d81d63609b06d7b7a7e571`; [Quality 41205843043](https://github.com/alimtalbi-ata/aiops/actions/runs/41205843043) QUEUED at checkpoint | Two scoped commits add duplicate migration ordinal/malformed name rejection and three negative/positive tests to existing source kit guard. No package generator integration, no sandbox install/upgrade/rollback. Revert `809ba94a`, `cc9bd9e` if regression. |
| 5/5 AI #196 | `747f0df4b8bae0fa0265b6dc568558a6a9057ad1`, current stacked base `1fade3e5b3f07bdbd6b4fa8222bbb585012894ca`; [Quality 41083049858](https://github.com/alimtalbi-ata/aiops/actions/runs/41083049858) FAILURE | Zero qualified Ollama repeats. Provider-reported tokens only; quality/p50/p95/cost UNKNOWN; no benchmark PASS. |

**Integration order and gate:** one main-based candidate #201, no wholesale merge. Review source blobs, migrations, Core/Portal/Worker/Compose collisions and exact CI; require server-derived actor+tenant and two-tenant positive/negative readback before D1. D0 component-only GO_LIMITED; D1/D2 NOT_QUALIFIED; D3 NO_GO (30/68 stale manifest entries in last audited #204 kit, no clean install/upgrade/rollback); D4 NOT_ATTESTED. `RELEASE_STABLE=NO_GO`. No new P0 lane or LIVE action.


**#210 release-guard exact-head CI closeout (~14:35 Europe/Paris):** runner compatibility fix `91f997c55c1c2cbe2f4f83566884de2bbf6cc0fa` after [prior Quality 41205843043](https://github.com/alimtalbi-ata/aiops/actions/runs/41205843043) FAILURE on Ubuntu 26.04/Playwright, now [Quality 41205943265](https://github.com/alimtalbi-ata/aiops/actions/runs/41205943265) **SUCCESS 3/3** on exact HEAD. Logs: **28/28 kit guard** (three new ordinal tests) and **11/11 inventory**, mandatory ephemeral Chromium 6/6. This proves the duplicate-009 archive gate in the stacked #210 source only, **not** that #205 SQL was renumbered or applied, nor D3 installation/rollback. Artifact #13044134248 is a synthetic screenshot, checksum NOT_RECHECKED. Release remains NO_GO.


**2026-10-31 16:40 Paris — 5/5 selective reuse delta (not a release promotion).** [#213](https://github.com/alimtalbi-ata/aiops/pull/213) draft HEAD `97dcd8c31f12cdc310cf834f725b5d245d20d859`, base #201 `851b9300906d20e62d5942da9bc7a7d8df5d4bc7`: two-file selective port from #210 `91f997c55c1c2cbe2f4f83566884de2bbf6cc0fa`, migration ordinal collision/malformed-name rejection and distinct install/upgrade/rollback inventory. [Quality 41215590665](https://github.com/alimtalbi-ata/aiops/actions/runs/41215590665) SUCCESS 3/3, 22/22 release guard tests and 7/7 Chromium synthetic; no main merge or runtime qualification. #212 SQL migration 012 remains stacked on stale #205 base, not ported/applied. Latest #204 `b7813d7eac9b8cd7a4ad12562738b7e7e23b050a` [artifact 13047246797](https://github.com/alimtalbi-ata/aiops/actions/runs/41212999760/artifacts/13047246797): 412/412 SHA sidecar and 413/413 repack PASS but JSON 38/68 valid, 30/68 SHA/size mismatches, release 8.0.0 vs 2.1.0-core-rc1.4, checkout SHA distinct, upgrade/rollback missing and 0/0/0 operations exercised. D0 isolated GO_LIMITED, D1/D2 NOT_QUALIFIED, D3 NO_GO, D4 NOT_ATTESTED; `RELEASE_STABLE=NO_GO`. Revert #213 two commits if necessary; no schema/runtime effects.


**2026-10-31 17:32 Paris — changed-head reuse disposition.** Sole main-based candidate #201 \`0564618b1d58c61fe62764a7746796a06790bdd7\` Quality [41217620694](https://github.com/alimtalbi-ata/aiops/actions/runs/41217620694) SUCCESS 3/3, 7/7 Chromium synthetic; owner 1 #198 \`50ba4727aa450972b3757e611708b15945a2a7b5\` Quality [41217358026](https://github.com/alimtalbi-ata/aiops/actions/runs/41217358026) SUCCESS 3/3, 7 synthetic events but six Core/GLPI/Evidence/closure checkpoints NOT_EXECUTED; owner 3 #205 \`22b221f53cb2ec8240d4d2c2c3930345b8d3a75a\` Quality [41218370044](https://github.com/alimtalbi-ata/aiops/actions/runs/41218370044) SUCCESS 3/3 (16 mock HTTP, 17 projection, 8 disposable PG16) but no Portal exact-Run actor+tenant authorization or real GLPI readback; owner 4 #204 \`51616f53a3d07bdc6c109a2d6256787f0b3797e2\` Quality [41217253473](https://github.com/alimtalbi-ata/aiops/actions/runs/41217253473) SUCCESS 6/6, disposable PG16 DR and Temporal restart evidence only. #196 remains FAILURE and zero qualified Ollama repeats. #212 migration 012 is on stale #205 base; #213 source-member provenance fence is on stale #201 base, new HEAD \`53de1482cb7940b7c1621fbcb13d2fb5bed056ca\` **CI pending**; no green-by-proxy. New #204 [kit artifact 13048882307](https://github.com/alimtalbi-ata/aiops/actions/runs/41217253473/artifacts/13048882307) outer SHA256 \`df5fb76895e89a0d385d0ef3dbcf962fc65f3f8aef557748014e0cb722fb085f\`, sidecar 412/412 and repack 413/413 PASS, JSON only 38/68 valid, 30 wrong size/hash, release 8.0.0 vs 2.1.0-core-rc1.4, 0/0/0 install/upgrade/rollback. **Do not promote; D1/D2 NOT_QUALIFIED, D3 NO_GO, D4 NOT_ATTESTED.** Exact handoff and details in board and issue #186.


### 2026-10-31 18:40 Europe/Paris — exact-head source-provenance and owner handoff delta

- Main \`27deb9b1a66faf27df8d69b137a63451f7649d80\`; **sole main-based candidate #201** \`230feb52f64c4480f72a33e7e7c56bb12909b2ab\` [Quality 41223358637](https://github.com/alimtalbi-ata/aiops/actions/runs/41223358637) SUCCESS 3/3, fail-closed Portal run-session (503/no cookie without verified actor+tenant); **not positive ACL**.
- Owner 1 #198 \`1eab448a88ca15ee7992a03d0e8bdf5f16b949a2\` [Quality 41222633155](https://github.com/alimtalbi-ata/aiops/actions/runs/41222633155) SUCCESS 3/3: synthetic graph/events only, no Core authenticated Run. Owner 3 #205 \`ba97148275e26b936c8631f87839450a49cb8025\` [Quality 41223021867](https://github.com/alimtalbi-ata/aiops/actions/runs/41223021867) SUCCESS 3/3: signed tenant xref disposable, not GLPI real or Portal exact-Run ACL; its migration 009 still needs #212 rename 012 and combined PG16 application/rollback. Owner 4 #204 \`0790872d170ec3af511993edbb1f7861689455c3\` stacked on #194, [Quality 41222846472](https://github.com/alimtalbi-ata/aiops/actions/runs/41222846472) SUCCESS 6/6: PG16 DR/outbox and Temporal synthetic no-effect replay only. #196 \`747f0df4b8bae0fa0265b6dc568558a6a9057ad1\` Quality FAILURE, zero qualified Ollama repeats, cost UNKNOWN.
- **5/5 release owner #213:** historical base #201 \`851b9300906d20e62d5942da9bc7a7d8df5d4bc7\`, new HEAD \`12a65b5733ecc96108f3cb77f96a340185f71616\`. Ported #209 deterministic staged JSON generator (exact blob \`ab98546a1c8cd6d745c106b979f1a51e2900bfb7\`) plus strict source/manifest verifier, three new tests; [Quality 41225279446](https://github.com/alimtalbi-ata/aiops/actions/runs/41225279446) SUCCESS 3/3, **28/28** guard tests, Chromium 7/7. Source paths: \`deploy/refresh_release_inventory.py\`, \`tools/check_cumulative_release_kit.py\`, \`tests/test_cumulative_release_kit_gate.py\`. This is an **inventory/provenance guard only**, not an installable cumulative kit or D1/D2. #213 is stacked on stale #201; port selectively after owner 2 review, no mass merge.
- New changed #204 artifact [13049949421](https://github.com/alimtalbi-ata/aiops/actions/runs/41222846472/artifacts/13049949421) independently audited: ZIP SHA256 \`d4a154289add6b13892d546d9fd13d9632c49675fa9c8eeed39bf26a7fd67342\`; 412/412 sidecar, 413/413 repack PASS, but embedded JSON **38/68** size/hash, release JSON \`8.0.0\` vs text \`2.1.0-core-rc1.4\`, package checkout SHA differs from #204 HEAD, install/upgrade/rollback 0/0/0. **Do not reuse as release.** #206/#210 remain distinct, not implicitly integrated.
- Gates **D0 isolated GO_LIMITED, D1 combined NOT_QUALIFIED, D2 same-SHA browser/API NOT_QUALIFIED, D3 clean install/upgrade/rollback NO_GO, D4 sign-off NOT_ATTESTED**. \`RELEASE_STABLE=NO_GO\`; no merge, production, Debian, GLPI write, executor or LIVE.

### 2026-10-31 19:32 Paris — changed-source reuse and source authority

- **#201 is the only main-based integration candidate:** `4e1dfaf03569a736d59d1b63816a37bc0a604ee3` (base main `27deb9b1a66faf27df8d69b137a63451f7649d80`), [Quality 41227486309](https://github.com/alimtalbi-ata/aiops/actions/runs/41227486309) SUCCESS 3/3. Owner 2 newly fenced `GET /api/portal/components` before configured link disclosure (503 UNKNOWN with bearer-only; 401/403 unauthenticated), plus bootstrap/navigation client bearer-only 200 rejection. Reuse this **fail-closed** contract; **do not** interpret it as positive actor+tenant authorization. Real Core exact-Run/Portal positive ACL and same-SHA browser/API D2 remain NOT_QUALIFIED.
- **Owner 1 #198:** `878e190cdcc6dc219ce3910076b0016b1963e17e` main-based, [Quality 41227577051](https://github.com/alimtalbi-ata/aiops/actions/runs/41227577051) SUCCESS 3/3; [artifact 13052471384](https://github.com/alimtalbi-ata/aiops/actions/runs/41227577051/artifacts/13052471384) is seven-event offline ACME graph-bound replay, not Core/GLPI/Evidence proof. Reuse fixture IDs and source edges only.
- **Owner 3 #205:** `e907199f169fa65e2717ba11bcd4b790579302b3` main-based, [Quality 41227319260](https://github.com/alimtalbi-ata/aiops/actions/runs/41227319260) SUCCESS 3/3; signed tenant-scoped xref read contract, PostgreSQL 16 disposable 9/9, no production IdP/GLPI readback. `db/migrations/009_itsm_xref_read.sql` blob `9408dcf9d92d5bfbdb75968a5a0b0a55f2985457` must be ported under **012** only after reviewing #212 `0c07090bed333e90aab1248ffcfc51e10d3f3c67`; combined 009/010/011/012 + restore/rollback NOT_RUN. No wholesale merge.
- **Owner 4 #204:** `241977c7802f5647a5f6eb6072bf1dcf1c508521` stacked on #194 `40d38705cf2bde3be6052340442c117a81908f65`; [Quality 41226950941](https://github.com/alimtalbi-ata/aiops/actions/runs/41226950941) SUCCESS 6/6 plus V2.8/Offline/Historical; PG16 outbox 10/10, DR 32 tables, synthetic Temporal/Worker restart and zero effects. Reuse **strict revision fence and tests** only after dependency review. Human OIDC/MFA and true lost-network-ACK NOT_ATTESTED.
- **5/5 release #213:** `12a65b5733ecc96108f3cb77f96a340185f71616` stacked on historical #201 `851b9300906d20e62d5942da9bc7a7d8df5d4bc7`, [Quality 41225279446](https://github.com/alimtalbi-ata/aiops/actions/runs/41225279446) SUCCESS 3/3, 28/28 inventory tests. Selectively reuse `deploy/refresh_release_inventory.py`, `tools/check_cumulative_release_kit.py`, `tests/test_cumulative_release_kit_gate.py`; no cumulative installation/rollback. **New #204 kit artifact [13052770018](https://github.com/alimtalbi-ata/aiops/actions/runs/41226950941/artifacts/13052770018) independently audited:** ZIP SHA256 `d81b1a1ce9bb55072fb6c01a19d237f61a7916d475ed6d034384af8c979d75df`, sidecar 412/412, in-memory repack 413/413, embedded JSON **38/68** correct, **30/68** bad; release 8.0.0 vs 2.1.0-core-rc1.4, package source SHA not #204 HEAD, install/upgrade/rollback 0/0/0. **Do not promote or copy kit as qualified.**
- **Benchmark #196:** `747f0df4b8bae0fa0265b6dc568558a6a9057ad1`, [Quality 41083049858](https://github.com/alimtalbi-ata/aiops/actions/runs/41083049858) FAILURE; Qwen3 1.7B and 4B evaluator each 3/3 exits 1, no scored real-model repeat. Provider tokens/latency/cost UNKNOWN. Deterministic provider baseline must remain separate.
- **Decision:** D0 isolated GO_LIMITED; D1/D2 NOT_QUALIFIED; D3 NO_GO; D4 NOT_ATTESTED; `RELEASE_STABLE=NO_GO`. Three P0 tracks only: Core/Portal positive actor+tenant, combined migration/D1-D2, cumulative kit/D3. Revert isolated branch commits or discard disposable DB; no main push, merge, Debian, GLPI write, executor or LIVE.

### 2026-10-31 20:25 Paris — changed-head reuse decision (one main-based candidate)

- **Single integration authority:** #201 base main 27deb9b1a66faf27df8d69b137a63451f7649d80, HEAD 98aec33fc9e0576c9944464aa1585fe9844cd6a0, [Quality 41232577017](https://github.com/alimtalbi-ata/aiops/actions/runs/41232577017) SUCCESS 3/3. Reuse Portal fail-closed run-session and navigation guards only; positive actor+tenant exact-Run ACL is absent. Do not confuse client forged-2xx rejection with server authorization.
- **1/5 ACME:** #198 HEAD 527acdfd4dfd6287b62fb81d95a787c123e20be2, base main, [Quality 41232090257](https://github.com/alimtalbi-ata/aiops/actions/runs/41232090257) SUCCESS 3/3. Reuse deterministic seven-event synthetic fixture and new checkout/symlink/hardlink export fence in tools/generate_acme_incidents.py; no Core/GLPI/Evidence execution.
- **3/5 Core:** #205 HEAD 113753eb3b6ebdb1ce017064c1afd403f89ed726, base main, [Quality 41232723723](https://github.com/alimtalbi-ata/aiops/actions/runs/41232723723) SUCCESS 3/3, disposable PG16 xref 9/9. Reuse app/core/itsm_xref.py and app/shared/core_itsm_xref_read.py **selectively**, not the conflicting 009 migration. The same SQL blob 9408dcf9d92d5bfbdb75968a5a0b0a55f2985457 is at db/migrations/012_itsm_xref_read.sql in #212, stacked on stale Core base; port only after owner 3 approval and ordered PG16 integration. Service digest ACL is not IdP or Portal exact-Run positive auth.
- **4/5 HITL:** #204 HEAD a69c45939290a6b1abf5936e39ffab19d9046e8e, base #194 40d38705cf2bde3be6052340442c117a81908f65, [Quality 41232288005](https://github.com/alimtalbi-ata/aiops/actions/runs/41232288005) SUCCESS 6/6; reuse strict revision/lease fencing and tests/test_hitl_pg16_outbox_integration.py **12/12 PG16**, DR 32 tables with pg_restore 16.15, synthetic Temporal/Worker restart zero effects. New lost-ACK-after-commit is a **disposable simulated failure**, not observed network packet loss or human identity proof.
- **5/5 release:** #213 HEAD 12a65b5733ecc96108f3cb77f96a340185f71616 stacked on historical #201 base 851b9300906d20e62d5942da9bc7a7d8df5d4bc7, [Quality 41225279446](https://github.com/alimtalbi-ata/aiops/actions/runs/41225279446) SUCCESS 3/3, guard 28/28. Reuse only source-provenance/inventory checks after selective port; no cumulative operation receipts. #204 new kit [13053983467](https://github.com/alimtalbi-ata/aiops/actions/runs/41232288005/artifacts/13053983467) SHA256 37629972b04b3ab01710c6a2ff6b72e1739131a3009ccb091ec0336307359a88 has sidecar 412/412 and repack 413/413, but **30/68 embedded JSON invalid**, release 8.0.0 vs 2.1.0-core-rc1.4, packaging SHA != source HEAD and install/upgrade/rollback 0/0/0. Do not reuse kit. #196 HEAD 747f0df4b8bae0fa0265b6dc568558a6a9057ad1, Quality FAILURE, 0 qualified real-model repeats, provider tokens/cost UNKNOWN.
- **No whole-branch merge:** current #201 tree has no 009_ai/010_evidence/011_hitl/012_xref migration files (exact-ref lookups 404). Combined PostgreSQL 16 migration/rollback and same-SHA Core/Portal/HITL/ACME D1/D2 NOT_QUALIFIED. D3 NO_GO, D4 NOT_ATTESTED; RELEASE_STABLE=NO_GO. Revert isolated branch commits/discard disposable DB only; no Debian/GLPI write/LIVE.


## 6. Architect branch audit — 2026-10-31 21:50 Europe/Paris

- #221 daily GitHub-hosted quality schedule was merged into `main` at `77a9d415464c67190c428d8c1559cf22db149d0e`; the post-merge quality workflow was running as #41240948760 at snapshot time.
- #219 reporter v3 and #220 clean-deploy source gate remain stacked on the Debian qualification branch; exact-head CI must be refreshed after any base change. #220 now fails closed when GitHub reports `main.protected=false`.
- #222 freshness observer remains Draft until a real schema-v3 `latest.json` is published to `ops/debian-runtime-reports`.
- #188 and #189 are Draft: #188's Docker-exec/self-hosted runner design is incompatible with the current least-privilege boundary; #189 duplicates the daily schedule merged by #221.
- Exact branch comparisons against main: #195 = 218 commits ahead (20 net files); #201 = 112 ahead (62 files); #202 = 43 ahead (18 files); #198 = 47 ahead (8 files); #205 = 50 ahead (10 files); #204 = 900 ahead / 43 behind (300 files). These are review/selection signals, not automatic merge recommendations. Do not merge these histories wholesale.
- The selected approach is a clean main-based integration branch with selective content/commit promotion, focused PRs and new exact-head CI. #195 remains the architecture source; its net files are being selectively ported rather than importing its 218-commit history.
- GitHub API reports `main.protected=false`; manual exact-head, diff, review and rollback gates remain mandatory.
\n\n## 7. Current integration state — 2026-10-31 22:05 Europe/Paris\n\n- Current main: `2c87bc931b170208b7c2f253218d0f939381355a`. #221 and #224 merged, each followed by exact-main quality 3/3 SUCCESS (#41240948760, #41241604652). #195 closed as superseded after selective port.\n- #198 ACME: HEAD `d3596cb0f42ea96a6ba8c7d9693372e3ffc44eff`, reported 3/3 CI but 3 newly added adversarial tests were not invoked (0/3); not merge-ready.\n- #223 Portal stale-response fence: HEAD `9d3ee6fedd23171e00bffa141b839bf2031aa964`, 3/3 CI; stacked on #201, not a direct main candidate.\n- #205 Core xref: HEAD `537b75dd4b10fb56791d8e59095fcdea0dd62e0d`, no exact-head CI; new CMDB entity-provenance defect reproduced.\n- #204 Policy/HITL: HEAD `5285aec4359a8132cb6c5801dc8d3a18118930fc`, quality plus three qualification workflows green; remains Draft on #194.\n- #201 candidate: 112 commits ahead of old main and behind current main; do not merge as a whole. #202 is main-based but its head/CI must be refreshed after main advancement.\n- GitHub reports main unprotected; require manual gates. Debian cron/latest.json remain NOT_ATTESTED.\n

## 2026-10-31 23:48 Europe/Paris — selective reuse and conflicts

- Main `ae7c3e5102b99a66bd7806d602146f1309a9749d`, post-merge #230 [Quality #41242870529](https://github.com/alimtalbi-ata/aiops/actions/runs/41242870529) 3/3 SUCCESS. Single candidate [#234](https://github.com/alimtalbi-ata/aiops/pull/234), initial ACME port commit `21a0c4d544cb58b4bebc9fc47a1961413f456bff`; source #231 `4f0edb91e4d62e9ef0c8f29243d85e586fc17a49`, 67/67 tests and Quality #41246212856 3/3. New candidate CI is separate; do not transfer source status.
- #230 Portal fail-closed merged main; #232 `3961ce2f85f3c6e1b7890ca5cebbdf09ac368db4` is Draft and OIDC RSA fixture was 1 SKIP (Quality #41247272385 3/3). No positive actor+tenant authorization.
- #233 Core `4a22adb19f4d5f1de4a03898cd0908058222d256` Draft, Quality #41248332891 3/3, disposable PG16 009→010→011→012 test-fixture chain 1/1; 009/010/011 are **not installed migration files**, GLPI ownership proof remains synthetic. Do not port 012 alone.
- #204 HITL `5285aec4359a8132cb6c5801dc8d3a18118930fc` stacked on #194; #228 `cd703c7d92782eb3309aaec70931efda465aed0d` stacked on historical #201. No whole merge. #206/#210 kits remain semantically NO_GO, #196 benchmark FAIL/cost UNKNOWN.
- Exclusive file ownership: Portal `app/portal/**`; Core `app/core/**` and migration ordinals; Policy/Worker/HITL owner 4; ACME fixtures/generator owner 1. Architect alone reconciles shared `.github/workflows/quality.yml` changed by both #231 and #233. P0 WIP max three (ACL, migrations/xref, HITL PG16/DR). Rollback by focused candidate revert; no main reset, persistent DB or LIVE.


## 2026-11-01 00:41 Europe/Paris — selective source provenance / conflicts resolved

- Candidate #234 main-base `ae7c3e5102b99a66bd7806d602146f1309a9749d`, code checkpoint `f69b0f7e41ac3d199c8236b09dd8b301b2607176`. #201/#194 remain historical source-only; no wholesale merge. Source exact-head CIs: #236 [41250583981](https://github.com/alimtalbi-ata/aiops/actions/runs/41250583981) 3/3 (trusted-origin ACME), #237 [41251913634](https://github.com/alimtalbi-ata/aiops/actions/runs/41251913634) 3/3 (RSA 12/12, OIDC session 8/8), #233 [41248332891](https://github.com/alimtalbi-ata/aiops/actions/runs/41248332891) 3/3 (Core xref), #238 [41252130273](https://github.com/alimtalbi-ata/aiops/actions/runs/41252130273) 3/3 **but installed PG16 test 0/1 executed on source**, #239 [41252996008](https://github.com/alimtalbi-ata/aiops/actions/runs/41252996008) 3/3 (Policy 26/26 and HTTP 9/9).
- Resolved migration ordinal conflict: installed 009 AI / 010 Evidence / 011 HITL / 012 xref; historical xref 009 excluded. Four SQL Git blobs pinned and reviewed in Core #238. Architect reconciled `.github/workflows/quality.yml` without overwriting ACME tests, adds real installed-chain PG16 idempotence/transactional rollback step, and applies ordered SQL to ephemeral Core DB. Exact integrated [Quality #41253703233](https://github.com/alimtalbi-ata/aiops/actions/runs/41253703233) PENDING at checkpoint.
- No source green-by-proxy: positive Portal/Core actor+tenant/Run/GLPI readback absent; no real GLPI or CMDB Twin authority; Policy outbox/Temporal/DR not ported; kit #206/#210/#213 semantic D3 NO_GO, benchmark #196 FAIL/cost UNKNOWN. No claim of D1/D2, install/upgrade/rollback or runtime. Revert selective commits in reverse order; no persistent migration/data downgrade validated.


## 2026-11-01 01:48 CET — reviewed scoped reuse (source-only ≠ integrated qualification)

| Owner | Source PR exact HEAD / source CI | Ported paths / candidate commit | Limit |
|---|---|---|---|
| 1 ACME/Twin | #240 `809d31bb7b3fe1e3d214e75a36ac2bbc20dd0d82`, [Quality 41254705977](https://github.com/alimtalbi-ata/aiops/actions/runs/41254705977) 3/3; 78/78 ACME | `tools/generate_acme_incidents.py`, catalog test, Twin story doc; `ef47f05ffcef5a4c1fe5c8d579463723ca26d197` | Synthetic pinned graph; no real SLA/OLA |
| 2 Portal | #241 `1d5b6a4fb02e970bde46bceff4212e120f336f89`, [Quality 41255492856](https://github.com/alimtalbi-ata/aiops/actions/runs/41255492856) 3/3; ACL negative 9/9 | Portal Run API/HTML, ACL consumer, OIDC contract, tests/bridge; `e73ad9577fe51909c44e41e7ad736303b69e6b03` | Positive actor authorization still absent |
| 3 Core | #242 `00dd0443d4d36d7aeb36bb77490777ac6ef5785d`, [Quality 41256616355](https://github.com/alimtalbi-ata/aiops/actions/runs/41256616355) 3/3; HTTP 21/21, PG16 10/10 | Core xref, GLPI gate ADR, API/PG tests; `dfc4f122b4dae706e25520d739096ffb3adb35ea` | GLPI HTTP mocked, actor delegation missing |
| 4 HITL | #243 `e4e4c7c09b96d911184f80dbb6249cd191fa8390`, [Quality 41257528298](https://github.com/alimtalbi-ata/aiops/actions/runs/41257528298) 3/3 + [HITL 41257528325](https://github.com/alimtalbi-ata/aiops/actions/runs/41257528325) 1/1; SQL 5/5 | Dedicated workflow (PR target `main`), SQL/DR test, qualification doc; `a44d6aed751b2e4c4cf8ec6e5b00fde29cd1cec3` | No Core claim/ACK, Worker/Temporal runtime |

Candidate #234 code checkpoint `a44d6aed751b2e4c4cf8ec6e5b00fde29cd1cec3` main base `ae7c3e5102b99a66bd7806d602146f1309a9749d`. Source commits and CI do not qualify new exact candidate HEAD. #201/#194/#204 are historical sources, not mergeable release batches. No collision of owned paths in these four ports. Revert one focused candidate commit per owner, reverse dependency order; no main reset.


### Architect cycle — 2026-11-01 02:44 CET — selective integration, NO_GO

SOURCE_REVIEWED: DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; sole Draft #234 from that base, candidate product checkpoint `7fe177ea165e063a64a80acd22bf4e1a8338b355` (final documentation commit and exact-head CI pending). No whole historical #201/#194/#204 merge. Owner source Drafts all based on prior candidate `d5227f5c3981a53dd2a42d5384dce798cfaf0d33`:

| Owner / source | Exact source HEAD; source CI | Architect selective port / paths | Gate and dependency |
|---|---|---|---|
| Core P0 #246 | `a69e68523b6d690dcb8edbaf8bac57b2e8b8cca0`; [Quality 41260773041](https://github.com/alimtalbi-ata/aiops/actions/runs/41260773041) 3/3; Core 30/30, PG16 installed 3/3 | `5d5f776272f2297f0a2e87cadb1f81c78851422f`; actor_resource_authz, itsm_xref router, Core tests/ADR (5 paths) | IdP introspection mocked; GLPI native human rights, nonce replay ledger and positive ALLOW **not qualified** |
| Portal P0 #245 | `78d0471328268f842e70f5ee5d898cc013b35206`; [Quality 41260115750](https://github.com/alimtalbi-ata/aiops/actions/runs/41260115750) 3/3; Portal 12/12 | `4bcf409c3f2aad27ccaad20ea3cf68dee15b557f`; ACL consumer, tests, OIDC/Core contract (3 paths) | ALLOW-shaped JSON is **not authority**; positive_core_contract_matches remains false, Run 503/UNKNOWN, no upstream |
| Policy/HITL P0 #247 | `dc005302819912f90f32dfc0584ff478fcf756f5`; [Quality 41261752806](https://github.com/alimtalbi-ata/aiops/actions/runs/41261752806) 3/3; [Temporal+PG16 41261752843](https://github.com/alimtalbi-ata/aiops/actions/runs/41261752843) 2/2, Worker 10/10, SQL 5/5 | `b7ab2ab1a5280e98b15805b2d6c7fa9bcac1598e`; Worker pure REJECT adapter, tests, doc, dedicated workflow (4 paths), workflow PR base retargeted to main | No Core claim/ACK HTTP, runtime poller, APPROVE, executor or LIVE; only disposable Temporal Worker restart, no Temporal server restart |
| ACME/Twin P1 #244 | `1c9b6f50c92d43fa893f08bcf0da8964873db4ae`; [Quality 41259232141](https://github.com/alimtalbi-ata/aiops/actions/runs/41259232141) 3/3; catalog 48/48, ACME targeted 85/85 | `7fe177ea165e063a64a80acd22bf4e1a8338b355`; synthetic catalog adversarial tests and provenance doc (2 paths) | Seed 20261018, 18 CI/17 edges, candidate blast radius only; owner/SLA/OLA/Change/real maintenance/observed impact UNKNOWN |

**Decision:** four disjoint, source-reviewed ports to one main-based candidate; all source CI are exact source HEAD, but **do not transfer green by proxy** to the new candidate. New D0 Quality + HITL dedicated runs must check final source HEAD; D1 combined disposable ITIL Event→Incident→Twin→Analyst/Critic→Evidence→HITL→SIMULATE→verification→resolution/reopen NOT_QUALIFIED; D2 browser/API same SHA NOT_QUALIFIED; D3 cumulative kit install/upgrade/rollback NO_GO; D4 client sign-off NOT_ATTESTED. `#196=FAIL`, provider-reported tokens only, cost UNKNOWN without versioned pricing. No real GLPI/IdP runtime, host or LIVE effects.

**Next owner contracts (WIP P0=3):** Core owns source-authenticated GLPI native actor permission and durable nonce/revocation, plus Core-fenced claim/ACK interface; Portal owns an authenticated transport and no-ALLOW-until-qualified exact Run binding, without overlapping Core files; Policy owns a disposable integration test for Core claim/ACK and Worker/Temporal REJECT with zero effects, without wiring poller; ACME owns independently sourced Twin governance facts and a synthetic end-to-end fixture, never invented SLA/OLA. Architect owns shared CI, migrations and candidate promotion. **Rollback:** revert these four focused commits in reverse order ACME→HITL→Portal→Core, remove disposable databases/artifacts; no persistent-data downgrade claimed and no main reset. `RELEASE_STABLE=NO_GO`.

Reuse decision: source #244/#245/#246/#247 are focused source branches; copy exact scoped file blobs and adapt only the dedicated Worker CI target to main. They remain Draft, not wholesale merge candidates.


## 2026-11-01 03:48 CET reuse register delta

Architect selectively ported source PR #250 Core (6 paths), #251 Worker (4), #249 Portal (3), #248 ACME (4) into sole Draft #234. No wholesale history or duplicated migrations. Exact source and candidate commit references, CI, scope, dependency, rollback and four-plane automation status: `docs/release/AIOPS2-INTEGRATION-CYCLE-2026-11-01-0348.md`. Source CI cannot qualify final candidate. Core native GLPI actor rights and real PG16 claim/ACK unqualified; Portal dispatch=false, Worker mock Core wire, ACME synthetic UNKNOWN governance. D1/D2 NOT_QUALIFIED, D3 NO_GO, D4 NOT_ATTESTED; #196 FAIL, cost UNKNOWN. RELEASE_STABLE=NO_GO.

## Architect integration checkpoint — 2026-11-01 04:50 CET (Europe/Paris)

Decision: sole DEV Draft candidate #234, RELEASE_STABLE=NO_GO. No main merge/push, real GLPI write, Debian/SSH, LIVE or executor. Main SHA ae7c3e5102b99a66bd7806d602146f1309a9749d. Candidate after product port 7321d140ae6658c7e7853422f3af7528c59d97b0 (29 ahead / 0 behind, 81 paths).

Selective SOURCE_REVIEWED port, not source-branch merge: ACME #252 HEAD 6914360b032a5a9a36e5470da395a96bd29afbcc (4 paths, 15-stage ITIL plan NOT_EXECUTED); Portal #253 HEAD 8751db0a2459d29fd3cd3d4ff562289dbed5301d (3 paths, Core UNKNOWN wire, no ALLOW); Core #254 HEAD db3ea1185eb3a991dade183ed7c24587d376317a (3 paths, PG16 populated REJECT tests, synthetic owner HMAC); HITL #255 HEAD c8f135d458b4527210431a5ea5f344495e854616 (3 paths, ASGI HTTP/PG16/Temporal test Worker, REJECT only). Thirteen disjoint owner paths selected by pinned blob SHA. Source CI successful on their own heads; candidate new-head CI PENDING.

Contract order: installed 001/004/009 AI/010 Evidence/011 HITL/012 xref -> Core REJECT claim/ACK -> Worker Temporal test Worker -> Portal negative wire -> ACME synthetic planned vertical. Actor+tenant ALLOW blocked on native GLPI User/Profile/Entity rights, independent OIDC-to-GLPI mapping, nonce/revocation and signed-response contract. Fifteen planned steps are NOT_EXECUTED, no runtime E2E claim.

WIP <=3 P0: Portal ACL (Portal paths); Core GLPI rights, durable replay and migrations (Core paths); Policy/HITL Core-Worker REJECT (Worker paths). ACME P1 fixtures/tools. Architect owns shared workflows, release docs, candidate ref. No overlapping owner paths.

Gates: D0 candidate exact-head CI NOT_VERIFIED after port; D1 combined business integration NOT_QUALIFIED; D2 same-SHA browser/API lifecycle NOT_QUALIFIED; D3 semantic kit and install/upgrade/rollback NO_GO; D4 client signoff NOT_ATTESTED. SOURCE_REVIEWED != CI_PASS != INTEGRATION_PASS != RUNTIME_OBSERVED. #196 FAIL; provider-reported tokens only, cost UNKNOWN.

Rollback: revert candidate-only port commit 7321d140ae6658c7e7853422f3af7528c59d97b0 on a fresh branch, rerun exact-head CI. Never rewrite main. Evidence in source PRs #252/#253/#254/#255 and issue #186.


## 2026-11-01 05:48 Europe/Paris — source reuse delta (no duplicate implementation)

| Owner | Reused focused source | Exact source CI | Selective candidate port | Unqualified dependency |
|---|---|---|---|---|
| ACME | #256 `39eb0a0ad863046d73b531e3fc595766b2cb8231`, 4 paths | Quality #41271570987 3/3 | Synthetic seven-event correlation + reverse-Twin candidate; no runtime IDs | Core authenticated tenant readback, real Incident/Evidence |
| Portal | #257 `78c039c8186ee9725e1d9264d81725cabfb72cab`, 3 paths | Quality #41271935539 3/3, 22/22 targeted | Current Core UNKNOWN vs signed-v1 offline parity, still 503 | Native GLPI human rights, durable nonce, Core response signer |
| Core | #258 `bcbafb9ee03410b78487bfb9ddb04b2b59ad3925`, 9 paths | Quality #41272794505 3/3; PG16 ledger 3/3 | Native rights preflight (negative-only), proposed migration 013 | Independent real IdP/GLPI; full migration + backup/downgrade |
| Policy | #259 `caab0842911f44d59c274cabaf2a667b4d582094`, 3 paths | Quality #41274206608 3/3, combined #41274206599 1/1 | Disposable TCP gateway-close-after-ACK test, Worker restart REJECT | Independently deployed Core TCP and Temporal server restart |

All 19 paths are disjoint across owners and were copied as exact Git blobs in #234 integration commit `74fe37e67f540e1b1ebc282dc0e8f26f17a8a25d`. The four source PRs remain Draft; no full-history merge, no second CMDB/Incident Store. Integrated D0 **PENDING** until workflows run on the final docs HEAD. Keep #201 historical source only, #234 sole candidate, main untouched. Kit #206/#210 D3 NO-GO and Analyst/Critic #196 FAIL/cost UNKNOWN without provider-reported tokens and versioned tariffs.


## Architect cycle — 2026-11-01 06:45 CET (Europe/Paris)

**Decision:** sole Draft #234, DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; no main promotion. Product integration commit `44f98ab51a21546efa837bb6571afa08b1e7476f` selectively imports 18 disjoint source blobs from four Draft PRs based on candidate `e8328b9f65fcf01addbe1c59b595466f8e48af15`. All four owner source Quality runs 3/3 SUCCESS, plus Policy combined 1/1, **but new integrated HEAD D0 PENDING until its own CI**. SOURCE_REVIEWED is not CI_PASS, INTEGRATION_PASS or RUNTIME_OBSERVED. `RELEASE_STABLE=NO_GO`.

| Owner / WIP | Source HEAD and exact source CI | Port / contract | Blocker / next |
|---|---|---|---|
| 1 ACME/Twin P1 | #260 `86c024b3174fdafbd6f9caab02c994494f89cd09`, Quality [41275176879](https://github.com/alimtalbi-ata/aiops/actions/runs/41275176879) 3/3; 117/117 targeted | 3 paths, local synthetic test-partition ingestion/dedup, seven events, pinned SAN→Payments reverse graph, seed 20261018 | Partition labels NOT tenants; no Core Incident/Run/Evidence receipts. Next: tenant-authenticated disposable ingestion adapter contract; preserve no-effect |
| 2 Portal P0 | #261 `195dce15e297d3899e1468ceeea189a54c649e0d`, Quality [41275956099](https://github.com/alimtalbi-ata/aiops/actions/runs/41275956099) 3/3; Chromium 12/12 | 3 paths, disposable TLS Chromium/API negative ACL 401/503, revoked/replay/cross-tenant, no Core fetch | Native GLPI actor+tenant ALLOW absent. Next: exact actor-resource delegated rights evidence and non-leaking negative UX, no positive read |
| 3 Core P0 | #262 `a3b476daca767d753c96657feaa5c865d1721a7c`, Quality [41276788868](https://github.com/alimtalbi-ata/aiops/actions/runs/41276788868) 3/3; installed 009→013 PG16 13/13 | 9 paths, native GLPI rights preflight and durable 013 issuer/JTI/nonce replay consume; UNKNOWN-only | No independently observed IdP/GLPI native actor rights; populated COPY restore is not full archive/upgrade/downgrade. Next: independent synthetic-service contract and full 009→013 sandbox restore without deleting audit |
| 4 Policy/HITL P0 | #263 `3ce13e2674ed18fce66a86c19004bcd0b9a61c2b`, Quality [41277445682](https://github.com/alimtalbi-ata/aiops/actions/runs/41277445682) 3/3 + combined [41277445680](https://github.com/alimtalbi-ata/aiops/actions/runs/41277445680) 1/1; combined 5/5 + DR 5/5 | 3 paths, independent disposable Core TCP process, persistent Temporal dev server SQLite restart, Worker REJECT, gateway-close-after-ACK | Not actual packet loss, not real GLPI or IncidentWorkflow. Next: exact tenant/lease fencing under restart with zero effects |

**Order/dependencies:** IdP delegation + native GLPI User/Profile/Entity/Ticket rights → Core exact tenant/Run/Incident/xref and durable 013 consume → Portal signed actor-resource response (currently always UNKNOWN) → Policy REJECT notification only → ACME synthetic Event/Incident projection. Migration order `001→004→009 AI→010 Evidence→011 HITL→012 xref→013 actor replay`; preserve immutable audit. No parallel owner edits to shared Quality, migration ordinals, candidate branch or release docs. Architect owns integration and CI.

**Gates:** D0 integrated exact-head CI PENDING after port; D1 partial disposable REJECT only, full ITIL business NOT_QUALIFIED; D2 same-SHA full browser/API ITIL NOT_QUALIFIED (negative Portal test alone not sufficient); D3 cumulative kit semantic integrity and clean install/upgrade/rollback NO_GO; D4 client sign-off NOT_ATTESTED. #196 benchmark FAIL, provider-reported tokens only, cost UNKNOWN. No GLPI real write, host/SSH/sudo, executor, LIVE or production. **Rollback:** revert focused integration commit `44f98ab51a21546efa837bb6571afa08b1e7476f` on candidate with a new commit, rerun exact-head CI; retain all 013 audit tables/rows outside disposable; never force-push/reset main.


## Architect integration checkpoint — 2026-11-01 07:44 CET (Europe/Paris)

**Sole candidate:** Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234), branch `integration/enterprise-slice-main-20261031-2230`; refreshed main `ae7c3e5102b99a66bd7806d602146f1309a9749d` (compare identical at read); pre-port candidate `f93a55cebdef017d979e43bba47f08126963048d`. Architect copied **14 reviewed, non-overlapping source Git blobs** into focused candidate commit `ba3e3f39e1097599b9a9a5a91831a0f62cf4a58a` without merging source histories. **D0 exact integrated HEAD CI PENDING until new HEAD logs checked.** No main merge.

| Owner | Source branch/HEAD → Draft PR | Source exact-head CI | Delta and next task |
|---|---|---|---|
| 1/5 ACME/Twin P1 | `feat/acme-itil-replay-verifier-20261101-0700` `3c52fc8688a73144f0ad1544dec28c3e199bbd7f` → [#264](https://github.com/alimtalbi-ata/aiops/pull/264), base `f93a55ce` | [Quality 41279214271](https://github.com/alimtalbi-ata/aiops/actions/runs/41279214271) 3/3; 127/127 targeted | 3 paths: 15-stage offline synthetic verifier + 10 adversarial tests; next: fixture-to-Core readback adapter **only when** real source receipts exist; otherwise emit NOT_EXECUTED |
| 2/5 Portal P0 | `feat/portal-core-tcp-unknown-20261101-0714` `e64ab649f5dba5b3135d4723afdc1da9b0ec4a29` → [#265](https://github.com/alimtalbi-ata/aiops/pull/265), base `f93a55ce` | [Quality 41280139388](https://github.com/alimtalbi-ata/aiops/actions/runs/41280139388) 3/3; Chromium 14/14, consumer 22/22 | 3 paths: independent test-only HTTPS Core UNKNOWN and deny parity; next: server-side fail-closed Core authorization consumer integration, no synthetic ALLOW |
| 3/5 Core P0 | `feat/core-actor-disposable-sources-pg16-archive-20261101-0720` `b3f8a229a2f60d9a72bfaaac2ec225d8bc7cd746` → [#266](https://github.com/alimtalbi-ata/aiops/pull/266), base `f93a55ce` | [Quality 41281162897](https://github.com/alimtalbi-ata/aiops/actions/runs/41281162897) 3/3; Core 75/75, installed PG16 14/14 | 5 paths: independent loopback IdP/map/GLPI mock, PG16 custom dump/restore populated 009→013; next: same-major PG16 client and independently TLS-validated native authority, audit preservation |
| 4/5 Policy/HITL P0 | `feat/p0-worker-multiworker-lease-temporal-restart-20261101-0734` `16d1f3c4236b4a0bbdf6bda22c09ad04fd5bda81` → [#267](https://github.com/alimtalbi-ata/aiops/pull/267), base `f93a55ce` | [Quality 41281513857](https://github.com/alimtalbi-ata/aiops/actions/runs/41281513857) 3/3; [combined 41281513844](https://github.com/alimtalbi-ata/aiops/actions/runs/41281513844) 1/1, 6/6 | 3 paths: two Worker lease race + Temporal server restart, REJECT only; next: adversarial stale lease/ACK replay across separate worker processes, no effect |

**Architecture/reuse review:** no new schema migration or GLPI writer; Core actor stays UNKNOWN despite successful mocked source preflight, Portal does not grant a read on 200 UNKNOWN, Policy never emits APPROVE, ACME projections are not observed ITIL receipts. PG16 restore uses PG18 client generated SQL with only `SET transaction_timeout = 0;` removed; same-major PG16-client restore remains unqualified. Worker gateway-close is injected, not physical packet loss. 013 JTI/nonce/revocation audit is immutable. All four source PRs are Draft, stacked on #234, retained for provenance; no #201/#194 wholesale merge, no automatic green→release inference. Source CI qualification does **not** transfer to candidate.

**Gates:** SOURCE_REVIEWED focused diffs and filenames; source CI_PASS as linked; candidate INTEGRATION_PASS **PENDING exact HEAD**; RUNTIME_OBSERVED only disposable CI after qualification; full ACME Event→Incident→Twin→Analyst/Critic→Evidence→Policy/HITL→SIMULATE→verify→resolution/reopen NOT_VERIFIED; D3 cumulative kit NO_GO; D4 client sign-off NOT_ATTESTED; #196 benchmark FAIL, cost UNKNOWN. **RELEASE_STABLE=NO_GO.** Rollback: revert focused port `ba3e3f39e1097599b9a9a5a91831a0f62cf4a58a` with a new commit, preserve 013 audit data, rerun exact-head CI; no reset/force-push/main mutation. No host/SSH/sudo, real GLPI write, LIVE executor or deployed runtime claims.


## Architect selective integration checkpoint — 2026-11-01 08:48 CET (Europe/Paris)

**Sole candidate:** Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234), main `ae7c3e5102b99a66bd7806d602146f1309a9749d` verified at selection; previous exact-head `ba009821abec50cc52dcbea1e8c6d71b58966115` had [D0 7/7](https://github.com/alimtalbi-ata/aiops/actions/runs/41282126973) only for that SHA. New focused product commit `c3e6b4e8ae8448d0295f369509aa2cb8976ce557` ports 12 reviewed non-overlapping Git blobs without source histories. New exact-head CI **PENDING** and must be independently observed after this documentation commit. No merge to main.

| Team/owner | Source PR/HEAD (Draft, base old #234) | Exact source CI | Selective integration / blocker / next |
|---|---|---|---|
| ACME/Twin P1 | [#268](https://github.com/alimtalbi-ata/aiops/pull/268) `c62d5959a68e912c16a89c83198f54b7cd3b6380` | [Quality 41283394088](https://github.com/alimtalbi-ata/aiops/actions/runs/41283394088) 3/3, 138/138 targeted | 3 paths: 15-stage receipt requirements, 6 checkpoints NOT_EXECUTED; no authenticated readback. Next: disposable Core Incident/Run receipt adapter, no forged GLPI/evidence IDs. |
| Portal P0 | [#269](https://github.com/alimtalbi-ata/aiops/pull/269) `e5fc0d60ac3051a50c8b3ff62fcb9a3ba2910efd` | [Quality 41283838658](https://github.com/alimtalbi-ata/aiops/actions/runs/41283838658) 3/3; Chromium 16/16, consumer 22/22 | 3 paths: actual Core TCP/TLS negative 200 UNKNOWN, 401/403; Portal 503 and OIDC 401. Next: real server-side delegation with independent GLPI human rights; keep dispatch disabled until qualified. |
| Core P0 | [#270](https://github.com/alimtalbi-ata/aiops/pull/270) `86f11b4112ebef53e6b91071a573c5f2b927ca77` | [Quality 41284915846](https://github.com/alimtalbi-ata/aiops/actions/runs/41284915846) 3/3; Core 84/84, native TLS 9/9, installed PG16 14 PASS **1 SKIP** | **Only 3/5 paths ported:** independent native TLS authority test + loader + proposed ADR. **Held back** `tests/test_core_actor_pg16_native_sha_restore.py` and `tests/test_core_xref_installed_migrations.py`: same-major PG16 client missing in Quality; 1 SKIP is NOT_QUALIFIED. Next: provide native PG16 client and make skip a hard CI gate. |
| Policy/HITL P0 | [#271](https://github.com/alimtalbi-ata/aiops/pull/271) `19a01436e1fa55b8c31a15e4f6d7ef11764c3a3a` | [Quality 41285129060](https://github.com/alimtalbi-ata/aiops/actions/runs/41285129060) 3/3; [combined 41285129105](https://github.com/alimtalbi-ata/aiops/actions/runs/41285129105) 1/1, 7/7 + PG16 5/5 | 3 paths: two distinct REJECT events across separate OS Worker processes and persistent Temporal restart, deterministic gateway-close, zero effects. Next: adversarial tenant/lease restart isolation; no APPROVE. |

**Contracts and ADR:** canonical Core Incident/Run authority, GLPI CMDB/ticket and verified-human rights, Twin governed dependencies, Policy deterministic, Temporal notifications only. Never infer ALLOW from synthetic IdP/GLPI preflight or HMAC. The 15 ITIL stage statuses remain NOT_EXECUTED, no real Analyst/Critic, SIMULATE, verification or resolution/reopen. Migration order `001→004→009→010→011→012→013`; no new schema this cycle; immutable 013 audit retained. No file overlap between four selected deltas. Old #201/#194 histories not merged. D0 integrated **PENDING**; D1 partial disposable REJECT only; D2 full same-SHA ITIL browser/API **NOT_VERIFIED**; D3 cumulative install/upgrade/rollback **NO_GO**; D4 customer signoff **NOT_ATTESTED**. `RELEASE_STABLE=NO_GO`.

**Rollback:** revert focused port `c3e6b4e8ae8448d0295f369509aa2cb8976ce557` and the subsequent documentation commit via new candidate commits; rerun exact-head CI, do not rewrite main, never delete installed 013 audit data. No host, real GLPI write, Docker socket, LIVE, production, or deployed-runtime assertion.


## Architect selective integration — 2026-11-01 09:41 CET (Europe/Paris)

**Decision:** keep sole Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234) on `integration/enterprise-slice-main-20261031-2230`, base current `main=ae7c3e5102b99a66bd7806d602146f1309a9749d` (40 ahead/0 behind before port). Reviewed four focused source Draft diffs and exact changed paths, ported **12 non-overlapping Git blob paths** in product commit `b354c44f26a26a5567b3cf57e0a7d3aa6cf64968` without their branch histories; Core dedicated PG16 workflow trigger adapted to include `main` so the integration PR can qualify its exact HEAD. **New candidate CI is PENDING** until the final docs HEAD is checked. Prior candidate `6a8c9bca` [7/7](https://github.com/alimtalbi-ata/aiops/actions/runs/41286401487) does not qualify this port. No merge to main.

| Owner / priority | Source Draft HEAD | Source exact-head checks | Imported scope / blocker | Next task |
|---|---|---|---|---|
| ACME/Twin P1 | #272 `8ce1c26ef284166c42770d81b58b1c30b5810677` | Quality [41287105440](https://github.com/alimtalbi-ata/aiops/actions/runs/41287105440) 3/3, 148/148 targeted | 3 ACME paths; offline probe only; actor/tenant binding UNKNOWN | Core independently authenticated seven-event binding; ACME may only validate a real readback, never invent receipts |
| Portal/GLPI P0 | #273 `2c2cda0a6dfcbf526bca491338dd40e9054aba7a` | Quality [41288065952](https://github.com/alimtalbi-ata/aiops/actions/runs/41288065952) 3/3, consumer 22/22, Chromium 18/18 | 3 Portal paths; session recheck and Core negative TLS; positive ALLOW prohibited | Native GLPI profile/entity ACL + signed Core response required; test revocation and no browser bearer |
| Core/NOC P0 | #274 `308bf92c311b7f8b07c8bb9f51adc64e8b3ff903` | Dedicated [41288738108](https://github.com/alimtalbi-ata/aiops/actions/runs/41288738108) 1/1 no SKIP, Quality [41288738180](https://github.com/alimtalbi-ata/aiops/actions/runs/41288738180) 3/3 | 3 Core paths; native PG16 16.15 archive/restore 001/004/009–013, audit preserved | Core actor+tenant+source hash readback contract, no positive human authority without independent GLPI |
| Policy/HITL P0 | #275 `2d44dd25eab684104b43cf704d6bb8aef227617f` | Dedicated [41289152239](https://github.com/alimtalbi-ata/aiops/actions/runs/41289152239) 1/1 (8/8 + DR 5/5), Quality [41289152249](https://github.com/alimtalbi-ata/aiops/actions/runs/41289152249) 3/3 | 3 Worker paths; two tenant-scoped synthetic principals, two OS restarts, REJECT-only | Continue isolated ACK/lease replay adversarial checks; no approval/effect/LIVE |

**SOURCE_REVIEWED:** 12 selected source paths; source CI_PASS as linked; new candidate **INTEGRATION_PASS not yet attested**. **RUNTIME_OBSERVED** only disposable CI at source HEAD, no client or Debian deployment. **NOT_VERIFIED:** canonical ACME seven-event Incident/Run actor+tenant+source hash linkage; 15 ITIL stages/6 checkpoints remain NOT_EXECUTED; GLPI native human rights, positive ALLOW, actual Analyst/Critic/Evidence/Policy/HITL/SIMULATE/verify/reopen journey, physical partition, cumulative install/upgrade/rollback, customer signoff. Native PG16 same-major restore is now qualified at **source** only; requalify at integration HEAD. Policy synthetic HMAC and gateway-close are not real OIDC/GLPI authority or physical packet loss. No new migration, GLPI writer or duplicate ledger; 013 audit rows must remain immutable. **D0 PENDING, D1 partial REJECT only, D2 NOT_VERIFIED, D3 NO_GO, D4 NOT_ATTESTED; RELEASE_STABLE=NO_GO.**

**Order/rollback:** #272→#273→#274→#275 selective blobs already combined in one candidate commit; do not merge Draft source PRs or historical #201/#194. For failure, revert product `b354c44f26a26a5567b3cf57e0a7d3aa6cf64968` and its docs commit via *new* commits on #234; rerun exact-head CI, preserve 013 audit and main history, no force-push/reset. Main promotion requires current mergeability, exact HEAD checks, D1/D2/D3/D4 evidence and explicit GO; otherwise keep Draft. No SSH/sudo/host, real GLPI write, LIVE executor or external mutation.


## 2026-11-01 10:40 CET — architect cycle 11: focused integration, authority still UNKNOWN

**Decision:** sole candidate [Draft #234](https://github.com/alimtalbi-ata/aiops/pull/234) based on main `ae7c3e5102b99a66bd7806d602146f1309a9749d` (42 ahead/0 behind *before* this cycle). Prior candidate HEAD `5d06311c6bc53d6d60c54483f485acfa5df8eba8`; focused product commit `c7c05aa70d49e45b65b8db5f287723ab88bbe6bf` imports 14 source file blobs from four Drafts without histories, migration or 013 audit change. New docs commit and **new exact-head CI pending at writing**; prior 8/8 on `5d06311c` does not qualify the new HEAD. No main merge. ADR: [cycle 10:40](../release/AIOPS2-INTEGRATION-CYCLE-2026-11-01-1040.md).

| Team / WIP | Source PR / exact HEAD | Source qualification | Integrated paths and next contract |
|---|---|---|---|
| ACME/Twin P1 | [#276](https://github.com/alimtalbi-ata/aiops/pull/276) `d54be9fe6babe3d60568363d5515e59e6487cda3` | [Quality 41291051671](https://github.com/alimtalbi-ata/aiops/actions/runs/41291051671) 3/3, 160/160 targeted | 3 ACME paths; seven-event SHA shape TEST_ONLY remains UNAVAILABLE, 15 stages/6 checkpoints NOT_EXECUTED. Next: integrate *independently authenticated* Core actor/tenant Incident/Run readback with seven immutable event links in disposable E2E, no invented IDs |
| Portal/GLPI P0 | [#277](https://github.com/alimtalbi-ata/aiops/pull/277) `34115ff47009f7085b3223f90c9feeb9abc3b336` | [Quality 41292392857](https://github.com/alimtalbi-ata/aiops/actions/runs/41292392857) 3/3; Chromium 19/19, consumer 22/22, OIDC 12/12 | 2 Portal paths; 15 re-signed negative variants, valid offline RSA shape never grants ALLOW. Next: native human GLPI User/Profile/Entity permission readback + Core signer/nonce contract, no positive UI until independently attested |
| Core/NOC/CMDB P0 | [#278](https://github.com/alimtalbi-ata/aiops/pull/278) `f8ce7dc7cd8d24decef19847de8720939e6bb745` | [Quality 41292933631](https://github.com/alimtalbi-ata/aiops/actions/runs/41292933631) 3/3; Core 91/91, xref 20/20, PG16 installed 14/14 | 6 Core paths; pinned HTTPS actor/tenant/Run/source event hash preflight before nonce; still 200 UNKNOWN. Next: independently sourced canonical seven-event readback + real native human GLPI authority on disposable stack; do not create parallel CMDB |
| Policy/HITL/Temporal P0 | [#279](https://github.com/alimtalbi-ata/aiops/pull/279) `6c4a8bb03534088355864c1ff41b39e173c2be6a` | [Quality 41293262077](https://github.com/alimtalbi-ata/aiops/actions/runs/41293262077) 3/3; [combined 41293262009](https://github.com/alimtalbi-ata/aiops/actions/runs/41293262009) 1/1, 8/8 + DR 5/5 | 3 Worker paths; two persisted Temporal server restarts/four Worker PIDs, REJECT-only. DEAD is CI SQL-injected, not runtime API; gateway close != physical packet loss. Next: Core-owned runtime DEAD transition/ACK lease fencing without effects |

**SOURCE_REVIEWED** 14 source paths and relevant patches, no overlapping team files; **CI_PASS** at four *source* exact HEADs only at authoring; **INTEGRATION_PASS** pending new candidate exact-head CI; **RUNTIME_OBSERVED** disposable PG16/Temporal/Chromium only, not customer/deployment; **NOT_VERIFIED** independent IdP/GLPI human ALLOW, canonical Core seven-event binding, real ticket/CI readback, full Event→Incident→Twin→Analyst/Critic→Evidence→Policy/HITL→SIMULATE→VERIFY→resolve/reopen, D2 role UX, D3 cumulative clean install/upgrade/rollback, D4 signoff. No runtime positive actor authorization. D0 pending, D1 partial negative REJECT only, D2/D3/D4 NO_GO, **RELEASE_STABLE=NO_GO**.

**Migration/rollback/merge:** no new migration; preserve 001/004/009→013, PG16 16.15 and append-only audit 013. The Worker DEAD fault is disposable SQL injection, not a data migration. Source PRs remain Draft, stacked on former candidate HEAD; never merge their histories or historical #201/#194. Revert the new docs commit then product `c7c05aa70d49e45b65b8db5f287723ab88bbe6bf` via fresh candidate commits, rerun all exact-head checks and retain 013 ledger. Main is unchanged; promotion only via merge commit PR with expected exact SHA, green checks, D1/D2/D3/D4 and GO. No SSH/sudo/Docker socket, real GLPI writes, LIVE or host validation.


## 2026-11-01 11:43 CET — architect selective integration cycle: independent authority remains unqualified

**Single candidate:** [Draft #234](https://github.com/alimtalbi-ata/aiops/pull/234), branch `integration/enterprise-slice-main-20261031-2230`, main independently checked at `ae7c3e5102b99a66bd7806d602146f1309a9749d` (0 behind before port). Previous candidate HEAD `ab06b95bca2caeffdc4757d671a83700930c8267` had D0 8/8 on [Quality 41294253563](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253563), [native PG16 41294253688](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253688), [combined 41294253489](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253489), [Worker DR 41294253549](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253549), [outbox 41294253557](https://github.com/alimtalbi-ata/aiops/actions/runs/41294253557). Those results **do not** qualify the new HEAD.

**Focused selective product port** `7a1e344313a94335c93fdafd0929c4063e673640`: 13 distinct exact Git blobs, four source Drafts stacked on the prior #234, without their historical commits. No migrations, schema/runtime write, 013 audit mutation, LIVE, host, or real GLPI access.

| Owner / priority | Source HEAD, exact source CI | 13-path port and next contract |
|---|---|---|
| ACME/Twin P1 | [#280](https://github.com/alimtalbi-ata/aiops/pull/280) `98617bb5e0bb248bb81d1bb71112a5c9cbb18e7f`; [Quality 41295561991](https://github.com/alimtalbi-ata/aiops/actions/runs/41295561991) 3/3, targeted 170/170 | 3 paths: seven full-event SHA256 vs Core v1 single `source_payload_hash` is **not** same hash domain. Next: jointly specify canonical serialization with Core; offline fixtures must remain UNAVAILABLE |
| Portal/GLPI P0 | [#281](https://github.com/alimtalbi-ata/aiops/pull/281) `7cd75b6d9ebbf707f80e19dea9b967ccd30fe485`; [Quality 41296693871](https://github.com/alimtalbi-ata/aiops/actions/runs/41296693871) 3/3, consumer 24/24, Chromium/API 43/43 | 4 paths: disposable signed Core + separate native-shaped GLPI human session, negative only; signer and actual native rights not attested. Next: independently sourced IdP/GLPI human User/Profile/Entity/Ticket rights, signer key rotation and revocation |
| Core/NOC/CMDB P0 | [#282](https://github.com/alimtalbi-ata/aiops/pull/282) `9590980f2d273a3cea33ebf0cf68fa03306c7c13`; [PG16 TLS 41297372938](https://github.com/alimtalbi-ata/aiops/actions/runs/41297372938) 1/1 (6/6), [Quality 41297372946](https://github.com/alimtalbi-ata/aiops/actions/runs/41297372946) 3/3 | 3 paths: synthetic PG16 seven-event readback on 001/004/009–013, **test-only** hash domain, no Core runtime seven-event API. Next: Core-owned canonical signed seven-event readback and audited terminal DEAD contract; avoid parallel CMDB |
| Policy/HITL/Temporal P0 | [#283](https://github.com/alimtalbi-ata/aiops/pull/283) `0074f91a25bec7d616eb2ece152b26cafd93c65c`; [combined 41297520143](https://github.com/alimtalbi-ata/aiops/actions/runs/41297520143) 1/1 (9/9 + DR 5/5), [Quality 41297520120](https://github.com/alimtalbi-ata/aiops/actions/runs/41297520120) 3/3 | 3 paths: actual Core claim after eighth lease stays LEASED attempts=8, **not DEAD**; existing DEAD is SQL injected. Next: Worker-only negative contract tests against Core-owned audited runtime DEAD; no APPROVE/effect |

**Architecture decisions:** no promotion from signed synthetic Core ALLOW or GLPI-shaped fixture to human authorization; independent issuer, tenant/actor/Run/ticket/entity, nonce/JTI and 013 ledger are mandatory. ACME full-event and Core source-payload hash domains differ; no seven-event Core runtime binding or verified blast radius. Worker retry exhaustion lacks runtime terminal transition. Temporal signal is notification only. Keep all 15 ITIL stages and six checkpoints NOT_EXECUTED until real synthetic disposable end-to-end receipts.

**Truth labels:** SOURCE_REVIEWED 13 source patches/blobs; CI_PASS four independent source exact HEADs; INTEGRATION_PASS **PENDING** on new candidate HEAD; RUNTIME_OBSERVED only disposable CI sources; NOT_VERIFIED actual human IdP/GLPI rights, Core seven-event production API, D1 complete ITIL chain, D2 operator role journey, D3 cumulative kit install/upgrade/rollback, D4 customer signoff. **RELEASE_STABLE=NO_GO**, keep #234 Draft, main unchanged. No merge despite source green. Revert new docs commit and focused product commit `7a1e344313a94335c93fdafd0929c4063e673640` using new candidate commits, rerun exact-head CI, never reset/force-push or delete 013 audit; main promotion only after D0–D4, expected_head_sha and explicit GO.


## 2026-11-01 12:34 CET — anti-duplication and selective port register

| Source | Ownership / reuse | Gate |
|---|---|---|
| #284 ACME HEAD `75eb60d8` | 3 exact blobs; full-event/payload/Core hash cross-domain **test-only**, no Incident/Run ownership | 181/181 targeted, Quality 3/3 source; integrated exact-head pending |
| #285 Portal HEAD `2523bad3` | 4 exact blobs; synthetic IdP→GLPI signer rotation/JTI/nonce negatives, no ALLOW | 48/48 targeted, Quality 3/3 source; integrated exact-head pending |
| #287 Core HEAD `20ecf050` | 4 exact blobs; independent HTTPS/TLS PG16 seven-event preflight, no migration/positive human ACL | PG16 10/10, dedicated 1/1 + Quality 3/3 source; integrated exact-head pending |
| #288 Worker HEAD `33b4730d` | 3 exact blobs; exhausted eighth lease fencing, zero signal, no runtime DEAD | combined 10/10 + DR 5/5, dedicated 1/1 + Quality 3/3 source; integrated exact-head pending |
| #286 existing-host observer | **HOLD / DUPLICATE**: second systemd observer and Issues-token publisher overlap already publishing reporter `scripts/debian-readonly-reporter.py` + SSH `scripts/aiops-publish-report.sh`. Reuse narrow runbook only after source/security review; typed task executor unconnected | No host install, no unrestricted Docker socket, no LIVE or arbitrary command; no merge |
| Debian runtime report | Existing canonical GitHub branch `ops/debian-runtime-reports`, 11:29 UTC collection; commits 11:29/11:30/11:35 UTC show repeated publication | Fresh at 12:34 CET (~5m), automatic cron firing NOT_TESTED, recheck each cycle |

The sole integration candidate remains Draft #234; source histories were **not** merged, only 14 exact blobs in `d3099158`. Main `ae7c3e51` unchanged. Source 14/14 jobs SUCCESS; new combined-head CI is **NOT_VERIFIED**. See [cycle record](../release/AIOPS2-INTEGRATION-CYCLE-2026-11-01-1234.md). Rollback by revert of candidate commits only, never main reset or audit 013 deletion.


## 2026-11-01 13:42 CET — 8h sprint integration: four exact-head receipt lots

**Sole Draft #234** base main `ae7c3e5102b99a66bd7806d602146f1309a9749d`, prior HEAD `bbe95d9894df13ab910c2b99ccb3d09ec32aa678`; source Drafts #289 `d55049cfc5627db5006667f05d459762002f1012` (ACME P1), #290 `b929bd8b0058c7f2e5a023631de14eae4db15aeb` (Portal P0), #291 `5514ce77728bfd7bf0ce6a1ccf3a6b9a2a9c946d` (Core P0), #292 `df978fc28d0d776e364d83dea587a8d82683f722` (Worker/Policy P0). The architect selectively imports **13 exact Git blob SHAs** (4+2+4+3) without merging source histories, touching migrations, creating a parallel authority or changing main/deploy. Combined new HEAD **CI pending until exact SHA qualification**; previous #234 10/10 is NOT transferable. All source PRs remain Draft.

**Source CI_PASS:** #289 [Quality 41304723889](https://github.com/alimtalbi-ata/aiops/actions/runs/41304723889) 3/3, ACME targeted 193/193 (156 catalogue+22 locator+12 SAN fixture+3 overrides); #290 [Quality 41305414476](https://github.com/alimtalbi-ata/aiops/actions/runs/41305414476) 3/3, Portal browser/API 51/51; #291 [Core PG16/TLS 41306396835](https://github.com/alimtalbi-ata/aiops/actions/runs/41306396835) 1/1 12/12 + [Quality 41306396816](https://github.com/alimtalbi-ata/aiops/actions/runs/41306396816) 3/3; #292 [combined PG16/Temporal 41306864067](https://github.com/alimtalbi-ata/aiops/actions/runs/41306864067) 1/1 10/10 + DR 5/5 and [Quality 41306864394](https://github.com/alimtalbi-ata/aiops/actions/runs/41306864394) 3/3. Source green is not integration runtime evidence.

**ADR/security:** ACME three SHA256 domains are distinct and **not Core runtime equivalence**; its 15 ITIL stages/six checkpoints remain NOT_EXECUTED. Portal's IdP/GLPI and signer/nonce tests are synthetic negative-only (503 UNKNOWN, revoked 401); no real human GLPI rights or positive ALLOW. Core seven-event informational receipt follows disposable TLS+PG16 readback but is nonportable, unsigned and UNKNOWN-only, with immutable migration 013 replay ledger preserved. Worker receipt observes two REJECT outbox events **LEASED attempts=8** across three disposable Temporal server generations, 0 signals/effects/APPROVE; DEAD remains missing in Core runtime (older SQL injection is not runtime). No GLPI write, executor, LIVE or host access.

**Debian runtime evidence:** canonical [latest.json](https://github.com/alimtalbi-ata/aiops/blob/ops/debian-runtime-reports/ops/debian-reports/SRV-DEB-05/latest.json) collected **2026-11-01 12:39:01 UTC (13:39 CET)**, 61 containers, 53 running/8 exited, 22 healthy/38 no-healthcheck/1 unhealthy. Rebuild Portal/Core running healthy; rollback historical exited/unhealthy does not prove active outage. GitHub reporter publication observed, automatic cron invocation NOT_TESTED. #286 duplicate observer stays Draft; no deploy/aiops2-stable push or Docker/volume change.

**Gates:** SOURCE_REVIEWED=13 source blobs and patches; CI_PASS=source exact-head only; INTEGRATION_PASS=PENDING new candidate SHA; RUNTIME_OBSERVED=disposable CI PG16/Temporal/Portal and read-only published host report only; NOT_VERIFIED=real human IdP/GLPI authorization, ACME→Core full-event equality, Core runtime DEAD, full ITIL E2E, D3 cumulative kit/rollback, customer validation. **RELEASE_STABLE=NO_GO**, #234 Draft, main unchanged. **Rollback:** revert only this selective candidate commit via new PR commit, requalify exact HEAD; preserve migrations 009–013, immutable 013 audit, Docker volumes and main history.


## 2026-11-01 15:21 CET — single-stack 7777 decision and Core 014 selective integration

**Decision:** sole Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234), main `ae7c3e5102b99a66bd7806d602146f1309a9749d` unchanged. The architect selectively ports **five Core-owned exact blobs** from Draft [#295](https://github.com/alimtalbi-ata/aiops/pull/295) HEAD `f4c177f4415f0ae0f1b5f2162e687b25dbdbc64e`: handler, migration **014**, PG16 test, dedicated workflow, ADR. Source [Core terminal PG16 #41315653226](https://github.com/alimtalbi-ata/aiops/actions/runs/41315653226) 1/1 SUCCESS, **12/12** adversarial tests; [native recovery #41315653322](https://github.com/alimtalbi-ata/aiops/actions/runs/41315653322) 1/1 SUCCESS with 001/004/009→014 archive restore; source Quality [#41315653230](https://github.com/alimtalbi-ata/aiops/actions/runs/41315653230) 3/3 SUCCESS. **Candidate new HEAD CI is PENDING; old candidate 10/10 does not transfer.** Worker [#296](https://github.com/alimtalbi-ata/aiops/pull/296) negative route-absent test is **not ported** before a new positive integration test on 014. All source PRs stay Draft; no PR merge.

**Host snapshot:** [GitHub latest.json](https://github.com/alimtalbi-ata/aiops/blob/ops/debian-runtime-reports/ops/debian-reports/SRV-DEB-05/latest.json) `2026-11-01T14:19:01.751858+00:00` = 15:19 CET, **61 total / 53 running / 8 exited**, rebuild Portal/Core running healthy; historical rollback portal exited/unhealthy. Loopback **17777 reachable**, **host TCP 7777 NOT_VERIFIED** (no PortBindings, proxy, ss, firewall, TLS/Host or public HTTP proof). **One existing stack** is target; no second portal/Compose project. See [consolidation plan](../operations/AIOPS2-SRV-DEB-05-SINGLE-STACK-7777-PLAN-2026-11-01.md) and [non-deployable manifest](../../ops/debian/compose.canonical.plan.yml) with KEEP/MIGRATE/STOP-LATER/UNKNOWN and host read-only evidence gates. #286 duplicate observer remains Draft. No host SSH/Docker execution, stop, migration, GLPI write, LIVE, volumes change or deploy branch push.

**WIP:** Portal P0 [#298](https://github.com/alimtalbi-ata/aiops/pull/298) HEAD `0a527ce265ad107651b7db9c2ca255ed5f38ff77`, Quality [#41315561070](https://github.com/alimtalbi-ata/aiops/actions/runs/41315561070) 3/3, 55/55 negative, **7777 host unknown**; Core P0 #295 12/12+restore, integrated candidate requalification pending; Worker/Policy P0 #296 HEAD `a96111982d43accdb9dc7cede2f1c466fab70baa`, combined [#41311898721](https://github.com/alimtalbi-ata/aiops/actions/runs/41311898721) 11/11+DR 5/5, negative 404 only, positive 014 not integrated; ACME P1 #297 HEAD `a4daed17b6452ca6179f9007780700ee9a795429`, Quality [#41314428648](https://github.com/alimtalbi-ata/aiops/actions/runs/41314428648) 3/3, 210/210 synthetic. Actor/tenant/GLPI native rights, Core signer, full ACME ITIL 15 stages/6 checkpoints and 7777 host remain **NOT_VERIFIED**. **RELEASE_STABLE=NO_GO**.

**Rollback:** revert the new selective candidate commit (Core 014 code + docs) by a forward commit, never DROP 013/014 or delete immutable audit; preserve existing volumes, images, backup and `main` history. Requalify new exact HEAD before any merge; no deploy.


### 2026-11-01 16:14 CET — Worker #299 selective reuse

Source #299 HEAD 507899f18d38a083f1bedc5a8603d17160612c83, CI 41316946503 (1/1 positive + 5/5 PG16 DR), Quality 41316946593 (3/3). Three Worker paths imported to sole Draft #234, with main-based CI trigger and no raw PG16 archive upload. Core #295 terminal /dead and migration 014 already present. Portal #298 55/55 negative and ACME #300 205/205 offline remain source-only. Exact candidate HEAD CI required; 7777 and real GLPI human authority NOT_VERIFIED. NO_GO, revert targeted code only, retain 013/014 audit and host volumes.


### 2026-11-01 16:25 CET — selective source #302/#301

Core #302 HEAD 990b1f8f6ce14a1e4d191a8fb062ada1fd990039, four files, canonical Core route mounted, source PG16 14/14 and native recovery CI 41320750573 SUCCESS, Quality 41320750574 SUCCESS. Portal #301 HEAD 604c704bde3291615350cc4623040dea8273a14c, five files, invalid OIDC cookie cannot downgrade, source Chromium/API 54/54 and Quality 41320526303 SUCCESS. Both selectively imported into sole Draft #234 without merging source history. Candidate exact-head CI pending; real GLPI human rights and host 7777 NOT_VERIFIED. NO_GO; forward revert targeted commits, preserve audit 013/014 and volumes.

## 2026-11-01 17:18 CET — Selective reuse decision

- #303 Worker: import three new files, change only its workflow trigger to include `main`; Core remains sole owner of DEAD/014; gateway-close injection != physical partition. Source CI 41321920299 (1/1 + DR 5/5), Quality 41321920306 3/3.
- #304 ACME: import four paths, including one additive test change, preserving synthetic seven-event `UNAVAILABLE` rather than fabricating Core PG16 equality. Source Quality 41324447715 3/3, targeted 200/200.
- #305 Portal: import five paths, including explicit duplicate OIDC cookie denial and forged HTTPS Origin refusal, no viewer fallback. Source Quality 41324950012 3/3, browser/API 56/56.
- All three source PRs remain Draft, unmerged; candidate #234 is the sole main-based Draft. No historic branch merges, no Core/Worker schema collision. Integrated CI on new HEAD is a separate gate; no main merge before all required exact-head jobs succeed and D1–D4 qualify. Rollback forward revert the focused integration commit only; preserve 013/014 audit and host volumes.


## Architect integration cycle — 2026-11-01 18:19 CET (source qualification; new exact-head CI pending)

- Single Draft integration PR [#234](https://github.com/alimtalbi-ata/aiops/pull/234); pre-port candidate `e484f2e17bf4c72e4c5319e2e92f32430b4ec3b0`, verified DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d` (62 ahead / 0 behind). New candidate HEAD and its exact CI must be read from GitHub after this commit. **Do not transfer the old 10/10 CI to the new HEAD.** No main merge, no host write.
- **SOURCE_REVIEWED:** 14 exact Git blobs selectively imported from four independent focused Drafts, not their branch histories: Core [#306](https://github.com/alimtalbi-ata/aiops/pull/306) `73967f349057e852ad5329852804d7412a3ac753` (3 Core test/workflow/ADR paths, base `5045dfa0` but both preexisting paths blob-identical on current candidate); Worker [#307](https://github.com/alimtalbi-ata/aiops/pull/307) `a9e1a56c7030b38f9a3a0079f073d5a0a6c848fa` (3 paths); ACME [#308](https://github.com/alimtalbi-ata/aiops/pull/308) `3368e068919b938898966ad16117e0daf06eecb2` (4 paths); Portal [#309](https://github.com/alimtalbi-ata/aiops/pull/309) `5b5d0960ed092c69068fd1e4f1a9ca72ff435b73` (4 paths). Source PRs are Draft and remain unmerged. No migrations or new persistent stack.
- **Source CI_PASS only:** Core [#41325667604](https://github.com/alimtalbi-ata/aiops/actions/runs/41325667604) 15/15 PG16, Quality [#41325667635](https://github.com/alimtalbi-ata/aiops/actions/runs/41325667635) 3/3; Worker [#41326736739](https://github.com/alimtalbi-ata/aiops/actions/runs/41326736739) 2/2 + DR 5/5, Quality [#41326736701](https://github.com/alimtalbi-ata/aiops/actions/runs/41326736701) 3/3; ACME [#41329857661](https://github.com/alimtalbi-ata/aiops/actions/runs/41329857661) Quality 3/3, targeted 210/210; Portal [#41330094178](https://github.com/alimtalbi-ata/aiops/actions/runs/41330094178) Quality 3/3, browser/API 58/58. These qualify **source heads only**. New combined exact-head CI, PG16 009–014 DR, Chromium/Portal and ACME/Worker interplay remain **NOT_VERIFIED** until GitHub Actions completes.
- **Contracts:** Core post-DEAD credential/permission/provenance revocation returns 401/403/UNKNOWN without rewriting immutable 014; Worker 18 concurrent post-DEAD HTTP retries/ACK/claim after persisted Temporal restart remain REJECT/zero effects; ACME consumes only untrusted seven-event offline readback as UNKNOWN, 15 ITIL stages and six checkpoints NOT_EXECUTED; Portal refuses split Cookie headers and forged GLPI rights, pins HTTPS callback :7777 (never :17777), 401/503 fail-closed. These are disposable synthetic tests, not native human GLPI authority or host listener evidence.
- **RUNTIME_REPORTED, not new runtime test:** GitHub `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json` collected_at `2026-11-01T17:14:01.198403+00:00` (18:14 CET), 61 containers / 53 running / 8 exited; `aiops2-rebuild-portal` healthy, `aiops2-portal-candidate-web-20261029` running/no healthcheck, rollback exited/unhealthy. Host TCP **7777 NOT_VERIFIED**; report lacks complete PortBindings, reverse proxy, firewall and traffic ownership. No host migration/stop performed.
- **Gate:** D0 integrated CI pending, D1 partial REJECT-only, D2 15-stage operator/GLPI HITL NOT_VERIFIED, D3 cumulative kit NO_GO, D4 human signoff NOT_ATTESTED. **RELEASE_STABLE=NO_GO.** Retain single DEV stack target `aiops2-rebuild-*`, classify duplicates UNKNOWN pending read-only mapping, no Docker/volume deletion or `deploy/aiops2-stable` push.
- **Rollback:** forward-revert only this 14-blob + three-document commit on the integration branch, then requalify exact new HEAD; never rewrite main, drop migrations 009–014, immutable 013/014 audits, DB or Docker volumes. If promotion is ever approved, merge via PR with exact expected HEAD and separately planned revert.
- **Next:** recheck all exact-head GitHub Actions; Core independently authenticated seven-event PG16 actor/tenant/Run proof, Portal GLPI native human authorization + 7777 host attestation, Worker concurrency stress boundary, ACME complete authorized ITIL scenario. Three P0 (Core, Portal, Worker), ACME P1. 


## Architect cycle — 2026-11-01 19:2x Europe/Paris (selective source port; D0 requalification pending)

- **Base:** main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; sole Draft #234 previous exact HEAD `e6381a6d7e8e088add37e6e28e9fde9ef543a9ff` (63 ahead/0 behind). New integration HEAD must be re-read and exact-head CI requalified after this commit; source CI cannot be transferred. No direct source PR merge, no main/deploy merge.
- **Core #310** `df845f9ea800c6956d96f3911e720e044ad2af2c`: 3 Core paths, PG16/TLS 14/14 and zero SKIP [#41336002970](https://github.com/alimtalbi-ata/aiops/actions/runs/41336002970), Quality 3/3 [#41336003122](https://github.com/alimtalbi-ata/aiops/actions/runs/41336003122); stale/expired independent transport evidence -> UNKNOWN, immutable 013/014 + native PG16 restore; synthetic 014 fixture not a runtime /dead.
- **Worker #311** `2ec1aef8952ea98ca69626ee8a4daf52f5303ed9`: 3 Worker paths, canonical 2/2 + revocation 1/1 + PG16 DR 5/5 [#41332063971](https://github.com/alimtalbi-ata/aiops/actions/runs/41332063971), Quality 3/3 [#41332063977](https://github.com/alimtalbi-ata/aiops/actions/runs/41332063977); CI-only proof withdrawal, Core 012 immutable trigger preserved, gateway close injected, physical partition NOT_TESTED.
- **ACME #312** `e1c5d1a7efeef318ac85c9b48e8110442237cc35`: 4 ACME paths, targeted 220/220, Quality 3/3 [#41334336181](https://github.com/alimtalbi-ata/aiops/actions/runs/41334336181); 7 synthetic events, 15 stages and six checkpoints NOT_EXECUTED/UNKNOWN, no positive ALLOW.
- **Portal #313** `e250bb8c16c50254f5ce0a22b7258cc4b0dc38c3`: 2 Portal paths, browser/API 59/59, Host/OIDC 8/8, Quality 3/3 [#41335292014](https://github.com/alimtalbi-ata/aiops/actions/runs/41335292014); forged human GLPI rights fail closed, 7777 contract not host verification, 17777 distinct.
- **Architecture/ownership:** only selected 12 exact Git blobs from these four source Drafts, no source history merge and no schema migration. Core owns authenticated source binding, Portal owns human GLPI visibility gate, Worker owns no-effect retry fencing, ACME owns offline ITIL replay. No new parallel ITSM/CMDB or persistent host stack. D0 integrated CI PENDING until exact HEAD run; D1 partial negative-only; D2/D3/D4 NO_GO. SOURCE_REVIEWED on diffs, source CI_PASS, INTEGRATION_PASS NOT_VERIFIED, RUNTIME_OBSERVED only through GitHub Debian reporter, not current candidate runtime.
- **Debian read-only** `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json` collected `2026-11-01T18:19:01.241861+00:00`, 61 containers (53 running, 8 exited). `aiops2-rebuild-portal` healthy, candidate portal also running. Host TCP 7777 NOT_VERIFIED (only 17777 loopback probe). Keep canonical rebuild services; parallel groups UNKNOWN until digest, Compose labels, network/port bindings, traffic, DB ownership, volumes, backups and rollback inspected. No STOP, prune, down -v, new stack or deploy/aiops2-stable change.
- **Rollback:** forward-revert this selective port on #234 (12 source paths and these docs), preserve immutable Core 013/014 audit, database/host volumes and history. Re-run exact-head CI after revert. **RELEASE_STABLE=NO_GO.**


## Architect cycle — 2026-11-01 20:19 CET — ACME/Portal focused source integration

- **Refs before port:** DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d`; sole Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234) `466cc80e7d1c651ad48791cbbfa7ac7fc6d1c6c6`, 64 ahead / 0 behind. New exact candidate SHA/CI MUST be requalified; old [D0 10/10 workflows, 13/13 jobs](https://github.com/alimtalbi-ata/aiops/issues/186#issuecomment-6562045016) applies only to old SHA. No main merge.
- **ACME/Twin P1 [#314](https://github.com/alimtalbi-ata/aiops/pull/314)** source `31367d1451a1a74ec3d1332d152e23e1d2044582`, 5 paths, [Quality #41339765432](https://github.com/alimtalbi-ata/aiops/actions/runs/41339765432) 3/3 and **230/230** targeted. Synthetic offline seven-event local/Core-shaped hash matrix; independent **TEST_ONLY_UNTRUSTED_NOT_PG16** vector never confers authority; actual Core PG16 hashes null, all 15 ITIL stages + 6 checkpoints NOT_EXECUTED. No real Incident/Run/GLPI/Evidence/HITL IDs.
- **Portal/GLPI P0 [#315](https://github.com/alimtalbi-ata/aiops/pull/315)** source `c308b7bcb31029887e42656364cd7fae520792d4`, 2 paths, [Quality #41340603232](https://github.com/alimtalbi-ata/aiops/actions/runs/41340603232) 3/3, **60/60 browser/API**, **10/10 native mock**, **24/24 consumer**. Two separate disposable TLS mock peers; seven native GLPI READ/READMY negatives, six Core signature/expiry/tenant/nonce negatives; synthetic signed ALLOW + mock READ remains 503 UNKNOWN, revoked OIDC 401. Human native GLPI READ independently NOT_ATTESTED.
- **Debian:** user/operator attests *local* `aiops2-rebuild-portal` running/healthy, `0.0.0.0:7777->777` and `/health` HTTP 200 JSON `external_port=7777`: **7777 LOCAL OPERATOR_VERIFIED**, not independently schedule-observed; external TLS/SSO/GLPI E2E, traffic, uniqueness remain NOT_VERIFIED. [GitHub reporter latest.json](https://github.com/alimtalbi-ata/aiops/blob/ops/debian-runtime-reports/ops/debian-reports/SRV-DEB-05/latest.json) collected `2026-11-01T19:14:01.516272+00:00`, **61 total / 53 running / 8 exited**; `aiops2-portal-candidate-web-20261029` still running; 17777 probe false, 7777 absent. Reporter lacks PortBindings/digests/Compose labels/traffic/volume ownership; no host change. Keep rebuild canonical, classify duplicate UNKNOWN pending read-only mapping, backup and rollback, no STOP.
- **Ownership:** Core P0 independent seven-event PG16 actor/tenant/Run+013/014 audit; Portal P0 native human GLPI trust; Worker P0 post-DEAD concurrent no-effect; ACME P1 honest offline ITIL comparison. Only 7 selected source Git blobs plus these 3 docs, no source history, migration or cross-owner files.
- **Truth/gates:** SOURCE_REVIEWED=2 PR diffs, source CI_PASS=2/2, new integrated D0 CI_PENDING; INTEGRATION_PASS=NOT_VERIFIED until new exact-head jobs. RUNTIME_OBSERVED=operator-local 7777 + published reporter only, NOT new code. D1 partial negative-only; D2 GLPI HITL/ITIL full journey NO_GO, D3 cumulative kit NO_GO, D4 client signoff NOT_ATTESTED; **RELEASE_STABLE=NO_GO**. No deploy/aiops2-stable push, SSH/Docker, GLPI write, LIVE, new persistent stack, DB/volume deletion.
- **Rollback:** forward-revert only this focused candidate commit, rerun exact-head CI, preserve Core 013/014 immutable audit, Docker volumes and main history; no force-push/reset.
