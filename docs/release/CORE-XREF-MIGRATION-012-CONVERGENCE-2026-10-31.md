# Core ITSM xref migration ordinal convergence — 2026-10-31

**Scope:** one narrowly scoped 3/5 Core contract correction, coordinated by 5/5. This branch is stacked on PR #205; it is **not** the single main-based integration candidate. That candidate remains PR #201. No merge or main push.

## Source and collision

- PR #205 formerly introduced `db/migrations/009_itsm_xref_read.sql`, conflicting with `db/migrations/009_ai_decision_ledger.sql` from the #194/#204 HITL stack.
- This branch relocates **the identical SQL content** to `db/migrations/012_itsm_xref_read.sql` and updates only the disposable PostgreSQL Quality workflow path. SQL semantics, Core route, tenant checks, and evidence guards are unchanged.
- Intended combined order: `001_schema.sql`, `004_operational_model.sql`, existing `005`–`008` as applicable, `009_ai_decision_ledger.sql`, `010_evidence_identity.sql`, `011_hitl_decision_outbox.sql`, then `012_itsm_xref_read.sql`. Confirm the **actual** repository migration inventory and dependencies before integration; do not assume a successful isolated #205 CI proves this combined order.
- The isolated #205 Quality job currently applies `001_schema.sql`, `004_operational_model.sql`, and `012_itsm_xref_read.sql` in disposable PostgreSQL. It does **not** exercise the combined 009–012 chain.

## Acceptance and safety

1. Exact-head Quality must pass Core HTTP auth/tenant adversarial tests, projection tests and PostgreSQL 16 disposable HTTP tests.
2. Before port to #201, apply the ordered **combined** migrations on a fresh disposable PostgreSQL 16 instance and separately test rollback/recovery, including duplicate ordinal detection from #210. Check migration table state and row hashes.
3. Core xref is synthetic-fixture-backed only: no verified GLPI source adapter, production OIDC, live tenant attestation or real Evidence/CI link. Return UNKNOWN when provenance, identity or ownership is not established.
4. Never migrate an existing database merely by renaming an already-applied migration. Inspect its applied migration ledger first. If `009_itsm_xref_read.sql` was ever applied, **stop and design an explicit state-aware migration plan**; do not replay or delete tables.
5. Revert this branch's commits to restore #205's original source layout; disposable test databases may be discarded and recreated. Production rollback is not authorized or exercised.

**Release gates:** D0 pending exact-head CI; D1 combined migration NOT_RUN; D2 browser/API same SHA NOT_RUN; D3 clean install/upgrade/rollback NOT_RUN; D4 customer sign-off NOT_ATTESTED. `RELEASE_STABLE=NO_GO`.
