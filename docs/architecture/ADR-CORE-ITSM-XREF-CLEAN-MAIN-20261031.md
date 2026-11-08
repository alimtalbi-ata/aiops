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
