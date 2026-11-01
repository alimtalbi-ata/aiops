# ADR — Core actor negative-only replay gate and 013 audit-preserving rollback (2026-11-01)

**Status:** Proposed, DEV-only, owner Core; architect integration required.  
**Source:** sole Draft #234, base SHA `e8328b9f65fcf01addbe1c59b595466f8e48af15`.  
**Contracts:** `aiops.core-actor-resource-authorization.v1`, `aiops.core-oidc-glpi-actor-binding.v1`, `aiops.core-actor-delegation-replay.v1`, unchanged `aiops.core-itsm-xref-read.v1`.

## Decision

1. Keep the current **UNKNOWN-only** actor endpoint. Bearer service `actor:resource:authorize` and server tenant ACL run first; opaque actor delegation is introspected using independently configured HTTPS IdP credentials. Issuer, audience, active/revoked, exact tenant/Run/Incident/GLPI ticket/entity/permission/nonce, JTI, timestamps and actor subject are checked. Never infer a Run from `RUN-*` ticket text.
2. Core xref signed history, exact Run→Incident and independently authenticated GLPI Ticket/Entity/CI readback must pass before the native actor preflight. HMAC and `verified=true` alone are insufficient.
3. A separately authenticated mapping authority must bind the OIDC subject to the exact GLPI User, tenant, instance, JTI and nonce, with source event, MAC and expiry. Native **human-session** GLPI reads must return the exact active User (`is_active=1`), active Profile with native `ticket` READ bit 1, active Entity, and exact Ticket in that Entity. A profile ID alone, READMY-only bit, service session, or synthetic mapping cannot authorize. This is a conservative preflight, not an `ALLOW`.
4. Only **after** these preconditions, Core invokes `aiops.actor_delegation_consume` against the installed 013 PostgreSQL ledger. SHA-256 hashes of subject/JTI/nonce and a domain-separated canonical digest of tenant, Run, Incident, GLPI instance, ticket, entity, permission and nonce bind the request. The database serializes consume/revoke on issuer/JTI, rejects revoked/expired/replayed tokens and persists immutable rows. An unavailable ledger returns 503 with decision `UNKNOWN`; refusal/replay returns 200 `UNKNOWN`. Even a successful first consume **still returns UNKNOWN**, not ALLOW. No positive authorization path exists.
5. Core does not write GLPI, execute actions, or own Worker/Policy delivery. The REJECT claim/ACK eight-field wire remains owned by the existing Core module, coordinated with Worker #251. This change does not alter it.

## Installed migration and upgrade gate

Retain the installed ordinal chain `001→004→009 AI→010 Evidence→011 HITL→012 xref→013 actor replay`. The 013 migration is additive and idempotent; it must be run in a transaction after 012. A fresh PostgreSQL 16 disposable database is mandatory for integration. The existing test `test_core_actor_nonce_pg16.py` exercises actual 013 SQL, concurrent single-winner, revocation, replay, populated reapplication and transactional rollback. The new test copies **populated** 013 audit rows using PostgreSQL COPY into a separate disposable restore schema and verifies row-for-row equality before rolling back the restore transaction.

These are **SQL logical round-trip tests**, not evidence of a production archive, full persistent schema downgrade or tested real GLPI rights. CI must execute the installed migration suite on the **exact proposed HEAD**.

## Data-preserving recovery and downgrade plan (NOT executed outside disposable CI)

The safe application downgrade is **code-only**: revert the actor replay call while leaving 013 audit tables, functions, triggers and rows intact. Do **not** run `DROP TABLE`, `TRUNCATE`, `DELETE` or `UPDATE` on either immutable 013 ledger table. Revocation facts are never deleted by a rollback. For a future explicitly approved database recovery:

1. Stop writes to the **disposable test** database and record exact commit, schema version, migration list, UTC timestamp, row counts, primary-key uniqueness and SHA-256 of the archived backup. No production database access is authorized by this ADR.
2. On the disposable database only, use PostgreSQL 16 `pg_dump --format=custom --no-owner --no-acl --schema=aiops --file=actor-audit-pre-change.dump` with an explicit isolated `--dbname`. Encrypt/restrict the archive, record `sha256sum`, and inspect it with `pg_restore --list`.
3. Restore into a **new isolated database**, never over an existing one, with `pg_restore --no-owner --no-acl --single-transaction --dbname=<disposable_clone> actor-audit-pre-change.dump`. Verify table/row counts, issuer+JTI keys, nonce uniqueness, timestamps, revocation source IDs, immutable triggers and actual consume/revoke behavior before accepting the clone.
4. If a previous application version cannot read 013, leave the tables in place and disable the new call by reverting code; do not destructively downgrade the schema. A future destructive schema downgrade requires a separate ADR, independently verified backup, audit-retention decision and tested forward recovery. Without these, status **NO_GO**.

## Test and security boundary

- Unit tests use only synthetic IdP/mapping/GLPI transports and fake PostgreSQL connections; no external network.
- PG16 tests require `AIOPS_XREF_CI_DISPOSABLE=1`, `GITHUB_ACTIONS=true`, loopback `127.0.0.1:5432/aiops`, user `aiops`, PostgreSQL major 16, and create/drop their own uniquely named test database. No DB production.
- Core xref and native actor rights must not enumerate foreign tenants; 401/403 for service access, otherwise 200 UNKNOWN or 503 UNKNOWN without business IDs.
- Real OIDC issuer trust, source-authenticated human GLPI User/Profile/Entity/Ticket read permission, signer governance, live revocation ingestion, real backup restoration and integrated ITIL D1/D2 remain **NOT_ATTESTED**.
- `link_status=UNKNOWN`; blast-radius paths remain `HYPOTHESIS_NOT_CONFIRMED` without source telemetry. `RELEASE_STABLE=NO_GO`.

## Revert

Revert only this PR's Core code/tests/ADR commits. **Do not revert or drop migration 013 or its audit rows.** No new migration in this PR. Architect alone integrates into #234; no owner merge/main push/deploy.
