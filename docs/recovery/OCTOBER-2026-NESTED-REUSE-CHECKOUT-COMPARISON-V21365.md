# AIOps V2.13.65 — Historical nested-source deduplication against the PR checkout

## Historical context and business need

The V2.13.64 bounded ZIP inventory can inspect one level of source files within cumulative release ZIPs without extracting or executing them. However, the existing V2.13.53 `zip_reuse_compare.py` compared **only top-level `members`** to the current checkout. Nested source files were not included in exact-byte reuse decisions, creating a risk of redundant rewrites.

The original private V2.13.6.1 Hybrid Final archive was previously verified in V2.13.64. This change relies on the **previously recorded metadata**, not on a fresh read of its private bytes:

| Source | Recorded SHA-256 | Reuse treatment |
| --- | --- | --- |
| `AIOPS-V2.13.6.1-HYBRID-FINAL.zip` | `0f382f64a3da7ad0e81c3fde33a2c800ea73844f1ea7f38711ab7b17979a5f29` | Original cumulative archive; do not commit |
| `05-Backup/AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip` (nested) | `83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550` | Previously found identical to standalone V2.13.4 ZIP |
| `03-Architecture/AIOps_V2.13.0_Architecture_Organigramme_HLD_LLD.zip` (nested) | `cc60a2b26829a37db4a771f15ea597ab37e45452698a8e1688a5cc2e0f29ca93` | Seven documents/images, no verified Python source |

The original Playwright F20.13 source files remain unavailable as complete, byte-verified originals. Historical shell transcripts are **not** a replacement.

## Architecture and interface

`Private ZIP -> zip_source_recovery.inventory(..., inspect_nested=True) -> reviewed metadata JSON -> zip_reuse_compare.compare_inventory(metadata, index_checkout(checkout)) -> metadata-only reuse decision`.

The comparator now includes `nested_members` in addition to `members`. Every nested result retains `archive`, `archive_sha256`, `nested_archive_member`, `nested_archive_sha256`, `member_path`, `member_sha256`, `origin_kind=nested`, and `import_authorized=false`. The response adds `nested_entry_count` while preserving the existing schema and statuses. The same relative path in an outer and inner ZIP is treated as two independent provenance identities.

Decisions: `EXACT_PATH_DUPLICATE`, `EXACT_BYTES_OTHER_PATH`, `DIVERGENT_PATH_REVIEW`, `NEW_CANDIDATE_REVIEW`, `BLOCKED_REVIEW`. Exact SHA equality proves byte identity **only**, not module completeness, functionality, safety or release readiness. No decision authorizes automatic import.

Fail-closed constraints: nested source count and inspection flag must agree, nested archive path and SHA must be valid and must match the same inventory's `opaque_archives` record with `NESTED_METADATA_ONLY_INSPECTED` status, nested member must remain `quarantine_review_required` and `import_authorized=false`; unsafe paths, duplicate provenance keys, sensitive-looking or syntactically broken sources are rejected or blocked. Opaque architecture documents are excluded from source-code comparison. No network, browser, container, service or database calls.

## Isolated offline qualification

```bash
python -m recovery.tools.zip_source_recovery /private/AIOPS-V2.13.6.1-HYBRID-FINAL.zip \
  --inspect-nested --output /private/zip-inventory.json
python -m recovery.tools.zip_reuse_compare /private/zip-inventory.json \
  --checkout /private/clean-aiops-pr-checkout --output /private/reuse-comparison.json
python -m unittest discover -s tests -p 'test_zip_*.py' -v
```

The ZIP and output reports stay private. The checkout should be pinned to a reviewed commit and should contain no runtime secrets. The synthetic tests cover the complete ZIP inventory-to-checkout path, nested exact matches, changed paths, missing candidates, duplicate identities, forged parent-ZIP SHA/status provenance, unsafe nested provenance and blocked sources. The existing isolated historical ZIP workflow runs these tests on PR changes. They **do not** qualify the Debian `:17777` portal, F20.13 real screenshots, or production.

## Reuse conditions and rollback

Before migrating any historical module: independently verify the full original bytes and SHA chain, assess interface/dependency compatibility, review secrets/privacy, compare tests and business behavior, and document a dry-run with fail-closed rollback. Never use historical `PASS` logs or screenshots of login pages as business evidence.

Rollback: revert the comparator, its tests and this document on PR #36. The change is read-only and adds no schema migration, service restart, port, LIVE action or write to GLPI/n8n/Grafana/DB/CMDB. No merge into `main` is authorized by this work.
