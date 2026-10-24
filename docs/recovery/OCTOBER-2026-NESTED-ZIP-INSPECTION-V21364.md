# AIOps V2.13.64 — bounded historical nested ZIP source discovery

## Need and historical context

The private V2.13.6.1 cumulative ZIP contains an architecture bundle and an exact nested copy of the V2.13.4 Hybrid Replay ZIP. The V2.13.63 metadata inventory already recorded their identities; neither nested payload had been inspected for source members by the recovery tool. This change enables **optional metadata-only, one-level inspection** of nested ZIP source candidates without importing, executing, extracting, or publishing historical bytes.

The original archive bytes are **not embedded in this commit**. The following fingerprints are carried forward from the previously verified V2.13.63 private archive metadata, not re-verified from original bytes in this commit:

| Original outer ZIP | Nested member | Nested member SHA-256 | Size |
| --- | --- | --- | ---: |
| `AIOPS-V2.13.6.1-HYBRID-FINAL.zip` | `03-Architecture/AIOps_V2.13.0_Architecture_Organigramme_HLD_LLD.zip` | `cc60a2b26829a37db4a771f15ea597ab37e45452698a8e1688a5cc2e0f29ca93` | 9,470,244 |
| `AIOPS-V2.13.6.1-HYBRID-FINAL.zip` | `05-Backup/AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip` | `83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550` | 29,354 |

The second nested member matches the already separately inventoried V2.13.4 archive hash. Treat it as a likely exact duplicate; do not reimport its modules.

## Architecture / interfaces

`recovery/tools/zip_source_recovery.py` retains the existing SHA-pinned single-descriptor outer ZIP reader, path/casefold/symlink fences, CRC-checked source-member reads and no-overwrite quarantine extraction. The new **opt-in** `inventory(archives, inspect_nested=True)` opens only the bytes of each bounded inner ZIP through `io.BytesIO`. It returns `nested_members` records with the outer archive SHA-256, nested ZIP member path and SHA-256, inner source member path and SHA-256, byte size, syntax-only status, sensitive-pattern indicator, and exact-byte duplicate pointer.

Default `inventory(archives)` behavior remains opaque. `--inspect-nested` is an inventory-only CLI flag; it is **rejected with `--apply`**. The preexisting top-level `members` and `member_count` schema are unchanged, so `zip_reuse_compare.py` continues to compare only top-level entries. Nested entries are separate, explicitly `import_authorized=false` and `reuse_status=quarantine_review_required`; no nested extraction is available.

Bounded limits: at most 8 nested ZIPs per invocation, 1,000 total inner members, 64 MiB total uncompressed inner bytes, 32 MiB per opaque inner non-source asset, 2 MiB per eligible source member, and a 200:1 compression-ratio fence. The path validator rejects traversal, Unicode normalization aliases, Windows reserved names, casefold duplicates and symlinks. Inner ZIPs found inside an inspected ZIP are **not recursively opened**. Sensitive-looking source content is never printed; only a boolean is emitted. AST parse success is not proof of a complete module.

## Offline operator recipe

Use a private isolated workstation or disposable workspace containing the original ZIP. Do not run on production Debian. Never publish the resulting raw ZIP or source without separate review.

```bash
python -m recovery.tools.zip_source_recovery \
  /private/recovery/AIOPS-V2.13.6.1-HYBRID-FINAL.zip \
  --inspect-nested --output /private/recovery/nested-inventory.json
python -m unittest discover -s tests -p 'test_zip_*.py' -v
```

Inspect the metadata JSON privately. Before considering any source reuse, independently confirm outer SHA, nested SHA, inner source SHA, dependencies, complete file bytes, interfaces, data sensitivity, tests, and divergence from the current PR branch. Never treat metadata as a verified runtime capture, historical code completeness attestation, or authorization for LIVE actions.

## Qualification and limitations

Synthetic regression tests cover nested source discovery, exact-byte duplicate detection, secret-pattern flags, invalid Python, traversal, ZIP bombs, large opaque media, no recursion, shared member/archive budgets and CLI refusal of extraction. GitHub Actions workflow `STAR historical ZIP source recovery (isolated)` runs the ZIP regression suite on PR changes. These tests do **not** establish that the original private architecture bundle contains any specific module, that F20.13 Playwright originals have been recovered, or that portal `:17777` has passed runtime E2E.

## Rollback / production fence

Revert the commit changing `recovery/tools/zip_source_recovery.py`, the matching `tests/test_zip_source_recovery.py` changes and this document on the draft branch. No migrations, ports, Docker operations, GLPI/n8n/Grafana writes, database writes, or runtime restarts are required. Never merge automatically.
