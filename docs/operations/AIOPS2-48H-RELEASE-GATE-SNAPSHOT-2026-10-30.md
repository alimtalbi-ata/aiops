# AIOps 2.0 — 5/5 release gate snapshot

**Recorded:** 2026-10-30 12:15 UTC. **Single scenario candidate:** [PR #185](https://github.com/alimtalbi-ata/aiops/pull/185) draft, head `5782d6fcece32cfd38ada0d50bfe68a8b74bd164`. **Overall: RELEASE_STABLE=NO_GO.**

## Exact selective integration

| Lot | Source HEAD | Files copied as exact Git blobs |
|---|---|---|
| 1/5 | `f50d3dac3182fd5d7c2bc5cb9ba8cf1bbba486ca` | `tools/find_acme_demo_run.py`, `tests/test_acme_core_authenticated_probe.py` |
| 2/5 | `ca6feab123d552c32ea707620a9176757b88b822` | `app/portal/main.py`, `tests/test_demo_v2.py` |
| 3/5 | `18ff72e312d5af5c2df239b646de18c16c4c534c` | `app/shared/acme_itsm_evidence_link.py`, `tests/test_acme_noc_glpi_join.py` |
| 4/5 | `901c5bb86922504ef447609e5a286c783cf8060b` | `app/shared/acme_policy_demo_result.py`, `tests/test_acme_policy_demo_result.py` |

One 5/5 commit, no `demo_v2.py` overwrite, no new release PR, no stable/main mutation. The #185 PR base is `feat/cron-stable-reconciled-20261028`, **not** `main`; its 72-file diff must not be merged wholesale.

## CI gates at this snapshot

- New SHA V2.8 isolated [41053319372](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319372): **FAILED** in `static-and-unit`, 59 tests / 1 error, `test_v28_portal_ui.PortalPageContractTests.test_demo_live_trace_is_source_backed`. Legacy fixture expects `response["gates"]["decision"]`, whereas the scoped Core gate reader now returns `{"items":[...]}` or `{"status":"UNKNOWN"}`. Do not relax identity checks; ask 2/5 to update fixture and add regression tests.
- New SHA Quality [41053319020](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319020): **IN_PROGRESS** at snapshot (five jobs SUCCESS, release-kit pending). Do not count pending as PASS.
- New SHA Historical [41053319033](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319033) and Offline [41053318999](https://github.com/alimtalbi-ata/aiops/actions/runs/41053318999): SUCCESS.
- #193 [41024125286](https://github.com/alimtalbi-ata/aiops/actions/runs/41024125286): targeted rerun 6/6 SUCCESS after pip transport `IncompleteRead`; this qualifies only that PR head.
- Local older operator archive `02dd3aa`: selected regression suite **193/193 PASS** and AI harness **3/3 PASS**. **Not** tests of the new `5782d6f` commit.

## Deployment and demo proof boundary

- `deploy/aiops2-stable` is exactly `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (0 ahead / 0 behind).
- Stable `deploy/deploy-demo-studio-v2.sh` copies only `app/portal/demo_v2.py` and `tests/test_demo_v2.py`, then patches `app/portal/main.py` locally. The candidate `deploy/poll-approved-deploy.sh` accepts only stable and refuses unsupported transport; it is not a four-image release path.
- Local preview on the *older* archive can be launched with `python3 scripts/check_demo_portal_preview.py --port 17777` from its extracted directory, then viewed at `http://127.0.0.1:17777/demo-studio/business-story`. This is a synthetic local preview, not a deployed customer URL.
- Operator-reported synthetic scenario IDs (not rechecked by this 5/5 run): `SCN-GOLDEN-PAYMENT-P1`, `RUN-73AFC6FF9315376C`, `INC-GOLDEN-P1-1edd0de6f46546e294139bf68d73d65a`. GLPI ticket, observed Payments impact, authenticated Evidence and runtime approval remain UNKNOWN; `INGEST=PENDING` was reported on the older run.
- New SHA CI artifact checksum, exact packaging, `applied.sha`, deployed image digest, Core/GLPI/Evidence authenticated read, Debian smoke and exercised rollback: **NOT_ATTESTED**.

## Decision and operator handoff

**DEMO_LOCAL=GO only for the earlier tested `02dd3aa` archive; NEW_CANDIDATE_CI=FAILED/PENDING; RELEASE_STABLE=NO_GO.** Next: 2/5 fixes the test fixture without weakening fail-closed checks; 5/5 integrates a new exact SHA, reruns all CI, validates the cumulative kit and obtains separately authorized read-only Debian preflight and rollback evidence.

#188 is the preferred daily quality + 15-minute read-only smoke design; #189 is a duplicate unmerged two-hour full quality cron. #146/#153 auto-deploy stays disabled, #187 new observability stack deferred. No merge, deployment, runner installation, cron change, LIVE action or host access was performed.


## 2026-10-30 12:20 UTC — completed exact-head gates and package inspection

- [Quality #41053319020](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319020) has now **completed SUCCESS, 6/6 jobs**. [V2.8 #41053319372](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319372) remains **FAILED** (58 passing tests, one error), so overall release gate remains **NO-GO**.
- Downloaded exact Quality artifact `12975971501` (outer ZIP SHA256 `5997c458a6d77ecd50796ce65aa8745c0bd8e01c4721776366f508194d9d70da`). Inner deployment kit SHA256 `af627c8af804eec25e643e7b3a7169bb6e513ee6cae8687c18bc4c47c2c0aa5d` matched its sidecar; **445/445 CRC**, `sha256sum -c FILES-SHA256SUMS` **395/395 PASS**, all eight source Git blobs matched the new commit.
- Actual tests on the **new exact package**: `PYTHONPATH=app:tests python3 -m unittest tests.test_initial_stage_state tests.test_demo_v2 tests.test_acme_core_evidence_refs_read tests.test_acme_policy_demo_result tests.test_acme_glpi_ticket_read tests.test_deploy_acme_p0 tests.test_find_acme_demo_run tests.test_portal_preview_readonly tests.test_acme_core_authenticated_probe tests.test_acme_noc_glpi_join tests.test_acme_itsm_evidence_link -q` → **253/253 PASS**; `python3 -m compileall -q app tests` PASS; `python3 -m unittest discover -s tests -p 'test_v28_*.py' -q` → **58/59 PASS, one KeyError**.
- Isolated loopback-only preview of the exact package: **14/14 GET routes HTTP 200** (`/`, `/runs`, `/timeline`, `/twin`, `/evidence`, `/policy`, `/copilot`, `/demo-studio`, `/demo-studio/business-story`, `/qualification`, `/qualification-lab`, `/acme-stories`, `/policy-control`, `/policy-story`); POST `/api/demo` **405**; unavailable run detail **404**. This is offline SIMULATED/UNKNOWN, not Core/GLPI/Evidence runtime proof.
- PR #185's base branch diverges from `main`: **672 ahead / 43 behind**, 272 changed paths in the branch comparison. Direct main merge is not a safe release operation; require a reviewed clean-main selective integration strategy.


## 2026-10-30 12:30 UTC — 5/5 scoped-gates regression repair — V2.8 regression gate recovered

**Current #185 head:** `2b2af9cd21e48be741a3906b7a12cfffa3371f7b` (one test fixture changed). Previous head `5782d6f` V2.8 FAILED 58/59. Exact new-head [V2.8 41055650146](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650146) **SUCCESS 2/2 jobs**, [Offline 41055650247](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650247) SUCCESS, [Historical 41055650640](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650640) SUCCESS; [Quality 41055650123](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650123) **IN_PROGRESS** at recording. Locally patched extraction of the *previous* #185 artifact passed `PYTHONPATH=app:tests python3 -m unittest discover -s tests -p 'test_v28_*.py' -q` **59/59** and selected 11-module unittest suite **253/253**; new SHA packaging NOT_YET_VERIFIED.

Main-based #197/#198/#199 are small and individually Quality-green; 2/5's main-based Portal is blocked by missing route/contract. #196 latest head Quality plus V2.8/Offline/Historical SUCCESS, but is stacked on #194. Two audited RC1.4 ZIPs are incomplete. #185 branch diverges 741 ahead / 43 behind main; never merge wholesale. Cron #188 preferred, #189 duplicate inactive, #146/#153 disabled, #187 deferred. **Single decision: DEMO_LOCAL=GO (prior synthetic archive only); RELEASE_STABLE=NO_GO.** No `applied.sha`, host smoke, GLPI runtime proof, full kit or exercised rollback.


## 2026-10-30 12:32 UTC — final exact-head CI and kit inspection — all CI gates green, cumulative kit still blocked

**#185 `2b2af9cd21e48be741a3906b7a12cfffa3371f7b`:** Quality 41055650123 **6/6 SUCCESS**; V2.8 41055650146 **2/2 SUCCESS**; Offline 41055650247 and Historical 41055650640 SUCCESS. New artifact `12976991134`: 445/445 ZIP CRC, 395/395 SHA256, corrected test blob verified. On new archive: V2.8 59/59, selected 253/253, compileall PASS, local read-only smoke 14/14 GET 200, POST 405, unknown run 404. **Kit completeness NO-GO** (no migration 011, OIDC/HITL verifier, #196 telemetry or architecture docs). Exact source remains on divergent #185 branch, not clean-main. Debian `applied.sha`, host smoke, GLPI authenticated proof, upgrade and rollback remain NOT_ATTESTED. #195 docs CI 41055915595 SUCCESS on previous docs SHA `fe4e92f`. **DEMO_LOCAL=GO (synthetic only), RELEASE_STABLE=NO_GO.**

### 2026-10-30 13:12 UTC — refreshed exact-head gates

- #185 `2b2af9cd21e48be741a3906b7a12cfffa3371f7b`, base `feat/cron-stable-reconciled-20261028` (`e5c6b030c374e47f64678f425df78cd147335eec`), **741 ahead/43 behind main**: no direct merge. [Quality 41055650123](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650123) 6/6 SUCCESS; [V2.8 41055650146](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650146), [Offline 41055650247](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650247), [Historical 41055650640](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650640) SUCCESS.
- Rechecked locally from fresh extraction of the exact inner ZIP: SHA256 `3ff78df871c3e32b72d1f9c4d077cee0301b5aeeb3dae0edab20a415719fc2aa`; `unzip -t` 445/445 intact, `sha256sum -c FILES-SHA256SUMS` 395/395 PASS, `PYTHONPATH=app:tests python3 -m unittest discover -s tests -p 'test_v28_*.py' -q` 59/59 PASS, `python3 -m unittest discover -s tests -p 'test_ai_eval_harness.py' -q` 3/3 PASS.
- **Cumulative kit FAIL:** inspected ZIP lacks migration `011_hitl_decision_outbox.sql`, OIDC `app/core/hitl_identity.py` and `app/shared/hitl_identity.py`, AI telemetry implementation doc and #195 architecture/story/cron docs. The evaluator is present but not the integrated #196 source.
- #197 `bd86faa` Quality 41057515083 SUCCESS, #198 `8f48b1b` Quality 41054868177 SUCCESS, #199 `e0fc68f` Quality 41055154260 SUCCESS: independent main-based patches, not cumulative integration. 2/5 remains blocked by absent main Portal run-detail route.
- Default `main` Quality YAML has no schedule; #188 daily `23 2 * * *` plus 15-minute read-only smoke preferred after approval; #189 duplicate `23 */2 * * *` unmerged. #146/#153 auto-deploy disabled.
- **GO/NO-GO:** `DEMO_LOCAL=GO_SYNTHETIC`, `CUMULATIVE_KIT=NO_GO`, `RELEASE_STABLE=NO_GO`. No deployed `applied.sha`, authenticated GLPI/Evidence smoke, four-image Debian install or exercised rollback attested.

<!-- convergence-5of5-477da60-20261030 -->
## Gate snapshot — 2026-10-30T16:15:33.055Z

**Audit UTC:** 2026-10-30T16:15:33.055Z. **Release candidate:** [#201](https://github.com/alimtalbi-ata/aiops/pull/201), base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, exact HEAD [`477da60d92dc777e1e635eea4c5510c350a5d90c`](https://github.com/alimtalbi-ata/aiops/commit/477da60d92dc777e1e635eea4c5510c350a5d90c), **28 ahead / 0 behind**, draft and unmerged. [Exact-head Quality 41088096834](https://github.com/alimtalbi-ata/aiops/actions/runs/41088096834) **QUEUED** at audit; previous #201 [Quality 41082715412](https://github.com/alimtalbi-ata/aiops/actions/runs/41082715412) **3/3 SUCCESS** on old `59ba22f1`, not on this new SHA.

| Tier | Verdict | Evidence / next exact gate |
|---|---|---|
| T0 tests | PENDING on new HEAD | #201 Quality 41088096834 QUEUED; old-head 3/3 is not transferable; targeted Python/JS suites wired |
| T1 ephemeral integration | NOT_TESTED | Authenticated one-tenant Core/Portal/Temporal/Evidence contract probe in isolated environment |
| T2 synthetic E2E | NOT_TESTED | One ACME SAN→Payments Incident/Run across 14 ITIL checkpoints, capture IDs and independent receipts |
| T3 deployed read-only | NOT_ATTESTED | Operator-only image digest, `applied.sha`, read-only smoke |
| T4 sandbox kit/rollback | NO-GO | Missing migration 011/OIDC/AI telemetry; no cumulative ZIP or rollback exercise |
| T5 LIVE | NO-GO | Explicit separate authorization and all gates absent |

#188 daily quality + 15-minute read-only runtime smoke remains preferred but unmerged; #189 duplicate. No runner, cron, Debian, GLPI, main/stable, deployment or LIVE action.

## Gate refresh — 2026-10-30 17:08 UTC

- Candidate #201: `main@27deb9b1a66faf27df8d69b137a63451f7649d80` → `1d3a902877d556549425a95cd4cef792c5c000c8` (29/0 ahead/behind). Portal exact source blob from #202 restored; prior Quality 41088096834 FAILURE 2/3, new [Quality 41096370024](https://github.com/alimtalbi-ata/aiops/actions/runs/41096370024) IN_PROGRESS. **T0=PENDING**.
- #195 previous [Quality 41088268202](https://github.com/alimtalbi-ata/aiops/actions/runs/41088268202) 3/3 SUCCESS at `38e3edc0`; new documentation head requires its own CI.
- #196 [Quality 41083049858](https://github.com/alimtalbi-ata/aiops/actions/runs/41083049858) 6/8 SUCCESS, 2 Ollama FAIL, no qualified model inference. #198 [Quality 41093598267](https://github.com/alimtalbi-ata/aiops/actions/runs/41093598267) 3/3 SUCCESS on synthetic fixture tests.
- **T1=NOT_TESTED; T2=NOT_TESTED; T3=NOT_ATTESTED; T4=NO_GO; T5=NO_GO. RELEASE_STABLE=NO_GO.** No cumulative ZIP, migration 011/OIDC/outbox/AI telemetry, authenticated tenant Evidence/GLPI links, sandbox rollback or host attestation. #188 remains preferred unmerged, #189 duplicate, #146/#153 disabled, #187 deferred.

### CI resolution — 2026-10-30 17:11 UTC

New #201 head `1d3a902877d556549425a95cd4cef792c5c000c8`: [Quality 41096370024](https://github.com/alimtalbi-ata/aiops/actions/runs/41096370024) **COMPLETED SUCCESS 3/3**, with Portal Python 26/26, JS 7/7, locator 16/16, ACME fixture 6/6, Chromium 6/6, kit-gate 12/12. Exact head and source blob `0dac60be` verified. **T0=GO (isolated CI only)**; T1/T2 NOT_TESTED, T3 NOT_ATTESTED, T4/T5 NO_GO, `RELEASE_STABLE=NO_GO`. A successful Chromium fixture does not qualify an authenticated Core/Temporal/GLPI/Evidence chain or cumulative rollback.



## 2026-10-30 19:10 UTC — exact-head gate refresh

- Candidate #201 base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, new HEAD `7e4cbe9d75aedccf2078ca50d052e6d0796c284e` (33 ahead/0 behind). Ported only two exact source/test blobs from #202 to mark ACME story SYNTHETIC on 200/401/403/503. Source #202 Quality 41109683748 SUCCESS; previous #201 HEAD `7bc825b3` Quality 41104533241 SUCCESS 3/3. **New candidate exact-head CI PENDING / NOT_OBSERVED**.
- #196 real-model benchmark FAILURE; #204 stacked failure-injection CI green but no runtime identity/ACK/restart proof. #201 synthetic story artifact `12999887492` is not a cumulative kit; no new archive member audit.
- **T0 PENDING** on new head; **T1 NOT_TESTED**, **T2 NOT_TESTED** full Core/Temporal/Evidence E2E, **T3 NOT_ATTESTED**, **T4 NO_GO**, **T5 NO_GO**. No stable/main push, merge, Debian change, GLPI write, or LIVE. Next: exact-head Quality; ephemeral authenticated E2E; cumulative ZIP member/checksum/manifest audit and sandbox install/rollback.


### 2026-10-30 19:13 UTC — T0 closeout

#201 `7e4cbe9d75aedccf2078ca50d052e6d0796c284e` [Quality 41113172965](https://github.com/alimtalbi-ata/aiops/actions/runs/41113172965) **SUCCESS 3/3**; inspected logs: Portal Python 28/28, JS 7/7, Chromium 6/6, kit gate 12/12. Synthetic artifact `13005150615` digest `sha256:6fdaab4220604c401c531999907df55e0a54d713920537ca22f5dfac2886bf69` listed only, contents NOT_AUDITED. **T0 GO_LIMITED; T1 NOT_TESTED; T2 NOT_TESTED; T3 NOT_ATTESTED; T4 NO_GO; T5 NO_GO.**


### 2026-10-30 19:16 UTC — new provenance-contract commit

#201 advanced from CI-green `7e4cbe9d` to **`cee6a834befbee47275e83651e7c0955528c51a0`** (base `main@27deb9b1`, 35 ahead/0 behind). Two narrow changes in `.github/workflows/quality.yml` and `tests/test_explore_story_playwright_e2e.py` separate PR source/base SHAs from merge checkout SHA in synthetic capture metadata. Previous artifact `13005150615` independently inspected (2/2 CRC, screenshot hash PASS), but its `git_sha` was merge checkout, not source. **New exact-head Quality NOT_OBSERVED**; T0 PENDING until CI. T1/T2 NOT_TESTED, T3 NOT_ATTESTED, T4/T5 NO_GO.


### 2026-10-30 19:20 UTC — final exact-head source/checkout verification

#201 `cee6a834befbee47275e83651e7c0955528c51a0` [Quality 41113479815](https://github.com/alimtalbi-ata/aiops/actions/runs/41113479815) SUCCESS 3/3; Portal Python 28/28, JS 7/7, Chromium 6/6, kit gate 12/12. Artifact `13004397285` downloaded: ZIP SHA256 `7f1821aefdbc687601bc2ae62163a7e777df03e8d6d939031880cead20b6ab93`, 2/2 CRC, screenshot checksum PASS; metadata source `cee6a834`, base `27deb9b1`, checkout `73a71c76` distinct, runtime authenticated=false. **T0 GO_LIMITED; T1/T2 NOT_TESTED; T3 NOT_ATTESTED; T4/T5 NO_GO.**

## 2026-10-31 5/5 exact-source security checkpoint

#201 main-based `f38014c92b85763be8ac3f72042b50a48dbba95c` includes exact #202 `f3943020d0d66d60c92dbf9b0d0c3fbb7913789e` Portal/test blobs; source Quality 41142124145 SUCCESS 3/3, combined new HEAD CI NOT_OBSERVED at port. Shared-bearer Core Run reads now fail closed at 503 UNKNOWN without disclosing Run/Incident/status until server-derived actor+tenant ACL is qualified. This is a security containment fix, not authorization. T0 pending combined SHA; T1 BLOCKED on Core actor/tenant exact-Run ACL, T2 NOT_TESTED, T3 NOT_ATTESTED, T4 NO_GO, T5 NO_GO. #196 model benchmark still FAILURE; #204 stacked success not integrated. `RELEASE_STABLE=NO_GO`. No LIVE/host/GLPI write.

### 2026-10-31 exact-head CI release decision

#201 `f38014c92b85763be8ac3f72042b50a48dbba95c` [Quality 41145124544](https://github.com/alimtalbi-ata/aiops/actions/runs/41145124544) SUCCESS 3/3; Portal fail-closed tests 30/30, JS 7/7, Chromium synthetic 6/6, kit guard 12/12. **T0 GO_LIMITED**, not T1 authorization. T1 BLOCKED (Core actor+tenant ACL missing), T2 NOT_TESTED, T3 NOT_ATTESTED, T4 NO_GO, T5 NO_GO; `RELEASE_STABLE=NO_GO`. Artifact `13020710411` listed, not inspected. No deployment or LIVE.


### 2026-10-31 5/5 gate refresh — tenant existence oracle remains

- Exact #201 `f38014c92b85763be8ac3f72042b50a48dbba95c`, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, [Quality 41145124544](https://github.com/alimtalbi-ata/aiops/actions/runs/41145124544) SUCCESS 3/3. Exact #195 prior `057d99351921f30beeb4e6ab4158f841dccf1a15`, [Quality 41145381815](https://github.com/alimtalbi-ata/aiops/actions/runs/41145381815) SUCCESS 3/3. No cumulative kit qualification.
- **BLOCKER (source review):** despite identity-field redaction, #201 Portal differentiates a valid internal Core Run from an absent/unqualified one via 503 reason/connection state. [#202 owner handoff](https://github.com/alimtalbi-ata/aiops/pull/202#issuecomment-6536560492) requests identical unqualified viewer responses and negative API/HTML tests; actor+tenant Core exact-Run ACL remains missing. No runtime cross-tenant exploit test performed.
- T0 **GO_LIMITED** (isolated CI); T1 **BLOCKED** (tenant ACL + non-enumerability); T2 **NOT_TESTED** (single Incident/Run Core→Temporal→Evidence); T3 **NOT_ATTESTED**; T4 **NO_GO** (kit/install/rollback); T5 **NO_GO** (LIVE). `RELEASE_STABLE=NO_GO`. #196 real Ollama still FAIL; #204 stacked HITL tests do not promote release. No Debian, GLPI write or deployment.

## 2026-10-31 UTC — exact-head gate correction

| Gate | Status | Evidence / blocker |
|---|---|---|
| T0 candidate #201 | PENDING NEW HEAD | `e6f9ad656d3b6f92ef065f7aec13f3d1b2ca3d74`, [Quality 41155594473](https://github.com/alimtalbi-ata/aiops/actions/runs/41155594473) IN_PROGRESS when checked; preceding `f38014c9` Quality 41145124544 SUCCESS 3/3 only |
| T1 authenticated tenant integration | BLOCKED | Shared bearer bootstrap now fails closed; exact-Run `connection_state` oracle, Core actor+tenant authorization and NOC tenant correlation remain unqualified |
| T2 single ACME Incident/Run Temporal/Evidence/Policy E2E | NOT_QUALIFIED | #204 [Quality 41153751242](https://github.com/alimtalbi-ata/aiops/actions/runs/41153751242) runtime-e2e FAILED: `RUN-E9872B4B3AF4065E` RUNNING, no Analyst/Critic/Policy records; 0 effects |
| T3 Debian read-only | NOT_ATTESTED | No authorized Debian/runner access |
| T4 cumulative kit + sandbox rollback | NO-GO | No exact-main-based cumulative migration 011/OIDC/AI package or exercised install/upgrade/rollback |
| T5 LIVE | NO-GO | No identity, executor fencing, runtime HITL/outbox or operator approval |

The #204 failure artifact `13024756054` was downloaded and inspected: 633-byte ZIP, SHA256 `01f97936ab67e68c4864ad1384d411a452fb78c57dcaeb4bdd6784bb3d719f6e`, CRC PASS, one JSON report, `result=FAIL`, `effect_receipts=0`. No production claim. `RELEASE_STABLE=NO_GO`.

### Exact-head CI recheck — 2026-10-31 UTC

#201 `e6f9ad656d3b6f92ef065f7aec13f3d1b2ca3d74`: [Quality 41155594473](https://github.com/alimtalbi-ata/aiops/actions/runs/41155594473) **COMPLETED SUCCESS 3/3 jobs** (policy-and-static, core-postgres-noc-real-integration, grafana-real-integration). Logs: Portal bootstrap HTTP **6/6**, Run API/HTML **32/32**, Run-link JS **8/8**, bootstrap DOM JS **5/5**, Chromium synthetic **6/6**, cumulative-kit guard **12/12**. T0 **GO limited** on this exact head; **T1 still BLOCKED**, T2 NOT_QUALIFIED, T3 NOT_ATTESTED, T4/T5 NO-GO.

[Artifact 13024589352](https://github.com/alimtalbi-ata/aiops/actions/runs/41155594473/artifacts/13024589352) downloaded and inspected: ZIP 237,689 bytes, SHA256 `451544e07a6da6a5284705fad6947cf5c1be3b917c1a1dfbb7e6fe93c9ea5b87`, 2/2 ZIP members CRC PASS; screenshot PNG SHA256 `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca` matches metadata. `source_head_sha=e6f9ad65…`, `base_sha=27deb9b1…`, `checkout_sha=58c8d9b5…`, `runtime_authenticated=false`, `glpi_ticket_id=null`, `production_qualified=false`. This is a CI-simulated screenshot, **not** a T2 runtime receipt or cumulative kit.

### 2026-10-31 02:28 UTC — stacked Temporal recovery verified, candidate release unchanged

[#204](https://github.com/alimtalbi-ata/aiops/pull/204) HEAD `fb05a75e48827fec38d30a15532a6549492ebf45` (base #194 `40d38705cf2bde3be6052340442c117a81908f65`): [Quality 41158324110](https://github.com/alimtalbi-ata/aiops/actions/runs/41158324110) **SUCCESS 6/6**, including Docker/Temporal runtime-e2e. [Artifact 13026113139](https://github.com/alimtalbi-ata/aiops/actions/runs/41158324110/artifacts/13026113139) independently downloaded: ZIP SHA256 `58186c794a3e90a7e63b2b1f48e4bc4e20b15468b548e1873de07597b66d34f2`, 2/2 CRC PASS. Synthetic `RUN-95D829080D737810` RESOLVED, 1 Analyst, 1 Critic, 1 Policy `PASS|SIMULATE`, 12 Evidence, **0 effect receipts**. CI deterministic AI fixture 5/5 PASS, not real Ollama. This supersedes the *stacked-branch* failure at #204 `8aded617` but **does not qualify #201 main-based T2**, GLPI, tenant ACL, worker restart/lost ACK or sandbox rollback.

#201 exact HEAD `e6f9ad656d3b6f92ef065f7aec13f3d1b2ca3d74`, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, [Quality 41155594473](https://github.com/alimtalbi-ata/aiops/actions/runs/41155594473) SUCCESS 3/3. #202 HEAD `eb7bd709106695e05fd80e241cdd6a22265ba535` [Quality 41158529106](https://github.com/alimtalbi-ata/aiops/actions/runs/41158529106) SUCCESS 3/3; same `acme_run_detail.py` blob as #201, so Run-existence `connection_state` disclosure remains source-observed. #196 `747f0df4` Ollama evaluator FAILURE, 0 qualified repeats. #195 previous exact HEAD `6af61a6099cabc4dfd725d58fb84ff56366a97cb` [Quality 41155714529](https://github.com/alimtalbi-ata/aiops/actions/runs/41155714529) SUCCESS 3/3; new docs HEAD CI pending.

| Gate | Decision | Reason |
|---|---|---|
| T0 | GO_LIMITED | #201 exact-head isolated CI SUCCESS |
| T1 | BLOCKED | Core-owned actor+tenant exact-Run ACL and indistinguishable unqualified Run responses missing |
| T2 | NOT_QUALIFIED | #204 stacked synthetic E2E PASS; not ported/tested on #201, no complete ACME 14-checkpoint receipt |
| T3 | NOT_ATTESTED | Debian runner/runtime access unavailable |
| T4 | NO_GO | No main-based cumulative install/upgrade/rollback exercised |
| T5 | NO_GO | No independent LIVE authorization or effect qualification |

`RELEASE_STABLE=NO_GO`. No merge, main push, Debian/runner/cron, GLPI write or LIVE action.


### 2026-10-31 03:27 UTC — fail-closed Run response normalization, exact CI pending

#201 main-based `a5bdb5bfeb8a05bd761cba7268b9c6ffc8fc3b95` (base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`), two targeted commits `647ced1057891d5c88395c2226b486e765ad976f` and `a5bdb5bfeb8a05bd761cba7268b9c6ffc8fc3b95`: Portal Run API/HTML 503 responses for valid, absent, foreign/malformed and timeout Core reads are source-normalized to `UNKNOWN/TENANT_ACL_NOT_QUALIFIED`, `connection_state=UNKNOWN`, `source=UNKNOWN`; one five-scenario negative test added. 401/403 authentication denials preserved. This is **not** Core actor+tenant authorization; upstream auth-status and timing side channels are not qualified. New exact-head Quality **NOT_OBSERVED** at this write; previous `e6f9ad65` Quality 41155594473 SUCCESS 3/3 remains historical T0 only.

#195 previous `cb19bbe5` Quality 41160220790 SUCCESS 3/3. #202 `2f49443e` Quality 41162565031 SUCCESS 3/3 (older Run blob). #204 stacked `b4198e1e` Quality 41162880436 SUCCESS 6/6, not a main-based E2E. #196 `747f0df4` Quality 41083049858 FAILURE, zero scored Ollama repeats.

| Gate | Decision | Basis |
|---|---|---|
| T0 | PENDING | New #201 source SHA requires exact-head CI; prior SHA GO_LIMITED |
| T1 | BLOCKED | Core-owned actor+tenant exact-Run ACL absent; no authenticated isolated integration |
| T2 | NOT_QUALIFIED | No complete 14-checkpoint ACME single-Run receipt on #201 |
| T3 | NOT_ATTESTED | No Debian host/runner access |
| T4 | NO_GO | No main-based cumulative install/upgrade/rollback sandbox exercise |
| T5 | NO_GO | No independent LIVE authorization/effect attestation |

`RELEASE_STABLE=NO_GO`. No merge, main push, Debian/cron/runner, GLPI write or LIVE.


### 2026-10-31 03:31 UTC — exact-head T0 green; T4 semantic-manifest blocker

#201 HEAD `a5bdb5bfeb8a05bd761cba7268b9c6ffc8fc3b95`, [Quality 41164572871](https://github.com/alimtalbi-ata/aiops/actions/runs/41164572871) **SUCCESS 3/3**: Portal Run Python **33/33**, synthetic Chromium **6/6**, kit guard **12/12**. Artifact 13028322111 ZIP SHA256 `8b8a295aee139c573cca1ca38577d9b00da4a59c3c9aac93ab1e11fd095f615b`, 2/2 CRC PASS, source/base/checkout separated, runtime unauthenticated. This proves response-level negative fixtures, **not Core actor+tenant authorization** or complete T2.

#204 stacked HEAD `b4198e1e` [Quality 41162880436](https://github.com/alimtalbi-ata/aiops/actions/runs/41162880436) SUCCESS 6/6. Its independently inspected nested kit artifact 13027198980: outer SHA256 `52bcc27148aa31c7cccce88823f3ef42c2fbec11ba838aaa6be72edda3f2bacf`, nested SHA256 `18255dab2e157c6671b077c18a4143309f83b2fb1eaeb2c37618e07829492e48`; generated `FILES-SHA256SUMS` 406/406 PASS, but embedded `manifests/MANIFEST.json` **30/68 digests mismatch** and release version conflicts with `RELEASE-MANIFEST.txt`. Extraction/repack 407/407 hashes PASS, install/rollback NOT_TESTED, SBOM absent. T4 remains NO_GO. #195 prior `71401ccf` Quality 41164604179 SUCCESS 3/3; any newer docs SHA requires new exact-head CI.

| Gate | Decision | Evidence |
|---|---|---|
| T0 | GO_LIMITED | #201 exact-head Quality 3/3 and 33/33 Portal Run tests |
| T1 | BLOCKED | No Core actor+tenant exact-Run ACL; timing/upstream auth distinctions not qualified |
| T2 | NOT_QUALIFIED | No integrated main-based ACME 14-checkpoint single Run |
| T3 | NOT_ATTESTED | No Debian access |
| T4 | NO_GO | No cumulative #201 kit; #204 manifest mismatch; no install/rollback |
| T5 | NO_GO | LIVE authorization/effect gates absent |

`RELEASE_STABLE=NO_GO`. No merge, main push, host changes, GLPI write or LIVE.

### 2026-10-31 ~04:35 UTC — 5/5 release gate

- T0: PENDING #201 new exact HEAD `e116d04c791b6f5a5028d6f2cc3797a547b460ec` [Quality 41169101273](https://github.com/alimtalbi-ata/aiops/actions/runs/41169101273); prior `a5bdb5bf` SUCCESS 3/3 only.
- T1: BLOCKED (Core-owned actor+tenant exact-Run ACL and isolated authenticated negative integration). T2: NOT_QUALIFIED on main-based combined ACME. T3: NOT_ATTESTED Debian.
- T4: NO_GO. #204 stacked [artifact 13029760540](https://github.com/alimtalbi-ata/aiops/actions/runs/41166983844/artifacts/13029760540) 406/406 SHA256SUMS PASS but **30/68 embedded manifest hashes mismatch**, release version conflicts, no SBOM/install/upgrade/rollback. New #201 source guard validates these semantics; exact-head CI pending and no kit built.
- T5: NO_GO. #196 Ollama 0 qualified repeats, no real-model quality or cost claim. `RELEASE_STABLE=NO_GO`. No merge, host/runner/cron/GLPI write or LIVE effect.

### Exact #201 quality closeout — 2026-10-31 04:36 UTC

[Quality 41169101273](https://github.com/alimtalbi-ata/aiops/actions/runs/41169101273) for #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec` **SUCCESS 3/3**, with **16/16** cumulative-kit guard tests PASS, **33/33** Portal Run tests PASS and **6/6** Chromium synthetic PASS. **T0 GO_LIMITED only.** The real #204 kit's embedded 30/68 mismatches are not repaired by these guard tests; T4 NO_GO until rebuilt, semantic hashes verified and sandbox rollback exercised. T1 BLOCKED actor+tenant ACL; T2 NOT_QUALIFIED; T3 NOT_ATTESTED; T5 NO_GO. `RELEASE_STABLE=NO_GO`.

### 2026-10-31 07:27 Europe/Paris — exact-source gate and staged manifest port

#195 previous HEAD `8aa0e9cc666e13b1ccced822e40e2af47f15945f` Quality 41173191433 SUCCESS 3/3. #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec` (main base `27deb9b1a66faf27df8d69b137a63451f7649d80`) Quality 41169101273 SUCCESS 3/3, 16/16 kit-guard negatives; no install kit. #206 `516e32b1540077ab059f651d78020c2b365b3fd4` Quality 41172956555 SUCCESS 6/6 and artifact 13031961877 semantic integrity 68/68 embedded, 407/407 sidecar, but stacked only. #196 `747f0df4` real Ollama evaluator FAILURE (0 valid repeats).

[New draft #207](https://github.com/alimtalbi-ata/aiops/pull/207) exact HEAD `0d0984cd2c8cf9fd5e934a4efb455d788cd5c6af`, based on #201, selectively adds staged inventory refresh, symlink-parent refusal, 11 isolated tests and CI step. Exact-head Quality NOT_OBSERVED at initial check; this is preparatory code only, **not** a packaged cumulative release. No source/base/checkout provenance attestation, SBOM, install/upgrade/rollback receipt.

| Gate | Decision |
|---|---|
| T0 | GO_LIMITED on exact #201 Quality; #207 PENDING |
| T1 | BLOCKED — Core actor+tenant exact-Run authorization absent |
| T2 | NOT_QUALIFIED — no combined 14-step single ACME Run on main-based SHA |
| T3 | NOT_ATTESTED — no Debian read-only access |
| T4 | NO_GO — no main-based kit with exercised install/upgrade/rollback |
| T5 | NO_GO — no LIVE identity, execution or change authorization |

`RELEASE_STABLE=NO_GO`. No main merge, Debian/runner/cron, GLPI write or LIVE effect.


**#207 exact CI closeout:** [41176811268](https://github.com/alimtalbi-ata/aiops/actions/runs/41176811268) SUCCESS 3/3 on `0d0984cd2c8cf9fd5e934a4efb455d788cd5c6af`; staged helper 11/11 tests and independent existing kit gate 16/16 PASS. Artifact 13033831546 ZIP SHA256 `438abee56ab02f01bf8f68bf947579c071e8d695fd55607f23526a80511fcc2b`, CRC 2/2, PNG digest matches; source/base/checkout `0d0984cd`/`e116d04c`/`6e03940a`, unauthenticated synthetic browser only, GLPI null. This raises only **T0 isolated helper qualification**, not main-based kit T4, T1 actor+tenant, T2 single Run, T3 Debian or T5 LIVE. `RELEASE_STABLE=NO_GO`. #195 prior `e4fcd656` Quality 41176846589 SUCCESS; new docs SHA CI pending.

### 2026-10-31 ~09:40 Europe/Paris — manifest provenance convergence and latest package integrity stop-line

- #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec` main-based Quality 41169101273 SUCCESS 3/3; #207 `0d0984cd2c8cf9fd5e934a4efb455d788cd5c6af` Quality 41176811268 SUCCESS 3/3; #208 `dd308475e17e1c5315da6b3caf73fba42e0e647a` Quality 41181004360 SUCCESS 3/3. New [draft #209](https://github.com/alimtalbi-ata/aiops/pull/209) HEAD `9d515aee54a809bf06d81d63609b06d7b7a7e571` base #207, two changed files, reconciles staged embedded MANIFEST regeneration with strict exact-source-member guard, three new regressions. [Quality 41185345014](https://github.com/alimtalbi-ata/aiops/actions/runs/41185345014) IN_PROGRESS; no new test PASS claimed.
- #204 stacked `aa24982c8c93f017b710dc7658e66728ad86fbde` Quality 41182602889 SUCCESS 6/6, but latest artifact 13035548118 independent audit: outer SHA256 `c817374ad19cf092d5d3abe57b32f5a53661354c1d233b0618b38e1af437f8f6`, inner SHA256 `c16c30f0808ec97885295271fa1b0a63a6187b92ada3f9554fe5adbd5d4696e1`; sidecar 407/407 PASS, embedded 30/68 SHA and sizes FAIL, release version mismatch. No main-based cumulative ZIP, install/upgrade/rollback or SBOM qualified.
- Gates: **T0 GO_LIMITED** on #201/#207/#208 exact CI, #209 PENDING; **T1 BLOCKED** Core actor+tenant exact-Run ACL plus Portal routes; **T2 NOT_QUALIFIED** ACME single-Run 14-step integrated E2E; **T3 NOT_ATTESTED** Debian; **T4 NO_GO** kit/rollback; **T5 NO_GO** LIVE. `RELEASE_STABLE=NO_GO`. No main merge/push, Debian/cron/runner, GLPI write or LIVE effect.

**#209 exact-head qualification (2026-10-31 ~09:42 Europe/Paris):** [Quality 41185345014](https://github.com/alimtalbi-ata/aiops/actions/runs/41185345014) SUCCESS 3/3 on `9d515aee54a809bf06d81d63609b06d7b7a7e571`; offline kit source/manifest guard 22/22 PASS, staged inventory refresh 11/11 PASS, Chromium synthetic PASS. Artifact 13036877174 ZIP SHA256 `3f6ce92b724e1b7f22c6f9a6bd5b1c48658dedf3a8db5e23663d215c4bf7975b`, CRC 2/2, screenshot SHA matches, runtime auth false, GLPI null. **T0 GO_LIMITED** only; T1 actor+tenant BLOCKED, T2 combined ACME NOT_QUALIFIED, T3 Debian NOT_ATTESTED, T4 kit install/rollback NO_GO, T5 LIVE NO_GO. `RELEASE_STABLE=NO_GO`.


### 5/5 release inventory stop-line — 2026-10-31 10:31 Europe/Paris

- Refreshed #195 main-based `26436048ade4ff4ac20878d33dc89057c32cb2be`, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, [Quality 41185495625](https://github.com/alimtalbi-ata/aiops/actions/runs/41185495625) SUCCESS 3/3. #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec`, [Quality 41169101273](https://github.com/alimtalbi-ata/aiops/actions/runs/41169101273) SUCCESS 3/3. #209 `9d515aee54a809bf06d81d63609b06d7b7a7e571`, [Quality 41185345014](https://github.com/alimtalbi-ata/aiops/actions/runs/41185345014) SUCCESS 3/3, 22/22 source kit tests, 11/11 staged inventory tests. These are T0 contracts, not a main-based cumulative kit.
- **New audit finding:** #209 `tools/check_cumulative_release_kit.py` accepted `deploy/aiops_release.py` as both installation and rollback entrypoint, even though that script's `main()` refuses deploy/rollback and permits read-only audit only. It also accepted `deploy/deploy-acme-p0.py`, a partial four-service transaction, and did not require a separate upgrade entrypoint. File presence could falsely satisfy the entrypoint inventory gate; it never demonstrated exercised install/upgrade/rollback.
- **Targeted [draft #210](https://github.com/alimtalbi-ata/aiops/pull/210):** base #209 `9d515aee54a809bf06d81d63609b06d7b7a7e571`, HEAD `929ce398f5a3ea5660a834baf8bdb63e0bbda8ac`, changes only `tools/check_cumulative_release_kit.py` and `tests/test_cumulative_release_kit_gate.py`. Requires separate explicit install, upgrade and rollback entrypoint families; three negative regression tests cover read-only audit, partial P0 and install-only. [Exact-head Quality](https://github.com/alimtalbi-ata/aiops/actions/runs/41189139337) **IN_PROGRESS at this snapshot**; expected 25 tests, **N/N NOT_YET_OBSERVED**. This is a stricter source inventory gate, not an implemented rollback or a release package.
- #204 stacked current HEAD `08706694d73e7c2a05f7a26d25807e5e4868525d`, [Quality 41186634005](https://github.com/alimtalbi-ata/aiops/actions/runs/41186634005) SUCCESS 6/6 and other observed workflows green. 4/5 reports offline HITL 60/60 and synthetic Temporal E2E, but neither qualifies #201 T2, Core actor+tenant ACL, source provenance or T4 rollback. Latest previously audited #204 package still has 30/68 stale embedded digests; a new package on current #204 HEAD has **NOT** been independently audited here.
- **Gates:** T0 GO_LIMITED #201/#209, #210 PENDING exact CI; T1 BLOCKED actor+tenant Core/Portal; T2 NOT_QUALIFIED one integrated ACME Run; T3 NOT_ATTESTED Debian; T4 NO_GO main-based kit, install/upgrade/rollback; T5 LIVE NO_GO. `RELEASE_STABLE=NO_GO`. No main merge, runner/cron/host, GLPI write or LIVE action.


**#210 exact-head CI and artifact closeout — 2026-10-31 ~10:36 Europe/Paris:** [Quality 41189139337](https://github.com/alimtalbi-ata/aiops/actions/runs/41189139337) **COMPLETED SUCCESS 3/3** on `929ce398f5a3ea5660a834baf8bdb63e0bbda8ac`. Job logs: `python -m unittest discover -s tests -p "test_cumulative_release_kit_gate.py" -v` **25/25 PASS** (three new negative cases), `python -m unittest discover -s tests -p "test_release_inventory_refresh.py" -v` **11/11 PASS**; Core/PostgreSQL and Grafana jobs SUCCESS. [Artifact 13038415494](https://github.com/alimtalbi-ata/aiops/actions/runs/41189139337/artifacts/13038415494) independently downloaded: ZIP 237,689 bytes SHA256 `28adc71f53d7618e9fc21fb3edf04a8143a1d403fe4486de7881929af8c0296c`, 2/2 CRC PASS, PNG SHA matches metadata. Metadata source HEAD `929ce398`, base `9d515aee`, checkout `5e2b7bc6`; `runtime_authenticated=false`, GLPI null, production false. **This artifact is a synthetic browser screenshot, not an installation kit.** #210 T0 GO_LIMITED isolated gate; T1/T2/T3/T4/T5 unchanged, `RELEASE_STABLE=NO_GO`.


### 2026-10-31 ~12:32 Europe/Paris — independent D0-D4 gate checkpoint

- D0 **GO_LIMITED** only on #201 `c19ef9143cdbe51b5c2516cf82421bbfd2526628`, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, [Quality 41195184054](https://github.com/alimtalbi-ata/aiops/actions/runs/41195184054) SUCCESS 3/3 and synthetic browser 6/6. #204 `4626f321e76d45fa5e8ab4ed83c5891fa486376f` isolated [Quality 41195151800](https://github.com/alimtalbi-ata/aiops/actions/runs/41195151800) SUCCESS 6/6 with PG16 DR and 5/5 outbox PostgreSQL SQL. These are **different heads**, not a combined qualification.
- D0 **FAIL** #205 `692649cc9cb1bdbac85d8d5ee5f7ebcf33663089`, base main, [Quality 41195560516](https://github.com/alimtalbi-ata/aiops/actions/runs/41195560516): 2/3 jobs SUCCESS, mandatory Chromium install fails on unsupported ubuntu26.04. Core xref 12/12 HTTP mock, 17/17 projection and 5/5 disposable PostgreSQL tests are not a substitute for full exact-head CI. Migration `009_itsm_xref_read.sql` conflicts in numbering with stacked `009_ai_decision_ledger.sql`; reconcile before port.
- #195 prior [Quality 41193635715](https://github.com/alimtalbi-ata/aiops/actions/runs/41193635715) FAILURE for the same runner issue. The single-file `policy-and-static` Ubuntu 24.04 fix is committed at `ea1a4aa1f4cea42cbe434f00d080eb0f76ce38a8` on #195; **no D0 promotion until final docs exact-head Quality succeeds**.
- D1 **NOT_QUALIFIED**: no disposable same-SHA Core actor+tenant exact-Run authorization + Portal + xref/Evidence. The new #205 tenant-scoped ticket→Run xref is not a generic authorized Run/Evidence read or OIDC/GLPI production readback.
- D2 **NOT_QUALIFIED**: no one-incident/one-Run ACME browser/API E2E on the combined #201 SHA; screenshots are explicitly synthetic and tenant-unattested.
- D3 **NO_GO**: #204 prior kit semantic 30/68 SHA/size mismatch and release version conflict; new head package not independently reaudited absent generator delta. #206 generator and #210 source/entrypoint gate remain distinct. No main-based kit, SBOM qualification or **install/upgrade/rollback receipts (0/0/0)**.
- D4 **NOT_ATTESTED**: no client demonstration sign-off. #196 Quality FAILURE and 0 qualified Ollama repeats; no provider token/cost or model quality claims. Debian host, cron, runner, GLPI write, LIVE remain untouched. **`RELEASE_STABLE=NO_GO`.**

### 2026-10-31 19:32 Europe/Paris — D0-D4 refreshed gate

- **D0 GO_LIMITED (isolated exact-head only):** #201 `4e1dfaf03569a736d59d1b63816a37bc0a604ee3` [Quality 41227486309](https://github.com/alimtalbi-ata/aiops/actions/runs/41227486309) SUCCESS 3/3; #198 `878e190cdcc6dc219ce3910076b0016b1963e17e` [41227577051](https://github.com/alimtalbi-ata/aiops/actions/runs/41227577051) SUCCESS 3/3; #205 `e907199f169fa65e2717ba11bcd4b790579302b3` [41227319260](https://github.com/alimtalbi-ata/aiops/actions/runs/41227319260) SUCCESS 3/3; #204 `241977c7802f5647a5f6eb6072bf1dcf1c508521` [41226950941](https://github.com/alimtalbi-ata/aiops/actions/runs/41226950941) SUCCESS 6/6, stacked on #194. #213 `12a65b5733ecc96108f3cb77f96a340185f71616` [41225279446](https://github.com/alimtalbi-ata/aiops/actions/runs/41225279446) SUCCESS 3/3 but stale #201 base. #196 `747f0df4b8bae0fa0265b6dc568558a6a9057ad1` [41083049858](https://github.com/alimtalbi-ata/aiops/actions/runs/41083049858) FAILURE, six evaluator exits 1.
- **D1 NOT_QUALIFIED:** Portal #201 bearer-only component/navigation/bootstrap now 503 UNKNOWN before link disclosure; positive actor+tenant/Run ACL absent. Core #205 signed xref synthetic, not a Portal exact-Run authorization; migration ordinal 009 collision until #212 source-only rename to 012, combined PG16 chain/recovery NOT_RUN.
- **D2 NOT_QUALIFIED:** seven ACME events are offline synthetic; no one-incident/one-Run authenticated browser/API journey at the same combined SHA. Captured Chromium 7/7 is synthetic, not positive tenant ACL.
- **D3 NO_GO:** changed #204 artifact [13052770018](https://github.com/alimtalbi-ata/aiops/actions/runs/41226950941/artifacts/13052770018) audited: SHA256 `d81b1a1ce9bb55072fb6c01a19d237f61a7916d475ed6d034384af8c979d75df`; 412/412 sidecar, 413/413 in-memory repack, **30/68** JSON size/hash incorrect, release mismatch `8.0.0` vs `2.1.0-core-rc1.4`, checkout SHA mismatch; cumulative upgrade/rollback missing, install/upgrade/rollback **0/0/0**. `SEMANTIC_INTEGRITY=FAIL`.
- **D4 NOT_ATTESTED:** no client sign-off. No Debian/cron/runner, merge/main push, GLPI write, executor, production or LIVE. **`RELEASE_STABLE=NO_GO`.**
