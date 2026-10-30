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
