# ADR — Core disposable same-major PostgreSQL 16 recovery gate (2026-11-01)

**Status:** proposed, DEV only. **Owner:** Core xref / NOC / Evidence / GLPI. **Base:** sole architect Draft #234 at `6a8c9bcab294e85a9831b34ae84980bf2b8649b1`. **Scope:** Core test, dedicated Core CI workflow, and this ADR only. No schema/runtime/Portal/Worker/Policy/shared Quality changes.

## Decision

The previous #270 native PostgreSQL 16 test was **NOT_QUALIFIED** (14 PASS, 1 SKIP) because the shared Quality runner lacked `/usr/lib/postgresql/16/bin/pg_dump`. The architect correctly held it back while selectively porting only the TLS tests. This change reintroduces **only** the held-back native recovery test as a strict non-skipping gate, using the official `postgres:16-bookworm` client job image and a separate disposable `postgres:16-alpine` server. The dedicated workflow is `.github/workflows/core-pg16-native-recovery.yml`, not the architect-owned Quality workflow.

A loopback TCP forwarder inside the disposable job container exposes the disposable PG16 service at exactly `127.0.0.1:5432/aiops`. The test refuses any other target, any server major other than 16, and any missing/wrong-major `pg_dump` or `pg_restore` client. The workflow checks out the exact PR HEAD, asserts SHA, and requires **one test passed, zero skips**. Missing prerequisites are failures, never successful skips.

The test creates two fresh isolated databases (CREATE fails if names preexist), installs the real `001_schema.sql`, `004_operational_model.sql`, `009_ai_decision_ledger.sql`, `010_evidence_identity.sql`, `011_hitl_decision_outbox.sql`, `012_itsm_xref_read.sql`, and `013_actor_delegation_replay_ledger.sql`. It populates synthetic tenant ownership, a consumed JTI/nonce and a revocation. It uses **native PG16** `pg_dump --format=custom`, computes SHA256, verifies the copied archive, rejects an intentionally tampered copy, then uses native `pg_restore --single-transaction --exit-on-error` to a *different empty disposable database*, without SQL rewrites. It compares populated source/target rows and proves replay and revocation are still rejected. Reapplying 009–013 to the populated restored target must be idempotent.

On successful qualification the workflow retains the **synthetic-only** `core-audit.pgcustom`, `core-audit.pgcustom.sha256`, and `recovery-manifest.json` in a seven-day CI artifact. The artifact includes no real GLPI/IdP data or credential. CI logs include `DISPOSABLE_PG16_ARCHIVE_SHA256`. The archive digest is per-run, not a fixed hash. The workflow itself verifies the SHA256 file and manifest before upload. A source PR is not qualified until its own exact-head workflow is green and artifact digest verified.

## Rollback, audit and negative authority

Rollback of this PR is a **code/test/workflow/ADR revert only**. Do not DROP, DELETE, TRUNCATE, or mutate the immutable 013 nonce/JTI/revocation ledger in any persistent database. Restoring a new disposable DB from an archive and a code-only revert are **not** an in-place production downgrade. A populated production downgrade would require a separately approved data-preserving runbook and evidence; this test cannot authorize it.

IdP, mapping and GLPI native User/Profile/Entity/Ticket authorities remain synthetic test sources. No human `ALLOW`, no ticket `LINKED` or xref `VERIFIED` is inferred from these tests, HMAC, `verified=true`, or ticket text. `actor_authorization=UNKNOWN`, `link_status=UNKNOWN`, `RELEASE_STABLE=NO_GO`. No real GLPI writes, external authority calls, SSH, host access, LIVE executor, deployment or main merge.

## Qualification command

Dedicated workflow uses:

```bash
/tmp/core-pg16-recovery-venv/bin/python -m unittest discover -s tests -p 'test_core_actor_pg16_native_sha_restore.py' -v
cd "$AIOPS_PG16_RECOVERY_ARTIFACT_DIR" && sha256sum --check core-audit.pgcustom.sha256
```

The separate Core-owned workflow avoids altering shared Quality and reports a hard failure on missing native PG16 clients. Handoff requires exact base/head SHA, 1/1 test with zero skips, exact-head workflow URL, retained artifact ID and independently checked SHA256 where available.
