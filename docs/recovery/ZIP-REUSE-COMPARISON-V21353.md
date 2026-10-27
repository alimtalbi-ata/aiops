# V2.13.53 — historical ZIP reuse comparison (HLD/LLD)

**Status:** isolated offline candidate; no source import, production access or runtime attestation. This report does not certify complete original modules.

## Purpose and provenance

PR #36 already contains recovery and STAR components. Comparing an original ZIP inventory to an actual checkout before migration avoids re-implementing exact byte duplicates and identifies changed files requiring manual reconciliation. Inputs are the reviewed `aiops-zip-source-inventory/v1` metadata produced by `recovery/tools/zip_source_recovery.py`, plus a local checkout. Original archive SHA-256 and member path/digest remain bound to each decision.

## HLD

`Original ZIP (read-only) -> ZIP inventory (SHA pinned) -> reuse comparator <- local Git checkout (read-only)`

The comparator outputs a **metadata-only** JSON report. It never reads production services, makes HTTP calls, executes archived code, opens browser sessions or writes into the checkout. No GitHub push is performed by the CLI. Paths named credentials, tokens, cookies or secrets and symlinks are excluded from the checkout index. The inventory input is bounded to 8 MiB.

## LLD and interpretation

- `EXACT_PATH_DUPLICATE`: same relative path and SHA-256, no import needed.
- `EXACT_BYTES_OTHER_PATH`: same SHA-256 elsewhere, inspect relocation and interfaces before reuse.
- `DIVERGENT_PATH_REVIEW`: same relative path but changed bytes; compare interfaces/tests manually; never overwrite.
- `NEW_CANDIDATE_REVIEW`: no matching path or bytes; validate complete original source and dependencies.
- `BLOCKED_REVIEW`: sensitive-content signal, invalid syntax or unknown sensitive flag; never automatically import.

All statuses set `import_authorized=false`. SHA-256 is evidence of byte identity, not trust, authenticity, correct functionality or full historical recovery. A syntactically valid fragment may still be truncated.

## Offline usage

```bash
python -m recovery.tools.zip_source_recovery ORIGINAL-V2.13.4.zip --output /private/zip-inventory.json
python -m recovery.tools.zip_reuse_compare /private/zip-inventory.json --checkout /private/aiops-checkout --output /private/reuse-report.json
python -m unittest discover -s tests -p 'test_zip_*' -v
```

Keep original ZIPs, full inventories, evidence PNGs and reports with potentially identifying paths in private quarantine; do not commit them without independent secret/privacy review. For F20.13 Playwright, first obtain the **complete** source archives, compare to existing Chromium adapter and verify original tests. Historical logs or fragments are not sufficient.

## Rollback and limitations

Rollback is removal of `zip_reuse_compare.py`, its test and documentation; no checkout, production or database state changes occur. `index_checkout` is a point-in-time byte comparison, not a Git worktree cleanliness/commit attestation; a review must record the exact checked-out Git SHA independently. Concurrent mutation of checkout files can change observed hashes; do not promote without a clean immutable checkout. The comparator does not infer functional equivalence from names, hashes of different bytes, or historical PASS claims.
