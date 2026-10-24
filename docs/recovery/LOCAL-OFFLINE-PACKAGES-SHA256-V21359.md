# Local offline packages — provenance inventory (2026-10-24)

Verified read-only in the current isolated workspace by opening each ZIP and SHA-256 hashing the archive bytes and the listed module bytes. These are **incremental packages**, not the historical F20.13 originals and not complete GitHub checkouts. No archive bytes or unreviewed code are committed here. Exact original paths are the package basenames under local `/mnt/data/`; these paths are local evidence only and may not exist on other machines.

| Version | Original local ZIP | Bytes | ZIP SHA-256 | Internal candidate module path | Module SHA-256 |
|---|---|---:|---|---|---|
| V2.13.50 | `AIOps-V21350-Historical-ZIP-Recovery-Offline.zip` | 8993 | `97220cc349f6a377c0be1f0934a520dbd3b448e3378079060ad302b2e5b54456` | `recovery/tools/zip_source_recovery.py` | `9c8c3d0e1f9e2faa095866704dcd793584646539dcb3dd4498f41eda97cf598c` |
| V2.13.51 | `AIOps-V21351-SHA-Pinned-Historical-Recovery-Offline.zip` | 12523 | `00abd6a4f6c3ca38632197ac6f540663c63cc19f95b0a9f588c961af68df5a14` | `recovery/tools/zip_source_recovery.py` | `0d80730c7a57dd45c5162fbfb4949f447e641a093a2e1fa0bc3614cf499ac0a3` |
| V2.13.52 | `AIOps-V21352-Atomic-Historical-Recovery-Offline.zip` | 10968 | `524d506042a0c9fb1bc3d4b8f93fb6c54a41b7d16b85b5ae8c6d56d166fa6bf5` | `recovery/tools/zip_source_recovery.py` | `8f55e2b16ebc1e1196c20b94a0ea2ac2faeb5c4ee833134202ba0c29b36ce17d` |
| V2.13.53 | `AIOps-V21353-Historical-Reuse-Comparison-Offline.zip` | 17870 | `8136cc806c73c0b1e99378559785ed83fe074cd94eb2f7ded14691cafa5cd192` | `recovery/tools/zip_source_recovery.py` | `b44bd935dcfa2317d1329bbe0d6b4ea0691208524e6a00136dcb241ba904d2b0` |
| V2.13.54 | `AIOps-V21354-STAR-Checkpoint-Plans-Offline.zip` | 8410 | `027558f55de98894c77767b367aa6bfd0b3a40c691119181ccab8edbe2ba9887` | `demo/star_checkpoint_plan_builder.py` | `6403f1a8ec71a2c3a4006e26a590665347eb78940192774a41b871417147ba29` |
| V2.13.55 | `AIOps-V21355-STAR-Chromium-Mask-Proof-Fence-Offline.zip` | 13550 | `86f7c915fdaadb97cb1a169939fcec49f6d6b0088adbd24baba45aae00b14979` | `demo/star_snapshot_browser.py` | `b9046e3ce7368e7d4f94bb47be602a19f01f8f4cc99a93266b5cda02073228fb` |
| V2.13.56 | `AIOps-V21356-STAR-Chromium-CSS-Overlap-Fence-Offline.zip` | 17839 | `f97a52893e9acd203c2052dfbb0f3617473191edb4ca7e13f33e22f5c7bcbf14` | `demo/star_snapshot_browser.py` | `a74bb5fd3e12fef32db339f547af216286a7335e8e69918f9750365584eb72f1` |
| V2.13.57 | `AIOps-V21357-STAR-Chromium-Proof-Visibility-Offline.zip` | 16258 | `2a0f0905f3e25d6ace291aee3d7d5645f6b2ad0591c94642c0761da951a88ac3` | `demo/star_snapshot_browser.py` | `3ada912347965d59335f3ee2702c4a8d02149ffad644d7e8a7fe0ccb53ec584e` |

## Business and architecture mapping

- V2.13.50–53: safe offline recovery of candidate ZIP source trees; descriptor-atomic parsing, SHA pinning, compare/dedup and quarantine. Python standard library; read-only archive inspection; no import into runtime. Use only after independent SHA confirmation and security review.
- V2.13.54: strict per-checkpoint capture plan construction for Grafana :3000, n8n :5678 and GLPI :8080. Pure Python with existing STAR choreography and browser request fence; plans are not screenshots.
- V2.13.55–57: successive hardening of Chromium read-only screenshot collection, CSS mask overlap and proof visibility. Playwright is an optional isolated QA dependency; no runtime auth or live execution proven.

## Reuse and tests

Reconcile candidate file hashes against the exact GitHub PR head before any reuse. Identical content: do not copy. Divergent content: diff, inspect for secrets and license constraints, run targeted unit tests and isolated Chromium tests, then propose a reviewed patch. Treat generated logs as untrusted, never publish sessions, tokens, private screenshots or archive payloads. These ZIPs contain only incremental subsets; do **not** claim they restore full F20.13, Temporal, DGX, RAG, CMDB, Policy or the portal. The canonical source remains the PR branch.

## Rollback

This document contains no executable imports and changes no deployment. Revert this documentation commit if any local provenance record is superseded by a more authoritative archive. Production remains untouched.
