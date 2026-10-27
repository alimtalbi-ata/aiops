# AIOps historical recovery — nested source quarantine V2.13.66

**Date:** 2026-10-24. **Scope:** offline historical preservation; no Debian production interaction.

## Business need and provenance

Recover complete, byte-identical source candidates from historical cumulative releases without rewriting working modules or importing unreviewed scripts. The previously inventoried original `AIOPS-V2.13.6.1-HYBRID-FINAL.zip` (SHA-256 `0f382f64a3da7ad0e81c3fde33a2c800ea73844f1ea7f38711ab7b17979a5f29`) contains `AIOPS-V2.13.6.1-HYBRID-FINAL/05-Backup/AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip` (SHA-256 `83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550`). Both SHA values are from the private V2.13.64 metadata-only inventory, not freshly revalidated in this cycle.

A source candidate within the nested ZIP is `AIOPS-V2.13.4-HYBRID-REPLAY-STAR/tests/chromium_hybrid.py`, SHA-256 `cc109ccdd9787ee5fec1c57447dd5290487d03cb747a18adb3caf512696fea6b`. **No completeness or runtime claim is made**; a syntax-valid file can still depend on missing modules. `assemble_hybrid.py` was already identified as an exact duplicate of code in the current repository; do not reimport it.

## Architecture and interfaces

New `recovery/tools/nested_source_quarantine.py` reuses the structural ZIP, path, sensitive-content and stable-descriptor guards in `zip_source_recovery.py`. Interface: `quarantine_nested_source(archive, nested_member, source_member, expected_outer_sha256=..., expected_nested_sha256=..., expected_member_sha256=..., quarantine=..., apply=False)`.

The three SHA-256 pins must be reviewed independently. The function validates the complete outer and one-level inner ZIP structure, refuses traversal, nonregular members, oversized/high-ratio content, suspicious secrets, Python syntax errors, and SHA mismatches. It verifies the outer file hash again on the same descriptor before any write. It does not recursively traverse a third ZIP or execute/import source.

The default mode is **validated dry-run, zero writes**. Explicit `--apply` writes only one source file to an existing private quarantine directory using `O_NOFOLLOW | O_EXCL` and permission `0600`; there is no overwrite or automatic deployment.

Example on a private isolated workstation (replace the archive location; never run against live mounts):

```bash
python -m recovery.tools.nested_source_quarantine ./AIOPS-V2.13.6.1-HYBRID-FINAL.zip \
  --nested-member AIOPS-V2.13.6.1-HYBRID-FINAL/05-Backup/AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip \
  --source-member AIOPS-V2.13.4-HYBRID-REPLAY-STAR/tests/chromium_hybrid.py \
  --outer-sha256 0f382f64a3da7ad0e81c3fde33a2c800ea73844f1ea7f38711ab7b17979a5f29 \
  --nested-sha256 83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550 \
  --member-sha256 cc109ccdd9787ee5fec1c57447dd5290487d03cb747a18adb3caf512696fea6b
```

To quarantine after independent review, create an isolated directory manually and add `--quarantine <private-existing-directory> --apply`. Do **not** push recovered raw files or any browser sessions, tokens, real captures or private records.

## Qualification, migration and rollback

The synthetic suite `tests/test_zip_nested_source_quarantine.py` checks the dry-run, three independent pins, private file permissions, no overwrite, traversal, secrets, invalid Python, compression bomb, symlinks and generic CLI error handling. The historical ZIP recovery GitHub Actions workflow runs it with the existing `test_zip_*.py` regression suite.

Migration policy: compare each quarantined file to current GitHub code by SHA before considering a reviewed, isolated adapter or test. F20.13 Playwright collectors remain untrusted until authenticated application-view tests demonstrate the expected page instead of a login screen. This change **does not** qualify portal `:17777`, ACME SAN P1 / Payments P2, Temporal, or any runtime capture.

Rollback: revert the commits adding `nested_source_quarantine.py`, its synthetic tests, workflow changes and this document on the draft PR branch. Quarantined files, if any, remain local and must be reviewed/deleted manually; no runtime rollback is needed.
