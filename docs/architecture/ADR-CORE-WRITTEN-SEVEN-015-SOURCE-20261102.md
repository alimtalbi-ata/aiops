# ADR Core — 015 API-written seven-event source readback (2026-11-02)

Status: SOURCE_ONLY / synthetic disposable PostgreSQL 16; not a release authorization.

## Decision

Extend the existing Core-owned `canonical_seven_pg_source` with a **read-only** `read_core_written_seven` preflight. Reuse the existing HTTPS/TLS Basic dispatch with a distinct pinned `/v3/core-written-seven-readback` path, not a Portal route and not an actor permission API. This deliberately does **not** add a migration or change 015, 013, 014, Worker, ACME, Portal, or shared workflows.

The source-side readback requires a fresh, non-revoked synthetic actor grant scoped to tenant, actor subject and issuer, Incident, Run, GLPI instance, ticket, entity and `run:read`; five fresh Core ownership rows; exactly seven Evidence and seven Core API-written `run_events` with `event_key=SYN-EVT-01..07`, `INGEST/SYNTHETIC_SOURCE_EVENT/PASS`, one matching Evidence per event, identical payloads, actor/source issuer fields in the immutable synthetic provenance, and two distinct canonical SHA256 domains:

- `aiops.core-source-event-payload.v1`
- `aiops.core-full-run-event.v1`

The source issuer is **not** the actor's IdP issuer; their equality is neither required nor asserted. Source-side grant data is a **synthetic test fixture** and does not independently authenticate a human. The Basic credential authenticates the *source service transport*, not the actor. The returned JSON is transport-bound and not a portable signature or GLPI authorization. A real IdP introspection and native GLPI human ticket/CI rights remain separate release gates. Never promote this readback to `ALLOW`, `LINKED`, `VERIFIED`, or an ACME full-event hash equivalence claim.

## Qualification contract

Dedicated disposable PG16 CI applies 001/004/009–014 and 015; exercises a transaction rollback before applying 015 and reapplying it; writes seven SYN-EVT events via the **actual `core.main.app` ASGI `/api/runs/{rid}/events`** route (not direct run_events INSERT); replays an exact event idempotently; reads through the Core SQL producer and TLS/Basic source adapter; denies foreign actor, tenant, Run, Incident, ticket, revoked grant and expired grant (7/7 UNKNOWN); rejects stale source and invalid TLS/Basic; compares audit 013/014 counters and native `pg_dump/pg_restore` readback with exact hashes. No SKIP permitted.

The redacted `core-written-seven-015.json` receipt includes the exact source HEAD, migration order, event IDs and both hash domains, seven negative decisions, audit counts, native PG16 archive checksum, and `decision=UNKNOWN`, `link_status=UNKNOWN`, `human_glpi_attested=false`, `portable_signature=NONE`. The archive itself is not retained.

## Deployment, handoff, rollback

This is a **source-only** candidate for architect selective integration. It does not mount a production endpoint, qualify Portal usage, or execute on Debian. Before in-place Debian DB changes, operator/architect must separately attest backup, migration ordering, active traffic, rollback and port/SSO/GLPI gates. Local operator previously verified host TCP 7777 health; external SSO/GLPI and portal uniqueness remain unverified.

Rollback: revert only this code/test/workflow/ADR delta. Never DOWN/DROP a populated 015 column/index and never mutate/delete immutable 013/014 audits. No LIVE, real GLPI writes, host SSH/Docker, second persistent stack, stable push or merge. `RELEASE_STABLE=NO_GO`.
