# ACME/Twin — pinned synthetic authority and ITIL blast-radius contract

**Scope:** focused additive tests on the architect-owned Draft #234 integration branch. This is an offline **SYNTHETIC_FIXTURE** contract, not a live CMDB, GLPI, Incident, Run or Evidence attestation. No new generator, endpoint, database, workflow or runtime effect.

## Authorities, fields and abstention

| Storyboard field | Pinned source and allowed interpretation | Authority limit |
|---|---|---|
| `site`, `site_by_path_ci_id` | `db/migrations/005_seed_acme.sql` Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`, each path CI node's synthetic `site` | Site is a node label, **not** a datacenter or verified customer location |
| `service_criticality_synthetic_1_to_5` | Same pinned SQL node row, 1–5 ordinal on the selected service | Not a service contract, SLO, SLA, observed outage or authorization |
| `dependency_path_edge_ids`, `dependency_path_node_ids` | Same 17 pinned directed edges, stored **consumer → dependency**, traversed in reverse for candidates | No verified causal propagation, no redundancy/failover proof |
| `blast_radius_candidate_service_ids`, `blast_radius_candidate_ci_count` | Reverse reachability from the source CI through pinned edges; services selected by pinned node type | **Candidates only**; `blast_radius_observed=UNKNOWN` |
| `impact_estimated`, `urgency_synthetic`, `itil_priority_candidate` | Pinned service criticality and catalog's synthetic urgency via offline priority matrix; active simulated maintenance or false-positive mode suppresses priority | `impact_observed=UNKNOWN`, `itil_priority_confirmed=UNKNOWN`; P1 is not a verified business incident |
| `maintenance_window_synthetic` | Pinned catalog offsets, if present, on the synthetic fixture clock | `maintenance_actual=UNKNOWN`, never infer an approved Change or a real maintenance window |
| `datacenter_id`, `datacenter_relation`, `service_owner_id`, `service_team_id`, `sla_id`, `ola_id`, `change_id` | **No authoritative identifiers/relationships in pinned 005 SQL** | All `UNKNOWN`; do not infer from Paris, names, roles or scenario titles |

Golden `SCN-GOLDEN-PAYMENT-P1` / seed `20261018` / 7 events / 18 CI / 17 edges. SAN-A → Pure01 → PAY01 → OraclePay → Payments uses `ACME-E08,E06,E04,E02`; `ACME-E01` links Payments to the business node. ERP and Payments are **candidate** affected services. SAN-B remains a redundant graph path, not proof of failover. Golden `CHANGE_LOOKUP` at +45s is planned only; `VERIFY` at +90s is a synthetic scenario step, not an independent post-action receipt. No actual recovery is asserted.

## Adversarial acceptance tests

The seven additional methods in the existing Quality-discovered `tests/test_acme_synthetic_incident_catalog.py` independently check all four supported scenarios: node/site/criticality from pinned SQL, absent DC/owner/team/SLA/OLA/change authority, independently traversed reverse graph blast radius, maintenance and false-positive suppression, rehashed forged governance fields, changed SQL blob (site/criticality/owner injection), and byte-identical Golden replay. Existing catalog, fixture, override-type and locator suites remain the regression baseline. No shared Quality workflow edits.

Run:

```bash
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python tools/generate_acme_incidents.py --scenario REDUNDANT_SAN_PATH_LOSS --seed 20261018 --output /tmp/acme-twin-provenance-replay.json
sha256sum /tmp/acme-twin-provenance-replay.json
```

Expected canonical replay JSON SHA256: `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`. The exact-source-HEAD Quality job must confirm `Ran N tests` and `OK`; do not infer test qualification from 3/3 job status alone. No tenant, GLPI ticket, Core Incident/Run or Evidence IDs are read from an API; these remain `UNKNOWN` and checkpoints `NOT_EXECUTED`.

**Integration dependency:** architect alone reviews and selectively integrates this focused PR into Draft #234. A future independently authenticated, tenant-scoped CMDB/GLPI readback is required before populating owner/SLA/OLA/Change, confirming priority or claiming runtime correlation. `RELEASE_STABLE=NO_GO`.

**Rollback:** revert only this PR's ACME test and contract-document commits; do not modify pinned 005 SQL, replay, Core, Portal, Policy, Worker or shared workflow. No GLPI writes, host access, deploy, merge, main push or LIVE.
