# ADR — Core disposable actor authorities and audit-preserving PG16 recovery (2026-11-01)

**Status:** Proposed / Core-owned source and test gate only. **Base:** sole Draft #234. **No real GLPI, IdP, production database, or LIVE access.**

## Decision

Keep `aiops.core-actor-resource-authorization.v1` **negative-only**: a successful introspection, source mapping HMAC, GLPI User/Profile/Entity/Ticket readback, and first JTI/nonce consumption still yield `200 UNKNOWN`, not `ALLOW`. Missing or inconsistent source authority yields `UNKNOWN`; an unavailable replay ledger yields `503 UNKNOWN`. A text `RUN-*` in a ticket never establishes `LINKED`.

Three **independently launched loopback HTTP servers** simulate IdP introspection, OIDC subject-to-GLPI mapping, and GLPI native human session. The production adapters retain pinned HTTPS URL validation and assert TLS verification, redirect refusal and independent credentials. The test-only transport bridge routes these HTTPS requests to loopback HTTP sockets. **This is not a real TLS certificate or external GLPI trust qualification.** The source test rejects issuer mismatch, foreign tenant, mapping revocation, absent ticket-read profile bit, and wrong ticket entity. It proves source contract and non-enumeration behavior, not human authorization.

## PostgreSQL 16 installation, backup, recovery and downgrade

A new disposable test applies **001 → 004 → 009 AI → 010 Evidence → 011 HITL → 012 xref → 013 actor ledger** in a newly created loopback database. It populates immutable tenant ownership, a consumed JTI/nonce, and a revocation. It runs real `pg_dump --format=custom`, decodes with `pg_restore --file`, and replays into a **different, empty disposable PostgreSQL 16 database** using `psql ON_ERROR_STOP=1`. The hosted runner currently supplies PostgreSQL 18 client binaries: the test removes exactly the incompatible `SET transaction_timeout = 0;` line from generated SQL, with no DDL or data rewriting. It verifies all three tables row-for-row, tests replay/revocation after restore, and reapplies 009–013 idempotently without changing audit data. A same-major native PostgreSQL 16 client restore remains an additional qualification gate.

A production-like downgrade is **code-only** while preserving 013 schema and audit rows. Never `DROP`, `TRUNCATE`, `DELETE` or rewrite the 013 nonce/revocation ledger. Archive checksum, verified restore, retained source database, exact PostgreSQL major version, and an architect-approved recovery plan are prerequisites before any persistent migration. This rehearsal does **not** qualify destructive in-place downgrade or restore under live writes. No schema migration is introduced by this PR.

## Gates and ownership

Only `tests/test_core_actor_disposable_sources.py`, `tests/test_core_actor_pg16_archive_restore.py`, the two Core-owned test discovery bridges and this ADR change. No Portal, Worker, Policy, shared Quality, packaging or candidate modifications. The architect alone selectively integrates. Existing Quality automatically discovers both additions via the Core-owned test bridges; exact-head CI must be observed before promotion.

**Rollback:** revert the test/ADR commits only. Never drop or mutate installed 013 audit tables, even after reverting actor application code. GLPI authority and independent OIDC subject mapping still require operational qualification. RELEASE_STABLE=NO_GO.
