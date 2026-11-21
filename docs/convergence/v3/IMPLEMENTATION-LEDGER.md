# V3 selective convergence — actual code port ledger

**2026-11-21 — PR #843, tranche 1.** This is an evidence ledger for *actual files added* and the dependencies preventing premature activation.

## Port 1 — Team C Run Journey offline projection (#824)

**Imported verbatim** from `team-c/san-payments-intelligence-20261119`:

| File | Source blob SHA | Purpose |
|---|---|---|
| `app/portal/acme_run_journey_projection.py` | `b2ae43b3cf63d2205b0da7309627b95988c7561b` | Real Python projection function `project_team_c_run_journey(impact, cockpit)`, 17 stages, deny LIVE |
| `docs/contracts/team-c-san-payments-run-journey.schema.json` | `d283d615244a868f747b9428bd543e37701ae948` | Closed v2 JSON contract |
| `tests/fixtures/team_c/run-journey.valid.json` | `605dc6595ebc56a49dbde138540b543ad89b6313` | Synthetic non-execution example |
| `tests/test_team_c_san_payments_contract.py` | `0dbc05f5e37f5c788c5c2e43da0f1274bec58959` | 12 offline positive/negative unittest cases |
| `.github/workflows/v3-selective-run-journey.yml` | New | Minimal exact-PR Python compile + offline contract gate |

**Dependency inspection on target branch `feature/mission-control-central-unified`:**
- `app/portal/main.py` exists, but does not reference `run_journey`.
- `app/portal/acme_incident_cockpit.py` and `app/portal/acme_incident_cockpit_html.py` returned GitHub 404 on the target branch. These are direct integration points used in #824/#825 and **must not be presumed available**.
- The projection function itself has no third-party imports, but its runtime inputs require `impact.twin_evidence`, `cockpit.twin_consumer`, a common `source_sha256`, `SIM-ACME-` story identity and a deterministic Analyst/Critic/Policy denial preview. **These upstream producers have not been qualified on this base.**
- The source #824 integration tests modify an existing cockpit and cannot be transplanted unchanged while the target lacks those files. The new workflow deliberately runs only the isolated contract suite, not the absent cockpit integration test.
- Source `receipt=null`, `executed_sha=null`, `tenant_id=null`, Worker `NOT_INVOKED`, HITL `SIMULATED_NOT_REQUESTED`, all 17 stages `NOT_RUN/MISSING`; never claim a real Run.

**Status:** `CODE_PORTED_ISOLATED` / `INTEGRATION_BLOCKED_BY_MISSING_COCKPIT_DEPENDENCIES`. The code is imported, but no new route, UI, real Run, Worker, GLPI, or LIVE capability is activated. Tests have **not been executed by this assistant**; CI result **UNKNOWN** until the new workflow reports on the exact head.

**Next safe step:** inspect #818 and #822 against the target at the file/diff level, then selectively port the canonical cockpit/read-model dependencies *with their tests*, or choose an existing target endpoint and adapt the projection. Do not copy #818's 92 changed files wholesale. Once upstream inputs are present, wire one read-only route, add real integration tests and require exact-SHA green CI.

## Rejected premature ports

- #799 replay/freshness test: its dependency `scripts/aiops2_event_correlation.py` is **absent on the target** (GitHub 404). Porting the test alone would break test discovery. HOLD until the canonical correlator and its dependencies are reviewed.
- #823 Playwright suite: the referenced source branch and target browser routes require verification; do not import a failing test suite without a runnable target and fixtures.
- #826/#827/#828 Twin variants: resolve supersession and same-origin contract before choosing one.
- #829 proactive Debian observer: potential host mutation/installer; HOLD pending explicit release approval and rollback qualification.

## Required before enabling this port

1. Confirm which base branch CENTRAL authorizes for V3; #843 currently targets `feature/mission-control-central-unified`.
2. Supply and validate the canonical cockpit, Twin consumer, Analyst/Critic and policy projections (or adapt to existing equivalents).
3. Run offline unittest and adversarial integration tests on the exact commit.
4. Verify that no UI claims a 17-stage PASS, approved HITL, GLPI ticket or real execution.
5. Obtain explicit CENTRAL approval before merge or deployment.

**Do not mark `INTEGRATED` or `QUALIFIED` merely because Python code and a CI workflow have been added.**


## Port 2 — ACME cockpit, Twin and Analyst/Critic dependency modules (#812 / #822 / #825)

