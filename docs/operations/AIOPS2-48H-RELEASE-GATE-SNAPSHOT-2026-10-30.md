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
