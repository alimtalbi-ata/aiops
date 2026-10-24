# V2.13.63 — Cumulative ZIP recovery, nested archive quarantine

## Verified original sources (2026-10-24)
Original ZIP bytes were read from the user's private Library in an isolated workspace, without extraction to GitHub, HTTP calls, Docker operations, or runtime access. All three ZIPs passed `ZipFile.testzip()` CRC checks. All 17 Python members (5 + 9 + 3, **including byte-identical duplicates**) passed `ast.parse`; syntax is not evidence of complete dependencies or business correctness.

| Original archive (Library, not published) | Archive SHA-256 | Archive ZIP members |
| --- | --- | ---: |
| AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip | `83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550` | 10 |
| AIOPS-V2.13.6.1-HYBRID-FINAL.zip | `0f382f64a3da7ad0e81c3fde33a2c800ea73844f1ea7f38711ab7b17979a5f29` | 32 |
| AIOPS-V21310-STAR-PORTAL.zip | `cdca139131dbbac7adb2f811077c25e94dd01899a6ec33c37ea067d26a351d87` | 8, including 3 directory entries |

## Complete historical code members, paths and SHA-256

The following members are complete **within the original archives**; this does **not** prove that the historical application, its dependencies, or the original deployment are complete. Paths below are relative to the archive's top-level directory.

| Version | Original member path | SHA-256 | Current decision |
| --- | --- | --- | --- |
| 2.13.4 | `tools/build_real_replay.py` | `f71a568f4229402a6f6b5238552efbdd18fa41320c8c285afedc386812bbb97d` | Keep private; existing `demo/star_legacy_replay_adapter.py` is the safer bounded replay adapter |
| 2.13.4 | `tools/assemble_hybrid.py` | `ffce55bf4c100642e751e73857a90e50b6f9bc030e4caba8f2bc71268db437d3` | Exact Git blob already in `recovery/legacy_v2134/tools/assemble_hybrid.py`; do not duplicate |
| 2.13.4 | `tests/test_replay.py` | `e1fadcf8c20ab19ba1e696aa11237f42ec300a64ce9745b496023648eaaef8aa` | Original tests retained privately; compare against modern replay tests |
| 2.13.4 | `tests/chromium_hybrid.py` | `cc109ccdd9787ee5fec1c57447dd5290487d03cb747a18adb3caf512696fea6b` | Historical Chromium harness; requires isolated browser review |
| 2.13.6.1 | `01-Demo/tools/build_real_replay.py` | `f71a568f4229402a6f6b5238552efbdd18fa41320c8c285afedc386812bbb97d` | Byte-identical to 2.13.4; no second import |
| 2.13.6.1 | `01-Demo/tools/assemble_release_v21361.py` | `e617ce963aafdff742e7d0e6850cbea48b19dd40529b0b8be4546384350fed82` | Full member; quarantine pending dependency/side-effect review |
| 2.13.6.1 | `01-Demo/tests/chromium_executive_full.py` | `dda9c66609f888136958c392df84fb70708bdb6ce0288cb1fcd99cbb83ec9a83` | Full member; isolated Chromium qualification pending |
| 2.13.10 | `portal_demo_public_v21310.py` | `5bee897914ec958af0f715f24eee229b9f9539a3df5da4f9c43cb8746ad60ee0` | Compare with current `app/portal/portal_demo_public_v21310.py`; no blind overwrite |
| 2.13.10 | `install.py` | `2aca6ff462cf1cf2c1d9be8f544b1d061d212af6745ea4171af48b00d219d6a0` | Installation script quarantined; never run against Debian |
| 2.13.10 | `tests/test_patch.py` | `5a3fa8a170ceb8d2467ec80eb6466bcbd5b03b8b28da2ae6bf73d1783d155a4e` | Historical test, not a runtime qualification |

The original 2.13.6.1 archive contains two **opaque nested ZIPs**:
- `03-Architecture/AIOps_V2.13.0_Architecture_Organigramme_HLD_LLD.zip` — 9,470,244 bytes, SHA-256 `cc60a2b26829a37db4a771f15ea597ab37e45452698a8e1688a5cc2e0f29ca93`; **NOT inspected recursively**.
- `05-Backup/AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip` — 29,354 bytes, SHA-256 `83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550`; byte-identical to the separately inventoried V2.13.4 original.

## Functional change and architecture

Existing `recovery/tools/zip_source_recovery.py` previously rejected V2.13.6.1 in its entirety because a nested architecture ZIP exceeds the 2 MiB source-member limit. It now accepts **opaque nested `.zip` members only**, up to 32 MiB per nested member and within the unchanged 64 MiB archive budget and 200:1 compression-ratio fence. Nested archives are hashed, identified as `OPAQUE_NESTED_ZIP_NOT_INSPECTED`, and explicitly `import_authorized=false`. They are **not recursively opened or extracted**. Normal source files remain capped at 2 MiB, and `recover()` still forbids selecting a `.zip` for extraction.

HLD: private Library ZIP → bounded structural validation → SHA-256 member inventory → deduplication against existing Git code → private quarantine → manual review → isolated tests → PR. No path from this workflow to production services.

LLD: `_validated_infos` applies extension-specific size ceilings but common total/ratio/path/symlink fences. `inventory` hashes nested bytes without parsing them and returns optional `opaque_archives` metadata. Existing `aiops-zip-source-inventory/v1` member records remain compatible with `zip_reuse_compare.py`.

## Reuse and tests

Business need: accelerate recovery of the original STAR portal, replay and demonstration assets without re-implementing identical code. The original V2.13.4 builder consumes `run.json`, `ai-ledger.json`, `evidence.json` and generates HTML; it may include operator-supplied metadata in HTML, so it is not promoted as a secure portal renderer. Chromium scripts require Playwright/Chromium in isolated fixtures, and the V2.13.10 installer is **not** authorized to run. Dependencies, privacy review and runtime authenticity remain unresolved.

Added regression fixtures exercise a >2 MiB incompressible opaque nested ZIP and a highly compressible nested ZIP bomb, including refusal of nested extraction. Run `python -m unittest discover -s tests -p 'test_zip_*.py' -v` and check GitHub Actions **STAR historical ZIP source recovery (isolated)**. Original archive CRC/AST checks are separate from the new GitHub tests; no live E2E has been run.

## Rollback and release fence

Revert the changes to `recovery/tools/zip_source_recovery.py`, `tests/test_zip_source_recovery.py` and this document on PR #36. No persistent application state, DB, CMDB, ticket, service or container is modified. Do not merge automatically. No secrets, original archives, operator exports or browser sessions are published.
