# ADR — Core ITSM xref v1 on clean DEV main (2026-10-31)

**Status:** Proposed for architect review; no production migration or deployment. **Owner:** Core xref team 3/5. **Base:** `780a8e03b32e0a3969fc36f6aeee69bacb5b45ab`. **Source:** #205 HEAD `15ba526d718e9676289558dcaa31a7be820449bb`; ordered migration name from #212 `0c07090bed333e90aab1248ffcfc51e10d3f3c67`.

## Decision

Port only the existing Core read-only xref router, shared fail-closed consumer, adversarial HTTP/contract tests and disposable PostgreSQL tests to a dedicated clean-main branch. Keep `aiops.core-itsm-xref-read.v1` and the existing route unchanged. Reuse the **identical SQL body** of #205 migration `009_itsm_xref_read.sql`, renamed `012_itsm_xref_read.sql` by #212, to avoid the competing `009_ai_decision_ledger.sql`. This is a migration name change, **not** a new schema design.

The GitHub Quality workflow runs the three new negative-readback/Evidence tests explicitly, the full Core HTTP and mock contract suites, and the disposable PostgreSQL 16 Core HTTP suite. The isolated test applies 001→004→012; it **does not** qualify combined 009→010→011→012 or any existing database upgrade. Full ordered migration, DR/rollback and same-SHA #201 integration remain architect gates.

## Trust boundaries

GLPI is authoritative for ticket/CMDB, Evidence is append-only, Core owns the Incident/Run↔ticket xref. A ticket title containing `RUN-*` never qualifies a link. Authenticated service identity, server-derived actor/tenant ACL, permission, exact identifiers, provenance and freshness must all pass. No real GLPI ingestion, entity/CI readback or production IdP is included; field link is `UNKNOWN` until independently authenticated tenant-scoped readback. No Portal/Worker/Policy/packaging changes.

## Migration / rollback

Disposable CI only. Do not run migration 012 on any persistent database until a reviewed ADR/migration registry and combined 009–012 upgrade/rollback test exist. Never apply both the historical `009_itsm_xref_read.sql` and `012_itsm_xref_read.sql` to the same DB. Revert this PR's commit to roll back source; discard ephemeral PostgreSQL to roll back test data. Live schema rollback is not authorized.

## Remaining gates

Independent GLPI ticket/entity/CI authenticated readback and entity ACL, attested association ingestion, IdP tenant, CI freshness, Twin import and source attestation, integrated #201/#205 exact-SHA E2E, combined ordered migrations, CI exact-head, release approval. `RELEASE_STABLE=NO_GO`.

## Additional independent ownership proof gate (2026-10-31)
The Core xref v1 schema and SQL remain unchanged. A signed xref history plus
`tenant_resource_ownership.verified=true` alone cannot prove independent
GLPI entity/tenant ownership. The read API now additionally requires a
separately keyed `aiops.core-ownership-proof.v1` JSON manifest at the
server-configured absolute `AIOPS_XREF_OWNER_PROOFS_PATH`, with
`AIOPS_XREF_OWNER_ATTESTATION_KEY` independent of
`AIOPS_XREF_ATTESTATION_KEY`. All five ownership rows are bound by HMAC
to kind, ID, tenant, verified, source_event_id, observed_at and known_at.
Missing/malformed/altered proof yields `UNKNOWN`, without business IDs.

The disposable PostgreSQL fixture generates **synthetic** proofs after
inserting its own rows. It is not an authenticated GLPI adapter or an
independent source readback. No deployment should provision the proof
manifest from unverified DB rows; the producer must authenticate GLPI/Core
and tenant/actor scope independently. Until then field status is UNKNOWN.
The migration 012 is staged for architect review only; the combined
009 AI / 010 Evidence / 011 HITL / 012 xref chain, idempotence and rollback
remain NOT_QUALIFIED on a disposable PostgreSQL instance. Never apply it
to a persistent DB. Rollback is revert of this branch and deletion of CI DB.

## Disposable combined migration qualification
A separate CI-only database tests 001→004→009 AI→010 Evidence→011 HITL→012 xref,
a full transactional DDL rollback, and a second idempotent application.
The three predecessor SQL fixtures are pinned by Git blob SHA-1 from
`#194@40d38705cf2bde3be6052340442c117a81908f65`; they are **test-only
snapshots**, not installed migrations. This does not qualify the final
architect-integrated migration versions, data downgrade, or any persistent
database upgrade. CI refuses non-loopback PostgreSQL and always drops the
isolated test database. Final chain still requires requalification on the
architect's exact integrated HEAD.