**Added actual source modules** from `team-c/san-payments-cockpit-integration-20261119` (PR #825, head `9500b05f1512f59bb6158f92c81eef880d24a9ed`):

| Module | Source blob SHA | Dependency classification |
|---|---|---|
| `app/portal/acme_signal_context.py` | `c6fc538d9a32acd0546a2603c3873ebc33696abd` | `acme_fixture_contract` present on target |
| `app/portal/acme_twin_provenance.py` | `c7d2b35e29892046743c8425539f365986582b85` | `acme_fixture_contract` present; fixture blob `ad91678e81c6875a94e699d37645a971615dfb1e` **identical** between source and target |
| `app/portal/acme_twin_consumer.py` | `96749e3f62fccbc8bb19ba6f2f790d4f18868bf9` | stdlib only |
| `app/portal/acme_lifecycle_read_model.py` | `055fe32afd55a9623c94ac87d3a3cff05875a943` | imports existing `acme_impact_read_model` and imported Twin consumer |
| `app/portal/acme_itil_readiness.py` | `47f95e66e8d7f538c97871a8f8dc29d5aba0594b` | imported lifecycle |
| `app/portal/acme_evidence_collection_plan.py` | `b1cb1c18e9aa8992ba56e0acfb25064a06ba8b0d` | imported lifecycle + ITIL |
| `app/portal/acme_analyst_critic_review.py` | `74d2293daae59c80bc0601e252eb5a94ec611b0f` | imported lifecycle + evidence plan |
| `app/portal/acme_workbench_presentation.py` | `9d5da4e571414212db6cf22eccab943cdeb2a73d` | stdlib only |
| `app/portal/acme_incident_cockpit.py` | `2a7e70c22b8b81427d2e6775e942f8917b315b66` | imported signal/lifecycle/ITIL/Evidence/Analyst/Run Journey |
| `app/portal/acme_incident_cockpit_html.py` | `8a0799c99d97d96f94661cb4d9c78fe267d6b8ed` | imported workbench presentation + Evidence requirements |

**Imported tests:** `tests/test_acme_signal_context.py` (blob `f771d3e3f1b99cc31b826a7a0fa6830ce1b66aa9`), `tests/test_acme_twin_consumer.py` (`1cb6749a10c171b4debcd49ea02549a91066ea5e`), `tests/test_acme_twin_provenance.py` (`cc101c30ee436c066c705f259b468f68b65fc01b`). Extended exact-PR workflow to compile all imported modules and run these three suites plus Run Journey contract tests.

**Critical compatibility issue:** `app/portal/acme_impact_read_model.py` already exists on target (blob `07e345de81812d0847c6f7983ec23e8627a03604`, 18,322 chars), but source #825 has a **different and larger** variant (blob `538ae6a9fcaf249debb051391d076ae65ffddc2d`, 32,290 chars). The target version does not expose `twin_evidence`/`twin_consumer`; source adds cockpit API/page routes and read models. **DO NOT overwrite the target module blindly**: requires method-by-method review, preservation of existing routes/auth and exact tests. `app/portal/main.py` still imports target router; no new routes were registered by this port. The imported cockpit functions are staged as code, not yet reachable in UI.

**Status:** `DEPENDENCIES_PORTED`, `TWIN_OFFLINE_TESTS_PENDING_CI`, `COCKPIT_ROUTE_HOLD`. The fixture identity is verified, import dependency paths inspected; **execution of tests and runtime wiring not verified**. If the CI fails, fix on this draft PR before further ports. The next integration step is a **selective, minimal change to the existing impact router** (or separate safe read-only router) with integration tests and explicit CENTRAL review.


## Port 3 — Active read-only cockpit route on the existing portal (2026-11-21)

**Implemented on PR #843, not copied wholesale:**
- `app/portal/acme_v3_cockpit_adapter.py` — new adapter that uses the target branch's **existing** `build_acme_impact_read_model()` and safely reads the same local ACME fixture, checks matching SHA-256, Run/incident IDs, impact path and affected CI IDs, then adds Twin evidence/consumer and deterministic signal context. The imported cockpit and Run Journey projection operate on the resulting view.
- `app/portal/main.py` — **two surgical additions**: import and `include_router` for the adapter. The original `acme_impact_read_model.py` (blob `07e345de81812d0847c6f7983ec23e8627a03604`) is left untouched.
- `tests/test_acme_v3_cockpit_adapter.py` — tests for projection authority boundaries, JSON+HTML endpoints, legacy impact endpoint non-regression, digest mismatch 503 and missing fixture 503.
- `.github/workflows/v3-selective-run-journey.yml` — pinned FastAPI/Pydantic/httpx/pytest for integration tests, PYTHONPATH and new exact-PR route tests.

**New proposed paths:**
- `GET /api/demo/v3/acme-incident-cockpit`
- `GET /demo/v3/acme-incident-cockpit`

**Runtime behavior if merged and deployed:** purely synthetic local fixture read, no upstream calls or writes, no GLPI/Temporal/Worker activity. Explicit `UNKNOWN` / `DENY_LIVE_ACTION` / `NOT_RUN` / `MISSING`; existing routes remain unchanged. Fixture mutation between reads causes a digest mismatch and a fail-closed HTTP 503 rather than cross-snapshot evidence mixing.

**Important distinction:** the new routes are **wired in the PR source code**, but are **not live on any host** until merge/deploy; no such action was taken. CI exact-head, browser rendering, security review and Debian runtime are **NOT VERIFIED**. Do not promote to GO until test evidence is available. The legacy synthetic route was already public; the new routes use the same strictly local public demo boundary, **not tenant-authorized operational data**.


## Port 4 — COLLECTION-ONLY, explicit CENTRAL instruction (2026-11-21)

**Instruction:** collect functionality, scripts and configuration/contracts from historical source branches and copy into PR #843. **No tests run, no collection execution, no runtime qualification.** These are source imports, not active production integrations.

**Exact source:** PR #818 branch `integration/aiops2-int07-abc-20261118` (HEAD at inspection `636205a7b24de08ff6c52e4b956a42904b58cee9`).

**New Python modules copied verbatim:**
- `app/worker/acme_simulated_hitl.py` — blob `cb20618d60117f373831da28b73f65df3103a84c`
- `app/portal/acme_runtime_context.py` — `5fcb5a81c2c57fb68158ab8b2e3e22148c903845`
- `app/portal/acme_authority_readers.py` — `f76c8de6798fbe4e37d1c90c82167ea49f157eef`
- `app/portal/acme_authority_continuity.py` — `1a8ac66d9af68b14e00726d7f05e68d3ea8bbdad`
- `app/worker/int06a_contract.py` — `d6fe8fa2676795f2866bdf2b712b045072392649`
- `app/worker/int06a_registration.py` — `94fe5a19e7a9a26db86dbb1dd21d7d020d9b7b42`
- `app/worker/int07_offline_collector.py` — `58c3853970b186468688cf30a9a4bf72d016882e`

**Scripts copied verbatim:** `scripts/acme_demo_readiness.py` (`bed51f1a96ccd3798e54d3303961d1a2a3cb69ea`), `scripts/acme_receipt_model.py` (`360870d12a9ff132d7a42c64e34a23cbe04bbc3c`).

**Configuration/contracts and source documentation copied verbatim:**
- `docs/contracts/acme-receipt.schema.json` — `d8766a858092cd919c4703f3c76678d169f5f7a2`
- `docs/contracts/int06a-c.md` — `3c2b529cc1d8e6e0a7e532baec2d0e106b99bdb4`
- `docs/contracts/int06b-b-authorities-proposal.md` — `d87e975998c20887d7faabc25ad667ad194eb14a`
- `docs/contracts/int06b-bc-continuity.md` — `e7ca4c9bcd584e0dbdbe46accb473fee3aa075a7`
- `docs/architecture/ACME-TWIN-PROVENANCE.md` — `772f97e274122915bc70b13d6218a0dbf3c81bfa`
- `docs/architecture/INT06A-FRONTEND-PRESENTATION.md` — `14a32a02cd61b0d90d04456241093d77c11cf8b0`
- `docs/demo/TEAM-C-SAN-PAYMENTS-E2E.md` — `a9b400c3ac61c38600410caa09c820f842e3c6cf`

**Dependency observations, no tests:** authority readers depend on `acme_runtime_context`; continuity additionally imports `worker.acme_simulated_hitl`; offline collector imports readers, continuity and `worker.int06a_contract`; INT06A registration imports `temporalio` and remains **unregistered** in `app/worker/main.py` on this PR. `int07_offline_collector.py` is **source code only**, not invoked. Existing live routes/worker entrypoints were not changed by this collection tranche.

**Historical tests/CI:** earlier commits on this draft PR contain tests and CI changes, but **none were executed in this collection-only tranche**. No CI outcome or functional validation is claimed. Further collecting should preserve file provenance and avoid overwriting existing divergent files.


## Port 5 — Large-scale archival collection without test execution (2026-11-21)

User instruction: **continue collecting historical functionality, scripts, configurations and associated artifacts into PR #843; do not run tests.** This tranche performed GitHub file reads and content-copy commits only. No runtime collectors, tests, workflows, deployments, or merges were intentionally triggered.

**INT07 / PR #818 additional functional sources:**
- Live-path additions (not imported into active routers): `app/portal/aiops_theme.css`, `app/portal/portal_usability.js` (source blobs `f552a2ee939bfc1596df6c29818d2f52ca0fed6e`, `101da4384c8fbd0a524eddbe78390ce0fe25f5ce`).
- Divergent canonical files archived **under** `docs/convergence/v3/source-imports/int07/` preserving original paths: `app/portal/acme_explore_story.py` (`20e77e66a961c6b85138b6d043deeef855dede63`), `app/portal/acme_run_detail.py` (`217bf48e1eba1bdad7b5668ebae608669c512c91`), `app/portal/glpi_operator_view.py` (`f653e24e0564d77a4e3cf7e692cec43f4eb3cdf2`), `app/core/main.py` (`d56c42e7330e683989d8c3c25e0766cc947c1a2b`), `app/worker/main.py` (`70232842f0cc2d933ba2e68c871afefe356eca50`), `app/portal/main.py` (`8fcfbda3d20db60cfed15117e8e86e423a02fb77`). The live canonical entrypoints remain intact.
- Archived historical CI configs: `int06a-c-offline.yml`, `int06a-frontend-offline.yml`, `int06a-integrated-offline.yml`, `int07-integrated-offline.yml`, `acme-demo-readiness.yml`, `quality.yml`, all under `docs/convergence/v3/source-imports/int07/.github/workflows/` to **avoid activating copied workflows**.
- Archived INT07 test/QA sources under `docs/convergence/v3/source-imports/int07/tests/` and `.../qa/playwright/` (23 files: authority, context, INT06A/INT07, worker, Core, Twin, UI, browser and JS contract cases). **Copied only; never executed.**

**TEAM D / PR #823:** original branch `qa/team-d-playwright-20261119` @ `fda248f967c966524af602e30fc654ad05dd477c`. Archived five historical files under `docs/convergence/v3/source-imports/team-d-823/`: Playwright README, report, pytest.ini, smoke script and GitHub workflow, with no activation.

**TEAM A / PR #822:** original branch `feature/team-a-acme-portal-ux-20261119` @ `b19bc42059759deaadc6e46788881582e5ab9823`. Archived divergent cockpit HTML (`56934c505b1afb995dccf721ca7ab10131f7d42a`) and GLPI operator view (`f653e24e0564d77a4e3cf7e692cec43f4eb3cdf2`) under `docs/convergence/v3/source-imports/team-a-822/` without overwriting canonical code.

**Not yet exhaustively collected:** all historical branches/PRs outside the inspected #812/#818/#822/#823/#824/#825 source set; exact entire repository branch inventory and satellites have not been copied. Do not claim global completeness. Further work should prioritize other P0/P1 source PRs, inventory file conflicts and archive non-activated variants.


## Port 6 — Additional P0/P1 historical source harvest (no tests, 2026-11-21)

- **PR #808** `feature/acme-workbench-demo-qualification-addon-20261117`: archived **15 qualification scripts** and **2 portal modules** under `docs/convergence/v3/source-imports/acme-808/` preserving source paths. Includes evidence projection, OIDC/ACL preflight, authority boundaries, browser receipt, Core/Worker binding, autonomous loop qualification, route inventory and receipt contracts. These are **inert historical copies**, not activated.
- **PR #829** `feature/central-proactive-cron-v1`: archived **8 deployment/proactive observer scripts** under `docs/convergence/v3/source-imports/proactive-829/`: installer, build handoff, candidate, update discovery, watchdog, rollback, portal build and archive verifier. Deliberately **not installed**, no cron enabled, no deploy action.
- **Additional PRs inspected for inventory:** #802 (`integration/acme-demo-readiness-gate-20261116`), #799 (`test/aiops2-correlation-freshness-replay-20261116`), with changed filenames identified; not yet completely copied.
- **No test executed** and no claim of exhaustive coverage across all historical PRs, branches or satellite repositories.

**Collection strategy:** copy missing non-conflicting code into active paths only when explicitly suitable; archive divergent entrypoints, workflows, executable deploy scripts and QA source in `docs/convergence/v3/source-imports/<source>/` to prevent accidental runtime activation. Do not automatically promote archival files into the running system.


## Port 7 — Close identified PR inventories, without running tests (2026-11-21)

**Source files copied verbatim and archived inertly:**
- **PR #802** (`integration/acme-demo-readiness-gate-20261116`, head `f594d04e02abde19b2299fbb523bf9d0d0e360b8`): **all 6 listed changed paths** copied under `docs/convergence/v3/source-imports/pr-802/` (three CI configs, golden-demo showrun, readiness script and its historical test).
- **PR #799** (`test/aiops2-correlation-freshness-replay-20261116`, head `7d7024b19cf85d53c5c4993b312681fe1ffd1505`): **its 1 listed changed path** archived under `docs/convergence/v3/source-imports/pr-799/`. Its upstream implementation dependency is still not asserted present.
- **PR #808** (`feature/acme-workbench-demo-qualification-addon-20261117`, head `41f91ab7c6c7f91814368e8590773581d4c5b212`): added its four architecture docs, workflow and divergent portal main plus all 23 listed historical QA/test paths under `docs/convergence/v3/source-imports/acme-808/`. Together with Port 6, **all 46 PR #808 changed paths have source copies** (15 scripts + 2 portal modules + 4 docs + workflow + main + 23 tests).
- **PR #829** (`feature/central-proactive-cron-v1`, head `08ed06f08f9e8ad6b3f8817effa14c57733d4959`): added its workflow, two docs and six test source paths under `docs/convergence/v3/source-imports/proactive-829/`. Together with Port 6, **all 17 changed paths have source copies** (8 deploy/scripts + 1 workflow + 2 docs + 6 tests).
- **PR #825**: archived Team C cockpit workflow and historical test, plus demo doc under `docs/convergence/v3/source-imports/team-c-825/`; active Run Journey modules/contract/fixture and imported tests are already in the PR.
- **PR #824**: archived source workflow and demo doc under `docs/convergence/v3/source-imports/team-c-824/`; source Run Journey module, contract and fixture were previously copied.
- **PR #818**: additionally archived Team C/Team D workflows, decision log, project continuity and E2E handover under `docs/convergence/v3/source-imports/int07/`. One already-existing archived workflow was not overwritten.

**Meaning of complete:** coverage of the **changed-file lists for the specifically enumerated PRs**, not an assertion that all repository branches, other PRs, other repositories or implicit runtime dependencies have been harvested. Source copies do not imply integration, correctness, authorization or deployability.

**User restriction:** NO tests executed, NO collector invoked, NO deployment/merge, NO live service calls. CI workflow files copied under documentation paths are inert. Existing active workflow from earlier implementation remains in the PR but no execution result is claimed.


## Port 8 — Broaden source coverage beyond the initial seven PRs (2026-11-21)

**Collection only; NO tests executed.** Source paths are copied byte-for-byte as UTF-8 text into inert `docs/convergence/v3/source-imports/<origin>/` directories, with no runtime activation, overwrite of canonical entrypoints, CI installation, or deployment.

- **PR #830** `feature/demo-studio-five-minute`: all **9** listed changed files archived under `demo-830/`, including `app/portal/demo_studio.py`, portal/Twin dependents and entrypoints, Dockerfile, workflow, documentation and historical test.
- **PRs #826, #827, #828** (TEAM B same-origin Twin): both changed paths for **each PR** archived under `team-b-826/`, `team-b-827/`, `team-b-828/`. All three source versions of `acme_impact_read_model.py` share blob `301c1bd927fc5f273dd78bc460feba80f24405d5`; HTTP test shares `650d97718dd569ec03dab8eba916ddbbd2a771a4`. No canonical impact router overwrite.
- **PR #809** `feat/ui-dark-saas-premium-20261117`: all **28** listed changed paths archived under `ui-809/`, including actor/tenant read policy, incident read policy, operator session, Postgres session schema, GLPI SCSS, Grafana dashboards, Prometheus YAML, Compose, UX and auth contracts, test sources.
- **PR #801** `feature/github-debian-openai-bridge-v1-20261116`: all **4** changed paths archived under `bridge-801/`, including the prototype agent and workflow; no agent execution.
- **PR #810** `integration/convergence-host-golden-selective-20261117`: all **9** listed changed paths archived under `host-810/`, including Dockerfile, Compose, portal variant, CI and smoke-test sources.

**Additional PR inventory discovered:** #821 (central 7770 cutover), #817/#816/#815 (INT06A), #814 (ABC), #813 (E2E), #811 (Frontend Premium), and earlier historical PRs back to #753 in the inspected recent-PR listing. These and PR #792's much larger portable install kit are **not all fully archived**. The source-harvest is therefore **NOT globally complete**; scope is explicit to prevent a false completion claim.

**No tests executed in Port 8, no operational collection, no merge or deploy.**
