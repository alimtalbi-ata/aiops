# ACME/Twin — pinned governance source-index contract (SYNTHETIC)

**Scope:** additive, read-only ACME-only provenance projection on sole Draft #234. The source-index is an independently Git-blob-pinned *index of pointers*, not a second CMDB, a real governance record, a ticket, or a runtime authority. All values are derived again from the pinned SQL graph or catalog; the index cannot authorize a value.

## Source boundaries

- Graph: `db/migrations/005_seed_acme.sql`, Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`, 18 CI and 17 directed consumer→dependency edges. Node `site` and service `criticality` are **synthetic**. SAN-A → Pure01 → PAY01 → OraclePay → Payments: `ACME-E08,E06,E04,E02`; `ACME-E01` connects Payments to its business CI. Reverse reachability yields only **candidate** impacted services (ERP, Payments), not observed outages or verified failover.
- Catalog: `tests/fixtures/acme_enterprise_incident_catalog_v1.json`, Git blob `78e749c623d7ee7ea1d33a74577b4f7b696f3207`. Only `scenarios[].maintenance_window` is a simulated offset on the fixture clock, not a real approved window.
- Change: the Golden SQL `scenario_steps.CHANGE_LOOKUP` is a **planned** lookup at +45 seconds, with no Change ID, approval, maintenance authority, or successful API readback.
- New index: `tests/fixtures/acme_twin_governance_source_index_v1.json`, Git blob `e77a0abbb53176488ec49d7c0c9f8581d4620b3f`. Its five non-UNKNOWN pointers identify only those SQL/catalog selectors. Datacenter, owner, team, SLA, OLA, Change and actual maintenance have no independent source record and remain `UNKNOWN`. No names, identities, contracts, or windows are inferred from PARIS, a planned step, or a synthetic scenario.
- `twin_service_context_offline` returns `governance_source_records` with selector, source Git blob, source CI references, value, authority scope, provenance and tenant scope. Source pointers are not authenticated runtime facts. A tampered index is rejected by its pinned Git blob; a forged manifest is rejected by the existing full canonical replay validation.

## Determinism and acceptance

Golden scenario `SCN-GOLDEN-PAYMENT-P1`, seed `20261018`, 7 SYNTHETIC events, canonical JSON SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`. The index is **not** embedded in the canonical replay, so its bytes do not change. The storyboard retains the same source event IDs, timestamps, roles N1/N2/N3/incident commander (planned), P1 candidate, HIGH estimated, and all six checkpoints `NOT_EXECUTED`. `tenant_id`, `incident_id`, `run_id`, `ticket_id`, `evidence_ids` remain UNKNOWN/null/empty. `impact_observed`, `itil_priority_confirmed`, actual maintenance and recovery proof remain UNKNOWN/false.

Five new methods in the already Quality-discovered `tests/test_acme_synthetic_incident_catalog.py` check pinned index, scenario-bound source derivation, maintenance/Change abstention, forged owner/SLA/tenant/index rejection, and byte-identical Golden replay/checkpoints.

```bash
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python tools/generate_acme_incidents.py --scenario REDUNDANT_SAN_PATH_LOSS --seed 20261018 --output /tmp/acme-governance-replay.json
sha256sum /tmp/acme-governance-replay.json
```

**Release and runtime:** `RELEASE_STABLE=NO_GO`. No GLPI write, Core/Portal/Worker/Policy changes, shared CI edits, migrations, deploy, host access, or LIVE. Owner may only propose a focused PR; architect alone integrates. Before any positive governance metadata, require tenant-scoped authenticated CMDB/GLPI authority with source, timestamps, freshness, verified CI/service linkage and approved contract/change relationships.

**Rollback:** revert only the focused ACME generator, source-index fixture, tests and contract documentation. Pinned 005 graph, catalog, replay and main remain untouched.
