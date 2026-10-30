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
