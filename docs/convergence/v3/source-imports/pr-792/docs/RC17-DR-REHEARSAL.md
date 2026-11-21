# AIOps 2.0 RC1.7 — automated disaster recovery drill

**Author:** Abdelhalim Talbi. **Date:** 2026-10-20.
**Source of truth:** GitHub PR #21, branch `feat/core-analysis-quality-v2`.

## Implemented
- `tests/postgres-dr-rehearsal.sh` is a fail-closed, local-loopback-only DR exercise.
- Creates a disposable database only after rejecting any pre-existing rehearsal target.
- Takes a fresh custom PostgreSQL dump; validates the TOC and confirms a deliberately corrupt archive fails validation.
- Restores into its own temporary database with `--single-transaction --exit-on-error`.
- Compares every table in the `aiops` schema by row count plus a deterministic MD5 aggregate of JSON row representations, not merely the number of tables.
- Destroys only the named temporary database it created, and cleans up the dump on exit.
- Writes a machine-readable non-secret JSON proof at `reports/postgres-dr-rehearsal.json`; CI uploads this artifact regardless of the later release result.

## Scope and limitations
This exercises a **disposable CI PostgreSQL logical backup**. It is not yet a full stack restore, does not validate application-consistent online volumes, MariaDB, Temporal/visibility, real provider or production RTO/RPO. The full-stack restored state cannot be marked PASS based on this drill. No LIVE effects authorized.

## Release acceptance gate
Require the exact branch-head workflow to complete successfully (build, migrations, database upgrade, Temporal E2E, DR drill, ZIP verification). Preserve the previous qualified RC1.5 release until then.

## Next
1. Extend disposable restore to Temporal and its visibility database, MariaDB, and independently scoped volumes.
2. Inject faults at failure points; verify degraded-state labeling and recovery continuation.
3. Publish verified RTO/RPO metrics *only if actually measured*, never estimate operational results from CI.
