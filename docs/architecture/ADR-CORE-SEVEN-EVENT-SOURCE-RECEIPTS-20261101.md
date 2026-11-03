# ADR — Core seven-event source receipts and immutable audit (2026-11-01)

**Owner:** Core/NOC/Evidence. **State:** SOURCE_CANDIDATE / SYNTHETIC_ONLY. **Release:** NO_GO.  
**Base:** sole integration Draft #234, exact SHA `bbe95d9894df13ab910c2b99ccb3d09ec32aa678`.  
**Scope:** Core adapter, disposable PG16/TLS tests and Core-owned dedicated workflow only. No schema or production writes.

## Decision

Retain `aiops.core-canonical-seven-source-binding.v1` as a **negative-only** precondition. After an independently configured, tenant/GLPI-instance-pinned HTTPS source readback has passed certificate and hostname validation, distinct service credentials, issuer, actor subject, tenant, Incident/Run, ticket/entity, `run:read`, freshness, revocation and all seven event hash checks, Core may emit an informational receipt via `canonical_seven_source_receipt(...)`. Failure returns `None`; no source data or foreign identifier is enumerated.

Receipt schema: `aiops.core-canonical-seven-source-receipt.v1`. Fields include exact tenant/Incident/Run/GLPI ticket/entity, actor issuer and **SHA256 of actor subject** (not raw subject), source event ID and payload digest, seven ordered evidence IDs and separate payload/full-event digests, observed/known/expiry, transport provenance, full source-proof digest and receipt digest. `decision=UNKNOWN`, `link_status=UNKNOWN`, `source_preflight=PASS_SYNTHETIC_ONLY`, `portable_signature=NONE`. The receipt is a locally computed digest of an authenticated TLS response, **not a portable digital signature, authorization credential, native GLPI attestation, or independent ACME hash equivalence proof**. Do not accept a client-supplied receipt to authorize a ticket or human actor.

Hash domains are explicitly different:

- `aiops.core-source-event-payload.v1`: canonical JSON of `{"schema":domain,"event":payload}`, SHA256.
- `aiops.core-full-run-event.v1`: canonical JSON of `{"schema":domain,"event":full_event}`, SHA256.
- `aiops.core-canonical-seven-transport-proof.v1`: canonical JSON of the TLS source proof, SHA256.
- `aiops.core-canonical-seven-receipt-hash.v1`: canonical JSON of receipt excluding its own digest, SHA256.
- ACME full-event domain: **NOT_VERIFIED / NOT_EQUIVALENT** until ACME owner supplies the producer's exact canonical bytes, field set, version and independent fixture digest. Never silently reinterpret `source_payload_hash` as an ACME full-event hash.

The independently authenticated disposable source reads actual PostgreSQL 16 Incident, Run, seven Evidence and seven run_events under read-only transactions; the test-only grant and immutability triggers are **not** operational GLPI User/Profile/Entity/Ticket authority or installed Evidence immutability. A source preflight success must not be promoted to `ALLOW` even after the first successful nonce consumption.

## Tests and acceptance

Dedicated Core workflow `.github/workflows/core-canonical-seven-binding-pg16.yml` installs PostgreSQL 16 and `001/004/009/010/011/012/013`, checks exact PR SHA, runs twelve PG16/TLS tests and requires zero skips. The two new tests validate machine-readable receipt domains and digest recomputation; exact actor/tenant/Run/ticket/entity non-enumeration; tampered, missing, reordered, future or revoked source proofs; replayed and revoked JTI denial by the installed 013 functions; and unchanged immutable 013 row counts. Existing tests cover the source transaction, TLS trust, seven actual rows and full/payload distinction.

```bash
AIOPS_XREF_CI_DISPOSABLE=1 GITHUB_ACTIONS=true PYTHONPATH=app \
  python -m unittest discover -s tests \
  -p test_core_actor_canonical_seven_binding_pg16.py -v
```

Qualification is **not** claimed until an exact-head CI run reports `12/12 PASS, 0 SKIP`. Separate native PostgreSQL 16 `pg_dump/pg_restore` recovery workflow remains authoritative for data-preserving restore; it is not automatically requalified by these receipt tests.

## Dependencies and rollback

Coordinate with ACME owner on full-event canonicalization, event ID, sequence, provenance and immutable hash mapping before any equivalence claim. The native human GLPI `ticket:read` permission and independent IdP→GLPI User/Profile/Entity/Ticket mapping remain unqualified. The runtime terminal `DEAD` API requested by Worker is a **separate Core-owned backlog**: proposed read-only audit response should bind tenant, event_id, owner, terminal reason, attempts, proposal hash/revision, lease expiry and immutable delivery evidence; no shared Core-file edits in this PR.

Rollback is a code/test/workflow/ADR revert only. Never DROP, TRUNCATE, UPDATE or DELETE `aiops.actor_delegation_nonce_ledger` or `aiops.actor_delegation_revocations`. Keep installed migrations `001/004/009–013` and all populated audit rows. No real GLPI write, external network, host SSH, deployment, LIVE or executor.
