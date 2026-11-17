# ADR — Core 015 event_key bridge for installed PG16 001/004/009–014

**Scope:** Core-only, disposable DEV qualification. No host deployment or GLPI write.

## Problem

The canonical Core `POST /api/runs/{id}/events` and `/command` writers use
`aiops.run_events.event_key`, but the installed Core xref/HITL chain
001/004/009–014 does not apply the historical optional 008 migration.
The resulting SQL error causes HTTP 500 and transaction rollback. Worker #325
reproduced this failure using the actual Core ASGI app.

## Decision

Install **015_core_run_event_idempotency.sql** after 014 in a single
transaction. It adds `event_key text` and a partial unique
`(run_id,event_key) WHERE event_key IS NOT NULL` index. Both statements are
idempotent and compatible with an installation that already applied 008.
It does not rewrite any existing event, 013 nonce/revocation or 014 terminal
receipt. A failed transaction rolls back the column/index atomically.
There is **no persistent DOWN/DROP**: retain immutable audit and existing events.

The Core writer rejects a reused command idempotency key when its Run or
command differs, and rejects a reused event key with different content. An
exact event replay may succeed with its original expected_version without
mutating Run state. Both writers retain their existing row locks and
single-transaction SQL boundary.

## Qualification and limitations

Dedicated PG16 test uses installed 001/004/009–014 plus 015, verifies
rollback-before-commit, repeated 015, seven synthetic SYN-EVT-* payloads via
the actual Core `/events` API, `/command`, seven HTTP negative cases,
an injected post-insert SQL failure, native PG16 `pg_dump/pg_restore`,
and the 013/014 immutable triggers. It emits a redacted JSON receipt.

**Security boundary:** existing Core `AIOPS_INTERNAL_TOKEN` is a service
bearer, **not independently attested tenant/actor/IdP authorization**.
The seven synthetic payloads do not prove source authority, ACME hash-domain
equivalence or GLPI human rights. They cannot be presented as LINKED,
VERIFIED or ALLOW. A separate scoped ingestion/authenticated-source
contract is required before tenant-bound production use.

**Rollout:** architect review; isolated PG16 test; backup/restore evidence;
explicit operator approval for any later DEV migration. No Debian SQL
was executed. Rollback for this PR: revert Core code, retain schema 015 and
all 013/014 audit rows; do not DROP on a populated DB.

**Release:** `RELEASE_STABLE=NO_GO`; no LIVE effects.
