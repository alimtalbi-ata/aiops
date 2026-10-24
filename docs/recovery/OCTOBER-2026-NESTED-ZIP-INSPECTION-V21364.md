# AIOps V2.13.64 — bounded historical nested ZIP source discovery

## Need and historical context

The private V2.13.6.1 cumulative ZIP contains an architecture bundle and an exact nested copy of the V2.13.4 Hybrid Replay ZIP. The V2.13.63 metadata inventory already recorded their identities; neither nested payload had been inspected for source members by the recovery tool. This change enables **optional metadata-only, one-level inspection** of nested ZIP source candidates without importing, executing, extracting, or publishing historical bytes.

The original archive bytes are **not embedded in this commit**. The following fingerprints are carried forward from the previously verified V2.13.63 private archive metadata, not re-verified from original bytes in this commit:

| Original outer ZIP | Nested member | Nested member SHA-256 | Size |
| --- | --- | --- | ---: |
| `AIOPS-V2.13.6.1-HYBRID-FINAL.zip` | `03-Architecture/AIOps_V2.13.0_Architecture_Organigramme_HLD_LLD.zip` | `cc60a2b26829a37db4a771f15ea597ab37e45452698a8e1688a5cc2e0f29ca93` | 9,470,244 |
| `AIOPS-V2.13.6.1-HYBRID-FINAL.zip` | `05-Backup/AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip` | `83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550` | 29,354 |

The second nested member matches the already separately inventoried V2.13.4 archive hash. Treat it as a likely exact duplicate; do not reimport its modules.

## Original nested members verified in this cycle

The **original private V2.13.6.1 ZIP bytes** were reopened in an isolated workspace. Its outer SHA-256 matched `0f382f64a3da7ad0e81c3fde33a2c800ea73844f1ea7f38711ab7b17979a5f29`. Both nested ZIP SHA-256 values matched the previous inventory, and their member bytes were read with ZIP CRC verification. The architecture ZIP contains **7 document/image members and no Python or other source-code members**. The backup ZIP contains **10 historical source/document members** and matches the separately inventoried V2.13.4 archive by SHA-256. Thus the architecture bundle is valuable documentation, not a recovered F20.13 Playwright source.

| Original nested architecture member | Bytes | SHA-256 (original bytes) |
| --- | ---: | --- |
| `03_HLD_Architecture_Logique.pdf` | 565,474 | `6e5753914768671237e7dd21e6807b773cc31db4882d57eda5b0472a3752d750` |
| `04_LLD_Conception_Detaillee.pdf` | 571,955 | `632263349626cb2186ce176b063309196caa1453f8840c7f00a9e6a234fb6f4e` |
| `03_HLD_Architecture_Logique.docx` | 1,980,235 | `951673b09b64b07886e90df0ffef023b691ad5db96f879e9a270646316f8e93c` |
| `01_Organigramme_AIOps_v2130.png` | 2,043,158 | `d2c79cca37ad53af2caf55f25811db24755b5549d73aed0402bcfeaaadd6ba18` |
| `02_Document_Architecture_Generale.docx` | 1,980,049 | `e82a937d2f5422182fa22284d2a3de34e9b050d85fa9634a8adf0a1fd391b5c2` |
| `04_LLD_Conception_Detaillee.docx` | 1,981,045 | `3521da1fde0167ad60bb5d1a9aacbf96457a525b7fa91e268f5524da7ebab42f` |
| `02_Document_Architecture_Generale.pdf` | 564,844 | `e207d03f195f4d5a553e9eb7caf31e0b16d84de82e2f7a42c6aae6dab6df4c98` |

These are **hashes and filenames only**. Document contents were not reviewed for secrets, contractual constraints, or technical correctness, and no original PDF/DOCX/PNG is committed. Do not claim the architecture is complete or production-approved from these fingerprints.

## Architecture / interfaces

`recovery/tools/zip_source_recovery.py` retains the existing SHA-pinned single-descriptor outer ZIP reader, path/casefold/symlink fences, CRC-checked source-member reads and no-overwrite quarantine extraction. The new **opt-in** `inventory(archives, inspect_nested=True)` opens only the bytes of each bounded inner ZIP through `io.BytesIO`. It returns `nested_members` source records and `nested_assets` opaque PDF/DOCX/PNG/SVG/JPEG or deeper-ZIP fingerprint records with the outer archive SHA-256, nested ZIP member path and SHA-256, inner source member path and SHA-256, byte size, syntax-only status, sensitive-pattern indicator, and exact-byte duplicate pointer.

Default `inventory(archives)` behavior remains opaque. `--inspect-nested` is an inventory-only CLI flag; it is **rejected with `--apply`**. The preexisting top-level `members` and `member_count` schema are unchanged, so `zip_reuse_compare.py` continues to compare only top-level entries. Nested source and asset entries are separate, explicitly `import_authorized=false` and `reuse_status=quarantine_review_required`; no nested extraction is available.

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

Synthetic regression tests cover opaque architecture-document SHA fingerprinting, nested source discovery, exact-byte duplicate detection, secret-pattern flags, invalid Python, traversal, ZIP bombs, large opaque media, no recursion, shared member/archive budgets and CLI refusal of extraction. GitHub Actions workflow `STAR historical ZIP source recovery (isolated)` runs the ZIP regression suite on PR changes. These tests do **not** establish that the original private architecture bundle contains any specific module, that F20.13 Playwright originals have been recovered, or that portal `:17777` has passed runtime E2E.

## Rollback / production fence

Revert the commit changing `recovery/tools/zip_source_recovery.py`, the matching `tests/test_zip_source_recovery.py` changes and this document on the draft branch. No migrations, ports, Docker operations, GLPI/n8n/Grafana writes, database writes, or runtime restarts are required. Never merge automatically.
