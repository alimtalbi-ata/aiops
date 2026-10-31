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
