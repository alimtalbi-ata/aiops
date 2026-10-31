# Release-kit audit — AIOps 2.1.0-core-rc1.4

**Audit date:** 2026-10-30 12:20 UTC  
**Source workflow:** [AIOps quality run 41053026110](https://github.com/alimtalbi-ata/aiops/actions/runs/41053026110)  
**Artifact:** `aiops2-core-deployment-kit`, ID `12974884559`  
**Result:** archive integrity PASS; release/production readiness NOT QUALIFIED.

## Exact artifact integrity

| Check | Result |
|---|---|
| Outer ZIP size | 705,587 bytes |
| Inner kit | `AIOps-2.1.0-core-rc1.4-Core-Deployment-Kit-20261030T120953Z.zip` |
| Inner ZIP size | 763,130 bytes |
| Inner ZIP SHA-256 | `4c7bd6a707fc24a308de033ee7f1b02b6df123cfd7c2615eea9cecb7b7be2646` |
| ZIP entries | 455 |
| `FILES-SHA256SUMS` entries | 405 |
| Verified file hashes | 405 / 405 PASS |
| Missing/mismatched hashes | 0 |
| Migration 011 HITL outbox | Present |
| Intelligence service + evaluator | Present |
| OIDC/HITL code and tests | Present |

## Manifest

```
product=AIOps 2.0
version=2.1.0-core-rc1.4
source_packaging_mode=versioned_git_tree
built_utc=20261030T120953Z
git_commit=6273ad48a027595c9115d0f229cc3df38c95b124
qualification=CI-runtime-e2e-PASS
synthetic_analyst_critic_quality=PASS
real_model_qualification=NOT_RUN
production_qualification=NOT_RUN
ci_evidence_carried=yes
```

The manifest's `git_commit` is the packaging workflow's temporary merge/tree SHA. It is not the PR head SHA and not Debian `applied.sha`.

## Contents relevant to current work

Present:
- `app/intelligence/main.py`
- `tools/evaluate_ai_core.py`
- `tests/test_ai_eval_harness.py`
- `db/migrations/011_hitl_decision_outbox.sql`
- `config/.env.example`
- `09-Qualification/ai-core-evaluation.json`
- `09-Qualification/runtime-e2e-RUN-FB8DDB7C6B22B5F4.json`

Absent:
- The new architecture/ITIL/48h documents from PR #195.
- The benchmark governance and deterministic baseline documents from the architecture branch.

The kit is therefore a reproducible RC candidate for the stacked #194/#196 source tree, not yet the cumulative reinstallation kit for the new main-based architecture baseline.

## Qualification boundary

- CI synthetic Runtime E2E: PASS.
- Synthetic Analyst/Critic evaluation: PASS.
- Real DGX/model qualification: NOT_RUN.
- Production qualification: NOT_RUN.
- Debian host `applied.sha`, deployed image equivalence, install/upgrade/rollback rehearsal on the target host: NOT_ATTESTED / NOT_RUN.
- LIVE remediation: disabled.

## Required next package

After the main-based integration PRs are accepted, rebuild the kit from one exact release-candidate SHA. Include the architecture/ITIL/benchmark docs, current configuration templates, full migration chain, scripts, tests, operator runbooks, rollback and health-smoke templates, CI evidence and checksums. Re-run clean extraction, offline repack, install/upgrade/rollback rehearsal and exact-SHA verification. Never re-label this current artifact as production-ready.


## Second RC1.4 artifact comparison — ACME candidate 5782d6f

A second kit was downloaded from PR #185 run `41053319020`, artifact `12975971501` (current ACME candidate head `5782d6fcece32cfd38ada0d50bfe68a8b74bd164`).

| Check | PR #185 ACME artifact | PR #196 HITL/AI artifact |
|---|---:|---:|
| Artifact ID | 12975971501 | 12974884559 |
| Inner ZIP SHA-256 | `af627c8af804eec25e643e7b3a7169bb6e513ee6cae8687c18bc4c47c2c0aa5d` | `4c7bd6a707fc24a308de033ee7f1b02b6df123cfd7c2615eea9cecb7b7be2646` |
| Entries | 445 | 455 |
| Checksums | 395 / 395 PASS | 405 / 405 PASS |
| Migration 011 | ABSENT | PRESENT |
| OIDC verifier | ABSENT | PRESENT |
| AI per-call telemetry | ABSENT (older Intelligence/evaluator) | PRESENT |
| Architecture/ITIL docs | ABSENT | ABSENT |

Both packages are internally checksum-valid but represent different source trees and capabilities. The ACME package is not a superset of the HITL/AI package; the HITL/AI package does not include the new architecture docs or latest ACME candidate fixes. Neither package is the final cumulative installation kit.

## Current candidate quality caveat

PR #185 head `5782d6f` has Quality run `41053319020` 6/6 SUCCESS, Offline `41053318999` and Historical `41053319033` SUCCESS, but V2.8 run `41053319372` FAILED: `test_demo_live_trace_is_source_backed` expected `gates.decision`, while the current scoped reader contract returns `gates.items`. This is a test fixture contract mismatch; update the fixture to the current collection shape, do not weaken identity scoping. PR #185 remains non-mergeable to main due base divergence.


## 2026-10-30 12:30 UTC — 5/5 scoped-gates regression repair — post-fixture kit gate

#185 has a new **test-only** commit `2b2af9cd21e48be741a3906b7a12cfffa3371f7b` (scoped `gates.items` fixture). V2.8 exact-head run 41055650146 SUCCESS; prior 58/59 error is fixed in CI. This **does not create or qualify a new cumulative ZIP**. The previously inspected #185 artifact `12975971501` still lacks migration 011, OIDC verifier and AI telemetry; #196 artifact `12974884559` lacks the architecture docs and latest ACME. Quality run 41055650123 is pending at this snapshot; no packaging claim for the new head. A cumulative kit must be built from a clean integrated SHA and inspected for actual files, manifest, hashes, migrations, rollback and smoke, not inferred from the artifact label. Stable/production NO-GO.


## 2026-10-30 12:32 UTC — final exact-head CI and kit inspection

New #185 exact-head Quality run [41055650123](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650123) **6/6 SUCCESS**; artifact `12976991134`, outer `aiops2-core-deployment-kit`. Inner `AIOps-2.1.0-core-rc1.4-Core-Deployment-Kit-20261030T123047Z.zip` SHA256 **`3ff78df871c3e32b72d1f9c4d077cee0301b5aeeb3dae0edab20a415719fc2aa`** (matches sidecar); **445/445 CRC, 395/395 file SHA256**. Exact changed test `tests/test_v28_portal_ui.py` Git blob `ca08e07e612e66d10936c0793d3f11c469147bd8` verified in ZIP. On fresh extraction: V2.8 **59/59**, targeted suite **253/253**, compileall PASS; offline loopback preview **14/14 GET 200**, POST 405, absent run 404. Inner manifest `git_commit=e778ce091510c6c0a596233e500437951063a485` is a CI temporary merge SHA, **not** candidate head or Debian applied SHA.

**Cumulative content gate still FAILS:** `db/migrations/011_hitl_decision_outbox.sql`, `app/core/hitl_identity.py`, `app/shared/hitl_identity.py` and `docs/architecture/AIOPS2-REFERENCE-ARCHITECTURE-2026-10-30.md` are **absent** from this exact ZIP; the intelligence/evaluator sources are older than #196. Passing checksums prove integrity, not completeness. No install/upgrade/rollback qualification or Debian runtime evidence. **RELEASE_STABLE=NO_GO.**

### 2026-10-30 13:12 UTC — repaired #185 ZIP member-level audit

#185 head `2b2af9cd21e48be741a3906b7a12cfffa3371f7b`; [Quality 41055650123](https://github.com/alimtalbi-ata/aiops/actions/runs/41055650123) SUCCESS. Local inner archive SHA256 `3ff78df871c3e32b72d1f9c4d077cee0301b5aeeb3dae0edab20a415719fc2aa`; 445/445 ZIP entries intact, 395/395 file SHA256 checks PASS, fresh-extraction V2.8 59/59 and AI harness 3/3 PASS. **Absent members**: `db/migrations/011_hitl_decision_outbox.sql`, `app/core/hitl_identity.py`, `app/shared/hitl_identity.py`, `docs/architecture/AI-INVOCATION-TELEMETRY-IMPLEMENTATION.md`, `docs/architecture/AIOPS2-REFERENCE-ARCHITECTURE-2026-10-30.md`, `docs/customer-story/ACME-P1-SAN-PAYMENTS-ITIL-DEMO-2026-10-30.md`, `docs/operations/AIOPS2-SCHEDULE-AND-CRON-STRATEGY-2026-10-30.md`. Archive integrity **does not** establish cumulative feature completeness, clean install, upgrade or rollback. Next kit: one clean main-based SHA with selective #185 scenario, #194 migration/OIDC, #196 telemetry, #195 docs and verified configs/scripts/tests/runbooks; audit actual members, hashes and exact-head CI before GO.

## 2026-10-30 14:00 UTC — main-based staging does not equal cumulative kit

Draft [#201](https://github.com/alimtalbi-ata/aiops/pull/201) head `2ceda14c8a21fe71e88b3228879799e6c37a5387`, base `main@27deb9b1`, brings six exact isolated source/test blobs from #197/#198/#199 and fourteen architecture docs from #195 plus CI test wiring and a provenance note. **It intentionally excludes** #185 Portal/scenario code, #194 migration 011/OIDC/outbox, #196 AI telemetry and any install/upgrade/rollback implementation. Combined [Quality 41068355452](https://github.com/alimtalbi-ata/aiops/actions/runs/41068355452) was **IN_PROGRESS** at capture; no artifact content or checksum claim. Prior #185 and #196 ZIPs are individually integrity-checked but mutually incomplete; neither may be relabeled cumulative. Release T0 pending, T1/T2/T4 NOT_TESTED, T3 NOT_ATTESTED, T5 NO_GO. Next package must be built from one fully integrated exact SHA and member-audited for migrations, OIDC, telemetry, docs, source manifests, checksum/SBOM, smoke and rollback.

## 2026-10-30 14:16 UTC — executable negative release gate added

[#201](https://github.com/alimtalbi-ata/aiops/pull/201) HEAD `03a5b0cce44e56d7ae315ee7df16e850a5e35b11` adds `tools/check_cumulative_release_kit.py` and 10/10 offline unit tests, plus CI wiring. Local exact-file Git blobs 2/2; new-head Quality pending at record time. A read-only invocation on the previously supplied #185 inner ZIP (`aiops2-2b2af9c-inner.zip`) verified **395/395 listed SHA256** but failed cumulative inventory: migration 011, HITL identity, #196 telemetry, main-based Portal/Policy/Evidence files and #195 docs are absent. `RELEASE-MANIFEST.txt` contains a temporary CI merge SHA, not the expected PR head. The provided local directory was not a Git checkout, so source equivalence is **NOT_ATTESTED**. The gate also rejects missing checksum members, ZIP traversal, duplicate members and manifest/source mismatches. This does **not** attest install/upgrade/rollback behavior, Debian `applied.sha` or LIVE. Next release kit must be built from one exact clean main-based SHA, checked against its source checkout and rehearsed in disposable infrastructure.

## 2026-10-30 14:23 UTC — source-provenance negative gates verified

The one clean-main staging [#201](https://github.com/alimtalbi-ata/aiops/pull/201) advanced to `84f6cf1c3656c8c9b74acaf6036cc0c443827aad` with two release-only commits: `tools/check_cumulative_release_kit.py` and `tests/test_cumulative_release_kit_gate.py`. The checker now rejects a dirty tracked source checkout (`SOURCE_TREE_DIRTY`) and a nested source directory (`SOURCE_NOT_REPOSITORY_ROOT`); matching ZIP member hashes and `git rev-parse HEAD` alone cannot certify commit provenance. [Exact-head Quality #41071155614](https://github.com/alimtalbi-ata/aiops/actions/runs/41071155614) completed SUCCESS **3/3 jobs**, with **12/12 cumulative gate tests PASS** in the policy-and-static job log (including both new negative tests). These are isolated inventory tests, not a cumulative package or install/upgrade/rollback rehearsal. Migration 011/OIDC/outbox/AI telemetry remain outside #201; Debian/LIVE qualification is NOT_ATTESTED/NO_GO.

## 2026-10-30 14:28 UTC — exact Portal source transport, not a new kit

[#201](https://github.com/alimtalbi-ata/aiops/pull/201) main-based candidate advanced from `84f6cf1c3656c8c9b74acaf6036cc0c443827aad` to `178bbf71f5884c5a8b54f38ca815c6f76ea0ffb9`, transporting four exact blobs from #202 `cd17c44d47ecdf5ced2306edf169befcb2eff8ac`. Previous #201 four blobs equaled #202 ancestor `6c72000e` **4/4**; no conflicting workflow, main.py, Compose or config was replaced. #202 [Quality 41071596535](https://github.com/alimtalbi-ata/aiops/actions/runs/41071596535) SUCCESS 3/3, targeted Portal tests 21/21 Python and 6/6 JS. **Combined new #201 SHA CI is IN_PROGRESS** at the time of this note; old #201 Quality 41071155614 SUCCESS 3/3 and 12/12 kit guard tests do not qualify the new SHA.

No cumulative ZIP was built or audited in this update. Migration 011, OIDC/outbox and #196 telemetry remain absent from #201. The historical #185 and #196 ZIPs remain individually checksum-valid but incomplete and incompatible as a cumulative source. Next gate: complete exact-head #201 CI, reconcile #194/#196 on clean main-based source, produce a single source-equivalent ZIP and separately exercise install/upgrade/rollback in disposable infrastructure. T4/T5 NO_GO; Debian `applied.sha` NOT_ATTESTED.

## 2026-10-30 15:10 UTC — additional source-only fixture gate, no cumulative artifact

- #201 single main-based candidate advanced to `7474c74c9e6a79c5d28d6624f7b9be2100a792ac` with two small commits: `tests/test_acme_san_payments_fixture_contract.py` copied exactly from #198 source blob `675a0af6cd240549d1af92fbcf7a06ec2d2bd638` (seed blob `67f0124a2c3b450e5249165e719a5d943fdd7237` unchanged), and `.github/workflows/quality.yml` now invokes its six offline tests. Exact new-head Quality [41077972849](https://github.com/alimtalbi-ata/aiops/actions/runs/41077972849) **IN_PROGRESS** at this snapshot. This is a source/CI coverage increment, **not a newly built ZIP**.
- #196 benchmark [Quality 41070920303](https://github.com/alimtalbi-ata/aiops/actions/runs/41070920303) green 8/8 jobs but both Ollama CPU jobs silently retained six failing evaluator exits (3 repeats/model), all `ReadTimeout`/UNAVAILABLE. Treat model qualification **FAILED/UNAVAILABLE**, independent of CI job status. No cumulative kit source has absorbed #194 migration 011/OIDC/outbox or #196 telemetry; no clean install, upgrade, rollback or Debian applied SHA evidence. T4/T5 NO_GO.

## 2026-10-30 15:36 UTC — no cumulative kit despite source/CI progress

#201 clean-main `2dafb00717b572023153e2b5dd974eada8a759c5` is a **test/contract integration candidate**, not a cumulative installable release. The exact-head [Quality 41082175476](https://github.com/alimtalbi-ata/aiops/actions/runs/41082175476) is pending; do not reuse prior green SHAs. Migration 011, verified OIDC/HITL outbox, #196 AI telemetry, runtime tenant/GLPI/Evidence links and actual clean install/upgrade/rollback are not integrated/attested. No new cumulative ZIP, checksum, SBOM, deployed `applied.sha` or rollback evidence was produced. Existing #185/#196 artifacts remain incomplete as a combined kit. T4/T5 NO_GO.

### 2026-10-30 15:40 UTC — source/browser artifact is not a cumulative kit

[#201 Quality 41082437029](https://github.com/alimtalbi-ata/aiops/actions/runs/41082437029) SUCCESS 3/3 on `5f2feb08`, Chromium 6/6 and 12/12 inventory gate. The downloaded [CI simulated browser artifact 12989149422](https://github.com/alimtalbi-ata/aiops/actions/runs/41082437029/artifacts/12989149422) has valid ZIP CRC and a screenshot whose bytes match metadata SHA256 `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca`; it is a **browser observation**, not a source deployment ZIP. #201 next HEAD `59ba22f1` selectively includes #202 Portal denial headers; [Quality 41082715412](https://github.com/alimtalbi-ata/aiops/actions/runs/41082715412) QUEUED. Cumulative migration 011/OIDC/AI telemetry, exact source install/upgrade/rollback and Debian applied SHA still NOT_TESTED/NOT_ATTESTED. T4/T5 NO_GO.

<!-- convergence-5of5-477da60-20261030 -->
## Exact-main-based candidate kit delta — 2026-10-30T16:15:33.055Z

**Audit UTC:** 2026-10-30T16:15:33.055Z. **Release candidate:** [#201](https://github.com/alimtalbi-ata/aiops/pull/201), base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, exact HEAD [`477da60d92dc777e1e635eea4c5510c350a5d90c`](https://github.com/alimtalbi-ata/aiops/commit/477da60d92dc777e1e635eea4c5510c350a5d90c), **28 ahead / 0 behind**, draft and unmerged. [Exact-head Quality 41088096834](https://github.com/alimtalbi-ata/aiops/actions/runs/41088096834) **QUEUED** at audit; previous #201 [Quality 41082715412](https://github.com/alimtalbi-ata/aiops/actions/runs/41082715412) **3/3 SUCCESS** on old `59ba22f1`, not on this new SHA.

This commit integrates only six source/test blobs from #198/#202, **not** migration `011_hitl_decision_outbox.sql`, OIDC/HITL or #196 per-call telemetry. No cumulative ZIP was produced or extracted in this checkpoint; manifest, member-level SHA256, SBOM, install/upgrade/rollback and `applied.sha` are **NOT_TESTED/NOT_ATTESTED**. Historical #185 and #196 ZIPs remain internally checksum-valid but mutually incomplete. **Kit gate T4=NO_GO**. Next exact test: from a clean, approved main-based source SHA, build ZIP; run `python3 tools/check_cumulative_release_kit.py --help` to inspect required CLI, then validate archive members, manifest, SHA256, ordered migrations and sandbox install/rollback. Never infer completeness from artifact name or CI green.

## Main-based source delta — 2026-10-30 17:08 UTC

[#201](https://github.com/alimtalbi-ata/aiops/pull/201) now `1d3a902877d556549425a95cd4cef792c5c000c8` (base `main@27deb9b1`, 29 ahead/0 behind). The only new source change is Portal `app/portal/main.py` exact blob `0dac60be551f58e8a2bf578178a4ff298aef5118`, copied selectively from #202 to restore no-store/CSP/anti-framing on the anonymous home response. Prior exact-head #201 Quality 41088096834 failed 2/3 due to missing header; new [Quality 41096370024](https://github.com/alimtalbi-ata/aiops/actions/runs/41096370024) **IN_PROGRESS**, not qualified. This source fix is **not a cumulative release kit**. No new ZIP/extraction/repack, ordered migration 011, OIDC/HITL/outbox, #196 telemetry, SBOM, manifest/member checksum verification, sandbox install/upgrade/rollback or Debian `applied.sha` attestation. Historical #185/#196 artifacts remain non-cumulative. T4/T5 NO_GO; never infer kit completeness from successful unit tests.

### Real artifact byte audit — 2026-10-30 17:12 UTC

Downloaded actual [#201 Quality 41096370024 artifact 12995044690](https://github.com/alimtalbi-ata/aiops/actions/runs/41096370024), **ZIP SHA256 `c1a5fcb6ed4819d67c1a06e252541674bfbcdf4db8332d2b88e529cd30fa6cbf`**, 2 entries, ZIP CRC PASS. Members: `capture-metadata.json` (851 bytes), `explore-story-ci-simulated.png` (249732 bytes). Screenshot bytes SHA256 `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca`, matching the metadata. Metadata explicitly says `CI_SIMULATED_PORTAL`, `runtime_authenticated=false`, `production_qualified=false`, `live_remediation_authorized=false`, `glpi_ticket_id=null`, `privacy_reviewed=false`.

**Provenance discrepancy:** artifact `git_sha=55b02788f9c699d20db4f48ae35eff2cda92cc2d`, whereas PR #201 source HEAD is `1d3a902877d556549425a95cd4cef792c5c000c8`. Source inspection shows `tests/test_explore_story_playwright_e2e.py` writes `git_sha=os.environ.get("GITHUB_SHA")`; for pull_request workflows this is normally the synthetic merge checkout, not the PR head. Do **not** claim screenshot is head-SHA-labelled. Next metadata contract test: record both PR head/base SHA from event and actual checkout/merge SHA, verify event association and fixture digest before promoting capture as exact-source proof. This ZIP is **not** an installable kit.

## Current candidate source and package gate — 2026-10-30 18:xx UTC

#201 now HEAD `7bc825b30e13c9a685192fde7486cad5632061fe` on `main@27deb9b1`; exact source import from #202 only: Portal four-field Core Run identity guard and negative tests (two files, commits `3356aac5`/`7bc825b3`). [Quality 41104533241](https://github.com/alimtalbi-ata/aiops/actions/runs/41104533241) QUEUED at audit; previous HEAD `1d3a9028` Quality 41096370024 SUCCESS 3/3 cannot qualify this new SHA. No new cumulative artifact was produced or inspected by this increment. Prior #201 artifact `12995044690` is a synthetic Chromium screenshot ZIP, **not an installable package**; its metadata `git_sha` identifies a PR merge checkout, not the source head. Explicit source-head/base/checkout and fixture digest must be recorded and validated in future receipts.

Historical #185 and #196 ZIPs are individually checksum-valid but neither cumulative; #201 still lacks main-based integration of migration 011, verified OIDC/HITL/outbox, AI telemetry, ordered install/upgrade/rollback and an exercised sandbox rehearsal. **T4 NO_GO / T5 NO_GO**. Next exact gate: build once from clean source SHA, inspect actual ZIP members and hashes, extract/repack, then test install/upgrade/rollback in an isolated sandbox. No Debian/production changes.


### 2026-10-30 19:10 UTC — no cumulative artifact from green integration CI

#201 prior exact HEAD `7bc825b30e13c9a685192fde7486cad5632061fe`, [Quality 41104533241](https://github.com/alimtalbi-ata/aiops/actions/runs/41104533241) SUCCESS 3/3, produced artifact `12999887492` (`acme-explore-story-ci-simulated`, 237616 bytes; GitHub Actions digest `sha256:54aa3dbd4a1564805b281c6647c2fd64e0f2edce5f22d49ef39b873fbfaf2ca2`). **No ZIP download, member audit, extraction or repack was performed in this checkpoint.** This is a synthetic-story artifact by workflow label, not a cumulative installation kit. New #201 HEAD `7e4cbe9d75aedccf2078ca50d052e6d0796c284e` has no observed exact-head CI/artifact yet. Migration 011, OIDC/outbox, #196 telemetry, ordered install/upgrade/rollback and disposable rollback rehearsal remain **NOT_INTEGRATED / NOT_TESTED**. Do not infer completeness from successful checksums or artifact names. T4 **NO_GO**, T3 NOT_ATTESTED, T5 NO_GO.


### 2026-10-30 19:16 UTC — artifact member audit and SHA distinction

Actual downloaded #201 artifact `13005150615` from [Quality 41113172965](https://github.com/alimtalbi-ata/aiops/actions/runs/41113172965): ZIP size **237618**, SHA256 `6fdaab4220604c401c531999907df55e0a54d713920537ca22f5dfac2886bf69` (matches GitHub digest), **2/2 CRC PASS**. Only `capture-metadata.json` and `explore-story-ci-simulated.png` exist; screenshot digest `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca` matches metadata. `git_sha=43f3b5bd...` is a temporary PR merge checkout, **not** source `7e4cbe9d...`. No migration, install, upgrade, rollback, or cumulative manifest in this artifact. #201 `cee6a834` now emits distinct source/base/checkout SHA fields (exact-head CI pending). **T4 NO_GO**, Debian T3 NOT_ATTESTED, LIVE T5 NO_GO.


### 2026-10-30 19:20 UTC — new exact-head synthetic artifact audited

#201 `cee6a834befbee47275e83651e7c0955528c51a0`, [Quality 41113479815](https://github.com/alimtalbi-ata/aiops/actions/runs/41113479815) SUCCESS 3/3. Artifact `13004397285` downloaded: **237689 bytes**, SHA256 **`7f1821aefdbc687601bc2ae62163a7e777df03e8d6d939031880cead20b6ab93`**, **2/2 CRC PASS**, screenshot checksum PASS. Members only `capture-metadata.json` and `explore-story-ci-simulated.png`; metadata source HEAD `cee6a834...`, base `27deb9b1...`, merge checkout `73a71c76...` are separately recorded and verified. This is **not** a cumulative kit. Migration 011/OIDC/telemetry/install/upgrade/rollback still unqualified. **T4 NO_GO**.


### 2026-10-30 ~20:08 UTC — kit gate after canonical status port

#201 main-based candidate advanced from `cee6a834befbee47275e83651e7c0955528c51a0` to `8236c93460a160914247aaca8141253ebddf3aac` via two exact-blob Portal/status test commits `81f9645d`, `8236c934`. [Quality 41120972224](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224) QUEUED at audit; no new artifact inspected. Prior exact-head [Quality 41113479815](https://github.com/alimtalbi-ata/aiops/actions/runs/41113479815) SUCCESS and screenshot artifact `13004397285` ZIP SHA256 `7f1821aefdbc687601bc2ae62163a7e777df03e8d6d939031880cead20b6ab93` are for old `cee6a834`, **not** the current candidate. Screenshot-only ZIP is not a cumulative kit. Migration 011, OIDC/outbox, AI telemetry, install/upgrade/rollback scripts, ordered migration checks, cumulative manifest/SHA256/SBOM and sandbox rollback remain NOT_INTEGRATED / NOT_TESTED. T4 NO_GO; T3 NOT_ATTESTED; T5 NO_GO. Do not infer readiness from green source CI.

## 2026-10-30 21:10 UTC — exact-head CI artifact audit, not a cumulative kit

[#201](https://github.com/alimtalbi-ata/aiops/pull/201) source HEAD `8236c93460a160914247aaca8141253ebddf3aac`, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, [Quality 41120972224](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224) **SUCCESS 3/3**. Downloaded [artifact 13007279749](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224/artifacts/13007279749): 237690 bytes, ZIP SHA256 `083ec62ececcbb11e2c47ef777619e86c7c5d9bfa11d9ff67713e4502d5718dc`, exactly two members (`capture-metadata.json`, `explore-story-ci-simulated.png`), **2/2 CRC PASS**, screenshot SHA256 `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca` matches metadata. Receipt separates `source_head_sha=8236c934...`, `base_sha=27deb9b1...`, `checkout_sha=959a34e1...`; `runtime_authenticated=false`, `glpi_ticket_id=null`, `production_qualified=false`.

This ZIP is a **synthetic browser observation**, not an installable cumulative release kit. `db/migrations/011_hitl_decision_outbox.sql`, HITL identity/outbox, `app/intelligence/main.py`, `tools/evaluate_ai_core.py` are absent from #201. No new cumulative manifest, member SHA256, ordered migration rehearsal, clean install/upgrade, rollback, SBOM or Debian `applied.sha` proof. Source inventory negative-path tests 12/12 PASS **do not substitute for a built kit**. **T4 NO_GO, T5 NO_GO; RELEASE_STABLE=NO_GO.** Next: after selective dependency integration, build from a clean exact source SHA; audit the actual ZIP with `tools/check_cumulative_release_kit.py --kit ... --expected-source-sha ... --source-dir ...`; extract/repack, exercise isolated install/upgrade/rollback and retain checksums and receipts.

## 2026-10-30 ~22:27 UTC — exact-head artifact inventory, release gate unchanged

[#201](https://github.com/alimtalbi-ata/aiops/pull/201) source HEAD `8236c93460a160914247aaca8141253ebddf3aac` on `main@27deb9b1a66faf27df8d69b137a63451f7649d80` remains Quality [41120972224](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224) SUCCESS 3/3. Its artifact `13007279749` is the **previously audited synthetic two-member screenshot ZIP**, not a cumulative kit. [#195](https://github.com/alimtalbi-ata/aiops/pull/195) prior HEAD `5034be415aac0029ba5cf6b8f2bf68b9f607dd59` Quality [41129279978](https://github.com/alimtalbi-ata/aiops/actions/runs/41129279978) SUCCESS 3/3; a new documentation commit requires fresh CI.

[#204](https://github.com/alimtalbi-ata/aiops/pull/204) HEAD `b8f0c24c1bb1c31b90d46a6d7d8977883ef6792c`, stacked on #194, Quality [41136324582](https://github.com/alimtalbi-ata/aiops/actions/runs/41136324582) SUCCESS 6/6. Actions lists `aiops2-core-deployment-kit` artifact **13015508690** (reported size 707182 bytes) plus runtime/DB rehearsal artifacts. **Listing an artifact is not a content audit**: bytes, CRC, member hashes, migration ordering, exact source manifest, extraction/repack and sandbox install/upgrade/rollback were NOT_INSPECTED/NOT_TESTED this run. This stacked artifact is **not** a cumulative #201 main-based candidate.

A newly confirmed release stop-line is the #201 Portal Run/Incident/status projection under shared bearer with `tenant_acl_qualified=false`. Even green CI does not authorize a multi-tenant operator cockpit; require Core server-derived actor/tenant exact-Run authorization and negative 401/403/404/503 disclosure tests. Migration 011, HITL/OIDC/outbox, Intelligence telemetry and cumulative package remain unintegrated into #201. **T0=GO_LIMITED for isolated exact-head CI; T1/T2 NOT_TESTED; T3 NOT_ATTESTED; T4/T5 NO_GO; RELEASE_STABLE=NO_GO.**

## 2026-10-31 5/5 — security source port is not a release kit

#201 `f38014c92b85763be8ac3f72042b50a48dbba95c` base `main@27deb9b1a66faf27df8d69b137a63451f7649d80` contains the exact #202 `f3943020d0d66d60c92dbf9b0d0c3fbb7913789e` Portal fail-closed blob and negative tests; source #202 [Quality 41142124145](https://github.com/alimtalbi-ata/aiops/actions/runs/41142124145) SUCCESS 3/3, but combined #201 exact-head CI pending at port. The previous #201 artifact 13007279749 is a synthetic Chromium screenshot ZIP, **not** a cumulative kit. #204 `c1fc37c16024ca3ae8b31aad7b604f71993eebcd` is stacked, its [Quality 41141963825](https://github.com/alimtalbi-ata/aiops/actions/runs/41141963825) SUCCESS does not qualify a main-based package. Migration 011, identity/outbox, Intelligence/evaluator, ordered install/upgrade/rollback and sandbox receipts remain absent/unqualified on #201. No ZIP extraction/repack or sandbox install/rollback performed this run. T4=NO_GO; T5=NO_GO; `RELEASE_STABLE=NO_GO`.

### 2026-10-31 — exact #201 Chromium artifact byte audit

[#201 Quality 41145124544](https://github.com/alimtalbi-ata/aiops/actions/runs/41145124544) on source HEAD `f38014c92b85763be8ac3f72042b50a48dbba95c` SUCCESS 3/3. Artifact [13020710411](https://github.com/alimtalbi-ata/aiops/actions/runs/41145124544/artifacts/13020710411) was **downloaded and inspected**: ZIP 237,688 bytes, SHA256 `b850361d60dd4b291d54f82db3acc838319dca2f1209f14d1b1feb3a40165b4f`, 2/2 CRC PASS, members `capture-metadata.json` and `explore-story-ci-simulated.png` only. PNG SHA256 `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca` matches metadata. Metadata separates `source_head_sha=f38014c9...`, `base_sha=27deb9b1...`, `checkout_sha=ae76127a...`; `runtime_authenticated=false`, `glpi_ticket_id=null`, `production_qualified=false`. **Synthetic browser capture, NOT a cumulative installation kit.** Migration 011/HITL/AI and sandbox rollback remain unqualified. T4/T5 NO_GO.


### 2026-10-31 03:31 UTC — independently inspected stacked #204 nested release artifact (not cumulative #201)

Source #204 HEAD `b4198e1e4a7fb763f632d1cd4d5a78b7db92f74e`, [Quality 41162880436](https://github.com/alimtalbi-ata/aiops/actions/runs/41162880436) SUCCESS 6/6. [Artifact 13027198980](https://github.com/alimtalbi-ata/aiops/actions/runs/41162880436/artifacts/13027198980) downloaded and independently audited: outer 709,590-byte ZIP SHA256 `52bcc27148aa31c7cccce88823f3ef42c2fbec11ba838aaa6be72edda3f2bacf` (2/2 CRC PASS), nested 767,490-byte ZIP SHA256 `18255dab2e157c6671b077c18a4143309f83b2fb1eaeb2c37618e07829492e48` (456/456 entries CRC PASS). Nested `FILES-SHA256SUMS` verifies **406/406** regular files, but embedded `manifests/MANIFEST.json` lists **68** paths with **30 mismatched file digests** (38 correct, none missing). It declares `release=8.0.0` while `RELEASE-MANIFEST.txt` declares `version=2.1.0-core-rc1.4`; `git_commit=fa7ad62702a5128de6cea0158cd5300268752c7c` does not match source HEAD `b4198e1e...` and lacks explicit checkout/source provenance. All ZIP paths safe, no symlinks; disposable extraction and repack verified **407/407 file hashes** unchanged, CRC PASS. **No SBOM found; no sandbox install/upgrade/rollback performed.** The package is not a qualified main-based cumulative release kit. Embedded manifest mismatch is a stop-the-line integrity defect, even though the separate generated SHA256SUMS is internally consistent.

#201 exact HEAD `a5bdb5bfeb8a05bd761cba7268b9c6ffc8fc3b95` [Quality 41164572871](https://github.com/alimtalbi-ata/aiops/actions/runs/41164572871) SUCCESS 3/3, Portal Run 33/33, Chromium 6/6, kit guard 12/12. Artifact 13028322111 is a synthetic browser capture (SHA256 `8b8a295aee139c573cca1ca38577d9b00da4a59c3c9aac93ab1e11fd095f615b`), not an install kit. **T4/T5 NO_GO**. Operator installation/rollback remains NOT_TESTED; no Debian access or effects.

### 2026-10-31 04:35 UTC — fresh #204 artifact and #201 semantic stop-line

Fresh #204 [Quality 41166983844](https://github.com/alimtalbi-ata/aiops/actions/runs/41166983844) SUCCESS 6/6 on stacked HEAD `7b7db90b71897b070deb20ca58dab62082bf0f80`; [artifact 13029760540](https://github.com/alimtalbi-ata/aiops/actions/runs/41166983844/artifacts/13029760540) downloaded and inspected. Outer ZIP 710,227 bytes, SHA256 `3c95c1c9d1c0727829cb09fbf93140fb6665a3bf7e4f70cc5719cdb10850fa20`, CRC PASS; nested ZIP 768,086 bytes, SHA256 `1bc9933f8c92a0d3e70969180e4936ae1c2a3a9e64f003d7e78be2c784d28605`, 456 members, CRC PASS, sidecar digest matches. `FILES-SHA256SUMS`: 406/406 PASS. Embedded `manifests/MANIFEST.json`: **38/68 match, 30/68 mismatch**, none missing; release `8.0.0` vs text `2.1.0-core-rc1.4`. No SBOM found. No install/upgrade/rollback performed. The package remains **NO-GO** despite workflow green.

#201 main-based source `e116d04c791b6f5a5028d6f2cc3797a547b460ec` now adds a read-only, fail-closed semantic manifest gate and four negative tests; [Quality 41169101273](https://github.com/alimtalbi-ata/aiops/actions/runs/41169101273) IN_PROGRESS at observation. The gate is not a repair of #204's generator, not an actual cumulative ZIP and not a sandbox rollback attestation. Next: fix generator at source, regenerate kit from exact integrated SHA, validate all manifest layers and SBOM, then exercise disposable install/upgrade/rollback with receipts. **T4/T5 NO_GO.**


### 2026-10-31 06:27 Europe/Paris — staged manifest generator source correction pending qualification

The prior stacked #204 kits 13027198980 and 13029760540 had 406/406 `FILES-SHA256SUMS` PASS yet 30/68 stale `manifests/MANIFEST.json` SHA256 values and release `8.0.0` versus `2.1.0-core-rc1.4`. Source inspection of #204 `deploy/package.sh` confirmed it archived the tracked historical V8 manifest and generated a separate checksum manifest without reconciling the embedded V8 file inventory.

[Draft PR #206](https://github.com/alimtalbi-ata/aiops/pull/206) from exact stacked #204 HEAD `f3ee9e104f3bcbb7466a8de9b68f132fe0851022` proposes a staging-only manifest refresh before ZIP checksums, fail-closed embedded verification and five regression tests. HEAD `020a05dfc186d20561ed7770b229088bc5c72238`; [Quality 41172832388](https://github.com/alimtalbi-ata/aiops/actions/runs/41172832388) initially QUEUED. No repaired ZIP has been inspected yet; source proposal does not qualify kit provenance, SBOM, install, upgrade or rollback.

Main-based #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec` [Quality 41169101273](https://github.com/alimtalbi-ata/aiops/actions/runs/41169101273) SUCCESS 3/3, 16/16 independent kit guard tests, but has no combined cumulative kit. **T4 NO_GO** until a single exact main-based integrated SHA, matching manifests and SHA256, SBOM if supported, and sandbox install/upgrade/rollback receipts. T5 LIVE NO_GO.


#### Independent fresh #204 artifact audit — 2026-10-31 06:31 Europe/Paris

[Quality 41171155211 artifact 13030723934](https://github.com/alimtalbi-ata/aiops/actions/runs/41171155211/artifacts/13030723934) downloaded and inspected (source #204 HEAD `f3ee9e104f3bcbb7466a8de9b68f132fe0851022`): outer ZIP **711,161 bytes**, SHA256 `7b968ef5d210383c24ae8a6328e1fefffa3db600f0c0ef5941d46c5cf6933418`, 2/2 CRC PASS. Nested ZIP **768,973 bytes**, SHA256 `31a626259cdcfa1d85e1f6690debdd2888b85fb837173fd44944f18d9bc0e3b4`, 456 members CRC PASS. `FILES-SHA256SUMS` **406/406 PASS**. Embedded `manifests/MANIFEST.json` **38/68 SHA256 match, 30/68 mismatch**, with **30/68 size mismatches**; no missing listed paths. JSON `release=8.0.0` conflicts with text `version=2.1.0-core-rc1.4`. Text `git_commit=14924a6405c52c364c9aa81036f3e90f2e62e60f` is packaging checkout, not exact PR HEAD, and provenance is not distinguished. **Semantic integrity FAIL despite green Quality 6/6**. This is the pre-fix stacked #204 artifact, not a #206 generated kit.

#206 revised source HEAD `516e32b1540077ab059f651d78020c2b365b3fd4` corrects test checksum fixture newlines after prior [Quality 41172832388](https://github.com/alimtalbi-ata/aiops/actions/runs/41172832388) showed 4/13 negative test failures due to invalid fixture sidecar; no production guard was weakened. New exact-head CI and regenerated artifact must be observed before any PASS. T4 NO_GO.


### Exact #206 post-fix artifact audit — 2026-10-31 ~06:38 Europe/Paris

Source: draft #206 `516e32b1540077ab059f651d78020c2b365b3fd4`, stacked on #204 `f3ee9e104f3bcbb7466a8de9b68f132fe0851022`. [Quality 41172956555](https://github.com/alimtalbi-ata/aiops/actions/runs/41172956555) SUCCESS 6/6; package verifier negative tests **13/13 PASS**. [Artifact 13031961877](https://github.com/alimtalbi-ata/aiops/actions/runs/41172956555/artifacts/13031961877) independently downloaded and audited.

| Check | Observed result |
|---|---|
| Outer ZIP | 713,938 bytes, SHA256 `49286d8d32ce195adc6973497f2e700b6b4f4f534d49f0952bed5c9743917251`, 2/2 CRC PASS |
| Nested ZIP | 771,686 bytes, SHA256 `4758c3b4fe803203dbf5273d1dad1994cf2d1ef070e3922af94f21bba042eecd`, 457 entries CRC PASS |
| ZIP safety | No unsafe paths, duplicate members or symlinks |
| Nested sidecar | SHA256 matches nested ZIP |
| `FILES-SHA256SUMS` | **407/407 PASS** |
| Embedded `manifests/MANIFEST.json` | **68/68 SHA256 PASS**, **68/68 sizes PASS**, 0 missing |
| Release versions | JSON `2.1.0-core-rc1.4` = text `2.1.0-core-rc1.4`; historical source release `8.0.0` explicitly preserved |
| Disposable extraction/repack | **408/408 file hashes PASS**; repacked ZIP CRC PASS |
| Actual install / upgrade / rollback | **0 / 0 / 0 — NOT_TESTED** |
| SBOM | NOT_ATTESTED |

The prior 30/68 embedded checksum mismatch is **repaired in this exact stacked artifact**, not in a main-based #201 release. The text manifest still records packaging checkout `82368d8a957ea177a421d9c0355dd019b76bab54` as `git_commit`, without separately declaring source head/base. No real-model qualification, tenant authorization, Debian runtime, independent ACME T2, or sandbox rollback is inferred. **T4 NO_GO, T5 NO_GO; RELEASE_STABLE=NO_GO**.


### 2026-10-31 ~08:30 Europe/Paris — independent latest #204 kit audit and new source fence

New #204 stacked HEAD `d5926feab3be7ff4496af23377541bab53dc1d70`, [Quality 41179273364](https://github.com/alimtalbi-ata/aiops/actions/runs/41179273364) SUCCESS 6/6, produced [artifact 13033619597](https://github.com/alimtalbi-ata/aiops/actions/runs/41179273364/artifacts/13033619597), downloaded and independently inspected. Outer ZIP 712929 bytes, SHA256 `001ad3949608134d100f5093eb1ff70979641cbc190c6541cb337295b4856279` (2/2 CRC PASS); nested ZIP 770818 bytes, SHA256 `d796bc988e9cb6b1f586d44115ba6e7a9d6bd12c9a9d667e8e67ae18c285b447` (457/457 CRC PASS). No unsafe paths/symlinks. Sidecar `FILES-SHA256SUMS` **407/407 PASS**, but embedded `manifests/MANIFEST.json` **38/68 digest matches, 30/68 SHA mismatches, 30/68 byte-size mismatches**. JSON release `8.0.0` conflicts with text `2.1.0-core-rc1.4`. Packaging checkout `b945cafa765d1230228dd4d880c0a8f33b77e80d` is not the PR HEAD and is not separately identified as such. Semantic integrity **FAIL** despite green workflow; no install/upgrade/rollback exercised.

The #206 repaired artifact 13031961877 is on a separate stacked branch and **does not repair** the latest #204 artifact. New draft [#208](https://github.com/alimtalbi-ata/aiops/pull/208) from #201 adds an additional read-only source-member provenance fence: even valid embedded/sidecar hashes must not conceal untracked or altered non-required files. Exact-head [Quality 41181004360](https://github.com/alimtalbi-ata/aiops/actions/runs/41181004360) pending at checkpoint. #207 staged refresh helper remains unwired to #201's legacy packager. No cumulative main-based kit, SBOM, source-vs-checkout provenance, sandbox install/upgrade/rollback or Debian attestation is qualified. **T4 NO_GO; T5 NO_GO; RELEASE_STABLE=NO_GO.**


#### Source-member guard qualification — 2026-10-31 ~08:35 Europe/Paris

[#208](https://github.com/alimtalbi-ata/aiops/pull/208) exact HEAD `dd308475e17e1c5315da6b3caf73fba42e0e647a` [Quality 41181004360](https://github.com/alimtalbi-ata/aiops/actions/runs/41181004360) **SUCCESS 3/3**; `python -m unittest discover -s tests -p "test_cumulative_release_kit_gate.py" -v` **19/19 PASS**. Three added cases prove the guard refuses checksummed untracked archive members and modified non-required tracked members while accepting matching tracked members. This validates the read-only gate only. Artifact 13035031531 SHA256 `91f8b9ea489fa17e3337e8238e68f86820fb7d24710e7fc84799412894e0979d` is a 2-member synthetic Chromium screenshot ZIP, not a release kit. **No main-based cumulative package, SBOM, install/upgrade/rollback or Debian proof; T4/T5 NO_GO.**

### Independent latest stacked kit audit — 2026-10-31 ~09:40 Europe/Paris

[#204 Quality 41182602889](https://github.com/alimtalbi-ata/aiops/actions/runs/41182602889) SUCCESS 6/6 on exact HEAD `aa24982c8c93f017b710dc7658e66728ad86fbde`. Downloaded [artifact 13035548118](https://github.com/alimtalbi-ata/aiops/actions/runs/41182602889/artifacts/13035548118): outer ZIP 713547 bytes SHA256 `c817374ad19cf092d5d3abe57b32f5a53661354c1d233b0618b38e1af437f8f6` CRC 2/2 PASS; nested ZIP 771397 bytes SHA256 `c16c30f0808ec97885295271fa1b0a63a6187b92ada3f9554fe5adbd5d4696e1` CRC 457/457 PASS; no unsafe paths/symlinks. `FILES-SHA256SUMS` 407/407 PASS; embedded JSON 38/68 SHA PASS, **30/68 SHA FAIL, 30/68 byte sizes FAIL**, JSON release 8.0.0 vs release text 2.1.0-core-rc1.4. `git_commit=6e8492dc695b3b8c50eb323e1abf3408264a8b71` is packaging checkout, not #204 source HEAD. **Semantic integrity FAIL**, even though CI is green. No install/upgrade/rollback or SBOM observed. [Handoff #204](https://github.com/alimtalbi-ata/aiops/pull/204#issuecomment-6541234890).

New [draft #209](https://github.com/alimtalbi-ata/aiops/pull/209) `9d515aee54a809bf06d81d63609b06d7b7a7e571` integrates #207's staged refresh and #208's source-member gate, with deterministic source-manifest provenance validation and three new tests. [Quality 41185345014](https://github.com/alimtalbi-ata/aiops/actions/runs/41185345014) IN_PROGRESS at write. It does not produce a cumulative ZIP or exercise install/upgrade/rollback. **T4/T5 NO_GO; RELEASE_STABLE=NO_GO.**


### 5/5 release inventory stop-line — 2026-10-31 10:31 Europe/Paris

- Refreshed #195 main-based `26436048ade4ff4ac20878d33dc89057c32cb2be`, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, [Quality 41185495625](https://github.com/alimtalbi-ata/aiops/actions/runs/41185495625) SUCCESS 3/3. #201 `e116d04c791b6f5a5028d6f2cc3797a547b460ec`, [Quality 41169101273](https://github.com/alimtalbi-ata/aiops/actions/runs/41169101273) SUCCESS 3/3. #209 `9d515aee54a809bf06d81d63609b06d7b7a7e571`, [Quality 41185345014](https://github.com/alimtalbi-ata/aiops/actions/runs/41185345014) SUCCESS 3/3, 22/22 source kit tests, 11/11 staged inventory tests. These are T0 contracts, not a main-based cumulative kit.
- **New audit finding:** #209 `tools/check_cumulative_release_kit.py` accepted `deploy/aiops_release.py` as both installation and rollback entrypoint, even though that script's `main()` refuses deploy/rollback and permits read-only audit only. It also accepted `deploy/deploy-acme-p0.py`, a partial four-service transaction, and did not require a separate upgrade entrypoint. File presence could falsely satisfy the entrypoint inventory gate; it never demonstrated exercised install/upgrade/rollback.
- **Targeted [draft #210](https://github.com/alimtalbi-ata/aiops/pull/210):** base #209 `9d515aee54a809bf06d81d63609b06d7b7a7e571`, HEAD `929ce398f5a3ea5660a834baf8bdb63e0bbda8ac`, changes only `tools/check_cumulative_release_kit.py` and `tests/test_cumulative_release_kit_gate.py`. Requires separate explicit install, upgrade and rollback entrypoint families; three negative regression tests cover read-only audit, partial P0 and install-only. [Exact-head Quality](https://github.com/alimtalbi-ata/aiops/actions/runs/41189139337) **IN_PROGRESS at this snapshot**; expected 25 tests, **N/N NOT_YET_OBSERVED**. This is a stricter source inventory gate, not an implemented rollback or a release package.
- #204 stacked current HEAD `08706694d73e7c2a05f7a26d25807e5e4868525d`, [Quality 41186634005](https://github.com/alimtalbi-ata/aiops/actions/runs/41186634005) SUCCESS 6/6 and other observed workflows green. 4/5 reports offline HITL 60/60 and synthetic Temporal E2E, but neither qualifies #201 T2, Core actor+tenant ACL, source provenance or T4 rollback. Latest previously audited #204 package still has 30/68 stale embedded digests; a new package on current #204 HEAD has **NOT** been independently audited here.
- **Gates:** T0 GO_LIMITED #201/#209, #210 PENDING exact CI; T1 BLOCKED actor+tenant Core/Portal; T2 NOT_QUALIFIED one integrated ACME Run; T3 NOT_ATTESTED Debian; T4 NO_GO main-based kit, install/upgrade/rollback; T5 LIVE NO_GO. `RELEASE_STABLE=NO_GO`. No main merge, runner/cron/host, GLPI write or LIVE action.


**Latest #204 kit re-audit — 2026-10-31 ~10:40 Europe/Paris:** On #204 exact HEAD `08706694d73e7c2a05f7a26d25807e5e4868525d`, [Quality 41186634005](https://github.com/alimtalbi-ata/aiops/actions/runs/41186634005) SUCCESS 6/6, independently downloaded [artifact 13037355818](https://github.com/alimtalbi-ata/aiops/actions/runs/41186634005/artifacts/13037355818). Outer ZIP **714198 bytes**, SHA256 `e4368de5d96a5a1cf51d09f52d32fd0144332a7ffddf160a6fa6ee02a021065c`, CRC 2/2 PASS; inner ZIP **772005 bytes**, SHA256 `ac464cfba547d2253dbdd7a1c07564ad13cb7be3b33a018b7496ddc4a7a1cc29`, CRC 457/457 PASS, no unsafe names/symlinks/duplicates. `FILES-SHA256SUMS` **407/407 PASS**, but embedded JSON **30/68 SHA and 30/68 byte-size mismatches**, `release=8.0.0` versus text `version=2.1.0-core-rc1.4`. Text `git_commit=7facef8d73ccaaf7f33db97707a0a7de166c1875` is a packaging checkout, not #204 source HEAD. **SEMANTIC_INTEGRITY=FAIL despite green CI.** #206's repaired kit remains a different stacked branch; #210's stricter source entrypoint gate is not yet incorporated. No install/upgrade/rollback exercised. **T4 NO_GO, RELEASE_STABLE=NO_GO.**

## 2026-10-31 11:33 Europe/Paris — newer #204 exact-head independent audit (supersedes prior artifact count only)

- Source PR #204 HEAD `fe25a4a816cebb9ae2122a09946751ed4be926f0` stacked on #194 `40d38705cf2bde3be6052340442c117a81908f65`; [Quality 41191668178](https://github.com/alimtalbi-ata/aiops/actions/runs/41191668178) SUCCESS 6/6. PG16 disposable DR PASS tables=32, not target host.
- [Artifact 13038908385](https://github.com/alimtalbi-ata/aiops/actions/runs/41191668178/artifacts/13038908385) outer ZIP **717779 bytes**, SHA256 `27bf58f1a1838bafab191147693a8ef75fbf4382763d36af6e5f0f9a537d0c1a`, 2/2 CRC PASS; nested ZIP **775752 bytes**, SHA256 `4e1a316fc1cdf5cea3e4a4adf7d41d5a9d480bb20eb94f197eb5753ae436358f`, 458 members CRC PASS, no path traversal, duplicates or symlinks.
- Sidecar `FILES-SHA256SUMS` **408/408 PASS** (the current count is 408, not the earlier 407). Disposable extraction/repack preserves **458/458 member bytes** with CRC PASS.
- Embedded `manifests/MANIFEST.json`: **38/68 matching; 30/68 SHA256 mismatches and 30/68 size mismatches**, none missing. JSON `release=8.0.0` conflicts with text `version=2.1.0-core-rc1.4`. Text `git_commit=1cb4511ef349bdc3bfa441817bd7d343360ff694` is packaging checkout, not source HEAD.
- **SEMANTIC_INTEGRITY=FAIL** notwithstanding green CI and sidecar. #206 corrected a different stacked kit; #210 validates entrypoint inventory only. Main-based cumulative install/upgrade/rollback **0/0/0 executed**; no SBOM qualification. **D3 NO_GO / RELEASE_STABLE=NO_GO**. Do not reuse this archive as a customer kit.


## 2026-10-31 17:32 Europe/Paris — exact changed #204 artifact (independent ZIP audit)

- Source PR #204 HEAD \`51616f53a3d07bdc6c109a2d6256787f0b3797e2\` (stacked on #194, not #201); [Quality 41217253473](https://github.com/alimtalbi-ata/aiops/actions/runs/41217253473) SUCCESS 6/6. [Artifact 13048882307](https://github.com/alimtalbi-ata/aiops/actions/runs/41217253473/artifacts/13048882307) outer ZIP 728672 bytes SHA256 \`df5fb76895e89a0d385d0ef3dbcf962fc65f3f8aef557748014e0cb722fb085f\`; nested ZIP SHA256 \`485da4133cfbdb7cfe848f439262b662e9cc6dc9cffbd4459b3dff4cc20b8640\`.
- Independent inspection: outer/nested CRC PASS; \`FILES-SHA256SUMS\` **412/412 PASS** (paths normalized from \`./\`); 413/413 regular file bytes preserved by in-memory extraction/repack, no duplicate, traversal or symlink. Embedded \`manifests/MANIFEST.json\`: **38/68** matching SHA256 and size, **30/68** incorrect; JSON release \`8.0.0\` vs text version \`2.1.0-core-rc1.4\`. Text \`git_commit=745a65b327a1d17004f6ac00f6e936cdf2d61d8d\` is packaging checkout, not PR HEAD. No separate cumulative upgrade/rollback entrypoints; install/upgrade/rollback **0/0/0 executed**.
- **SEMANTIC_INTEGRITY=FAIL; D3 NO_GO.** #206/#209 provenance improvements and #213 exact-source fence are separate branches and do not qualify this archive. No host, Docker, Debian or LIVE operation performed.


### 2026-10-31 ~18:40 Europe/Paris — changed #204 kit artifact, independently checked

- Source #204 HEAD \`0790872d170ec3af511993edbb1f7861689455c3\`, [Quality 41222846472](https://github.com/alimtalbi-ata/aiops/actions/runs/41222846472) SUCCESS 6/6. [New artifact 13049949421](https://github.com/alimtalbi-ata/aiops/actions/runs/41222846472/artifacts/13049949421) downloaded: outer ZIP **729166 bytes**, SHA256 \`d4a154289add6b13892d546d9fd13d9632c49675fa9c8eeed39bf26a7fd67342\`; inner ZIP **787945 bytes**, SHA256 \`cf896467e3a1a6ec880f41a8a2ecbea6e707054e08018bcdab96b8af69ab3041\`. Outer and inner CRC PASS; 462 inner members / 413 regular files; no duplicate or traversal paths; **412/412** FILES-SHA256SUMS entries match; extraction/repack preserves **413/413** regular file bytes.
- **Embedded semantic failure persists:** JSON \`manifests/MANIFEST.json\` only **38/68** size+SHA256 entries match archive bytes, **30/68** wrong; JSON release \`8.0.0\` vs text \`2.1.0-core-rc1.4\`; \`RELEASE-MANIFEST.txt\` \`git_commit=0c1b6be04a39f24e8b4a55c2ea733451789e423b\` differs from source #204 HEAD. \`deploy/install.sh\` present; cumulative upgrade and rollback entrypoints absent. **0/0/0** clean sandbox install/upgrade/rollback exercised. **SEMANTIC_INTEGRITY=FAIL; D3 NO_GO.**
- Separate draft #213 HEAD \`12a65b5733ecc96108f3cb77f96a340185f71616\` ports deterministic staged JSON provenance and strict Git-source correspondence from #209 onto an older #201 base. [Quality 41225279446](https://github.com/alimtalbi-ata/aiops/actions/runs/41225279446) SUCCESS 3/3, 28/28 offline release guard tests. It has **not** generated, installed, upgraded or rolled back a cumulative kit, and does not fix the #204 artifact. Sole main-based integration candidate remains #201 \`230feb52f64c4480f72a33e7e7c56bb12909b2ab\`. \`RELEASE_STABLE=NO_GO\`.
