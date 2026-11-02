# ACME/Twin — pinned Event → correlation → Twin impact contract (SYNTHETIC)

**2026-11-01, ACME P1.** This contract is an offline source-review fixture, **not** an Event ingestion, ITIL Incident, GLPI ticket, Core Run, Evidence receipt, Analyst/Critic execution, Policy/HITL decision or SIMULATE effect. All runtime checkpoints are **NOT_EXECUTED**. It adds no second CMDB, Incident Store or orchestration path.

## Source and identities

- Reuse `db/migrations/005_seed_acme.sql`, pinned Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`, with **18 CIs / 17 directed consumer→dependency edges**; scenario `SCN-GOLDEN-PAYMENT-P1`, seed `20261018`, seven fixture-clock events.
- Reuse governance source index blob `e77a0abbb53176488ec49d7c0c9f8581d4620b3f` and vertical ITIL plan blob `e74e7b67d0d58e8eb1c2e4b54b1b0bf688694d13`. No re-port of #252/#248.
- New independently pinned `tests/fixtures/acme_synthetic_event_impact_contract_v1.json`, Git blob `10a0dac5d41d39ce115e29d6363c458148361496` (SHA256 `0e407ee0036e052053b38b9ef4be210bc2780d813f9c191ad26c1e1f5a84e75c`). The seven source-event IDs, deduplication keys, correlation key, synthetic timestamps, CI IDs and script actions are copied from the *verified canonical replay*, not invented ITSM IDs.
- `load_event_impact_contract_fixture` verifies Git blob bytes, schema, tenant scope, source index, graph, vertical plan, exact seven event rows and independently recalculated candidate blast radius. `event_impact_contract_offline` verifies the *complete* canonical manifest first, including tenant, seed, timestamps, source and evidence fields, before producing a read-only projection.

## Correlation and impact semantics

The correlation key `SYN-CORR-406EBF166A17BEB7E248` is **LOCAL_FIXTURE_ONLY**, not an Incident ID. All seven events have distinct `SYN-EVT-*` and `SYN-DEDUP-*` fixture keys. Correlation does **not** authorize cross-tenant joins or create tickets. The event action `INCIDENT_OPEN` is a scripted **expected action**, not evidence that an Incident was opened.

From `ACME-SAN-FABRIC-A`, reverse consumer reachability identifies ERP and Payments as **candidate** affected services; the selected path to Payments is `ACME-E08,E06,E04,E02` through Pure01, PAY01 and OraclePay. Estimated impact `HIGH` and proposed priority `P1` are *synthetic hypotheses*. No observed service outage, verified causality, evaluated SAN-B redundancy or confirmed ITIL priority is asserted.

Tenant, GLPI ticket, Core Incident, Run and immutable Evidence IDs remain `UNKNOWN`/null. Owner, datacenter, team, SLA/OLA, actual Change and maintenance remain `UNKNOWN`. Analyst/Critic, Policy, HITL and SIMULATE receipts are null; 15 vertical stages and six runtime checkpoints remain `NOT_EXECUTED`. Fixture timestamps are not wall-clock observations.

## Reproduction and negative tests

```bash
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
python tools/generate_acme_incidents.py --seed 20261018 --event-impact-contract --output /tmp/acme-event-impact.json
python tools/generate_acme_incidents.py --seed 20261018 --output /tmp/acme-replay.json
sha256sum /tmp/acme-replay.json
```

Expected canonical replay JSON SHA256: `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`. The projection does not mutate the replay. Nine new adversarial methods reject forged tenant, seed, bool/int alias, timestamp, source ID, CI, dedupe/correlation key, Evidence receipt, and unsupported impact or fixture provenance. Existing Quality discovery of the catalog suite is reused; no shared workflow edit.

## Contract ownership and release gate

ACME owns only this synthetic fixture, offline projection, tests and documentation. Core remains authoritative for tenant-scoped Incident/Run/Evidence, GLPI for tickets and native actor rights, Portal for read-only display, Policy/Worker for decisions and effects. A real cross-system link requires authenticated tenant-scoped API readback with provenance and timestamps; source-event coincidence is never sufficient. Coordinate schema boundaries in issue #186; do not edit other teams' files.

**RELEASE_STABLE=NO_GO.** No host access, GLPI write, deployment, LIVE effects, candidate merge or main push. **Rollback:** revert only the focused ACME commits (new fixture, generator, tests, document) without changing the graph, seed, vertical plan, shared Quality or architect integration branch.
