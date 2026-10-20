# RC1.6 — recovery and restore qualification

**Date:** 2026-10-20  
**Owner:** Abdelhalim Talbi  
**Branch:** `feat/core-analysis-quality-v2` — PR #21.

## Implemented this batch
1. Harden the offline verifier for private stack backups. All volume TAR members must be ordinary files or directories. Symlinks, hardlinks, device nodes and other special entries are rejected even when their checksum is valid.
2. Reject volume TARs exceeding declared per-file or aggregate size limits or member-count limits before any restore action.
3. Add regression tests for a checksum-consistent TAR symlink and device-node attack.
4. Add a required GitHub Actions PostgreSQL logical backup/restore rehearsal using a *disposable* target database, comparing source and restored table counts and selected evidence/decision ledger row counts.

## Proof boundaries
- Passing PostgreSQL rehearsal proves the logical PostgreSQL test database can be dumped and restored on CI; it does **not** qualify Temporal visibility, MariaDB, user data volumes, crash consistency, an application-level recovery point, or the Debian target server.
- The current volume backup is explicitly **online_snapshot**, **application_consistent=false**. Restore must remain operator-authorized and isolated.
- Never upload private backup archives, environment secrets or raw database exports to the public repository or CI artifacts.
- An uncompleted CI run is not a release acceptance result.

## Next engineering batch
- Disposable full-stack recovery rehearsal including PostgreSQL, Temporal + visibility, MariaDB and stack-owned volumes, with writer quiescence and deterministic pre/post data assertions.
- Fault injection at backup interruption, partial restore, worker restart and fencing ownership.
- Produce a signed machine-readable recovery report and clearly label the recovery points and any untested elements.
