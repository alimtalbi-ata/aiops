# ADR — Core seven-source readback and 013/014 recovery qualification (2026-11-01)

**Scope:** Core-owned disposable test and dedicated workflow only. **Status:** proposed, source-only. No runtime authorization or schema change.

## Contract

The existing `aiops.core-canonical-seven-source-receipt.v1` is generated only after a separate HTTPS authority (ephemeral CA, verified TLS and Basic service credentials) reads synthetic PostgreSQL 16 Incident/Run, seven Evidence rows and seven run_events in read-only transactions. It binds exact actor issuer/subject, tenant, Run, Incident, GLPI instance/ticket/entity, permission `run:read`, freshness, revocation and the pinned source event. The payload hash domain `aiops.core-source-event-payload.v1` and full event hash domain `aiops.core-full-run-event.v1` are distinct. Neither is asserted equal to ACME's full-event domain.

One added test `test_z_v2_native_014_audit_restore_and_fail_closed_receipt` uses that authority, then installs 014 **after** the existing disposable 001/004/009–013 fixture and seeds one explicitly unverified, synthetic 014 terminal audit fixture referencing the same Run. This is **not** evidence of Core terminal handler execution. It checks foreign actor/tenant/Run/ticket/entity, corrupted full hash and revoked proof all return no source receipt (UNKNOWN). It verifies 013 nonce/revocation and 014 receipt preservation, failed transactional append rollback, PG16 native custom archive SHA256, restore into a new disposable database, 013/014 migration reapply and immutable trigger enforcement. No DOWN migration, no audit deletion or production database.

CI uploads only a redacted machine-readable `seven-014-recovery.json` and its SHA256, bound to the checkout HEAD. No raw archive, lease token, service secret, human subject, bearer or GLPI credential is retained. The fixture's temporary databases are deleted **only within disposable CI**.

## Limits and integration

- `source_preflight=PASS_SYNTHETIC_ONLY` is source-integrity evidence, **not** native IdP/GLPI human authorization.
- `decision=UNKNOWN`, `link_status=UNKNOWN`, `human_glpi_attested=false`, `acme_full_event_equivalence=NOT_VERIFIED`, `execution_allowed=false`, `effect_allowed=false`.
- The 014 row in this test is fixture data, not a Core /dead receipt from a live transition. Existing dedicated Core terminal PG16 tests independently qualify /dead.
- No new CMDB, no external GLPI writes, no host/container/port claim. Host TCP 7777 remains NOT_VERIFIED; 17777 is distinct.
- Source-only Draft targets the sole candidate branch; architect exclusively integrates. **RELEASE_STABLE=NO_GO**.

## Rollback

Revert only this Core test, dedicated workflow change and ADR. Preserve installed 001/004/009–014 and immutable 013/014 rows. Do not execute schema DOWN/DROP or host volume operations. CI-created databases are disposable and are not persistent host resources.
