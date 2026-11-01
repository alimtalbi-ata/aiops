# ADR — Core-owned canonical seven-event PostgreSQL source producer (2026-11-01)

**Status:** focused source Draft; disposable synthetic qualification only. **Owner:** Core/NOC. **No new migration.**

## Decision

Move the canonical seven-event SQL readback **out of the test-only HTTP handler** into `app/core/canonical_seven_pg_source.py:read_canonical_seven`. A separately authenticated disposable TLS/Basic source harness calls this Core-owned producer in a fresh PostgreSQL 16 transaction. The producer executes `SET TRANSACTION READ ONLY` before any query, checks the exact issuer/subject/tenant/Incident/Run/GLPI instance/ticket/entity/permission grant, checks five exact Core ownership records, checks a single DEMO Run and synthetic Incident, and reads exactly seven Evidence plus seven run_events. It independently recomputes `aiops.core-source-event-payload.v1` and `aiops.core-full-run-event.v1` SHA256 values and binds the provenance and freshness of each row.

The producer returns the existing `aiops.core-canonical-seven-source-binding.v1` proof or `None`; the existing independently pinned TLS client verifies the proof and emits the informational `aiops.core-canonical-seven-source-receipt.v1`. Neither stage returns human GLPI `ALLOW` or `LINKED`. `tenant_resource_ownership.verified` in the disposable fixture is **not** native GLPI rights attestation. A TLS-bound proof is not a portable signature and ACME full-event hash equivalence remains `NOT_VERIFIED`.

## Qualification and consumer contract

The dedicated PG16 workflow must execute 15/15 tests, zero SKIP, using installed 001/004/009–013 plus disposable 014, with native PG16 custom-format dump/restore and reapplication/immutable 013/014 assertions inherited from the existing suite. New Core-owned producer test covers exactly seven negatives: foreign actor, tenant, Run, ticket, entity, revoked grant and stale ownership. Other existing tests cover source tampering, expiry, TLS CA rejection, audit non-mutation, source mismatch and rollback. The redacted `core-owned-producer.json` carries exact source HEAD, seven distinct payload/full-event hashes, seven UNKNOWN negatives, audit counts and canonical SHA256. It contains no subject, bearer, DB secret, lease token or portable authorization credential.

ACME consumer must compare these hash domains **by exact byte domain and schema**, never reinterpret a Core hash as an ACME hash. The Core producer is not an ACME ingestion endpoint, native IdP, native GLPI permission source, or production service; its HTTPS harness remains disposable and synthetic. The installed migrations and immutable 013/014 ledgers are unchanged.

**Rollback:** revert the four focused source changes (Core producer, Core test, dedicated workflow, this ADR); **CODE_ONLY_KEEP_013_014_AUDIT**, no DOWN/DROP or audit deletion. No Debian host, persistent container, GLPI write, deploy or LIVE.
