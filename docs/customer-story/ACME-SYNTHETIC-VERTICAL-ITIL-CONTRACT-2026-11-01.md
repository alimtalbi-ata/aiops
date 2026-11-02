# ACME SAN→Payments — synthetic vertical lifecycle contract v1

**Scope:** ACME-only, offline, deterministic and **NOT_EXECUTED**. This is a planned ITIL 4 demonstration contract, **not** an Incident Store, GLPI ticket, Core Run, Evidence ledger, Analyst/Critic execution, Policy decision, HITL approval or SIMULATE receipt. No HTTP, database, host, GLPI write, deploy or LIVE operation.

## Sources and invariants

- Canonical `db/migrations/005_seed_acme.sql` graph: Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`, 18 CI, 17 consumer→dependency edges, 7 Golden scenario script steps. SAN-A → Pure01 → PAY01 → OraclePay → Payments uses `ACME-E08,E06,E04,E02`. `ACME-E01` connects the Payments business CI. Reverse-reachable ERP and Payments are **blast-radius candidates only**, never observed outages.
- Existing incident catalog and governance source index are reused; index Git blob `e77a0abbb53176488ec49d7c0c9f8581d4620b3f`. Site `PARIS` and Payments criticality `5/5` are **synthetic SQL attributes**. Datacenter, service owner/team, SLA/OLA, Change ID and actual maintenance remain `UNKNOWN`.
- New **pinned plan fixture**: `tests/fixtures/acme_synthetic_vertical_contract_v1.json`, Git blob `e74e7b67d0d58e8eb1c2e4b54b1b0bf688694d13`. Its 15 stage declarations refer to existing SQL scenario step numbers and expected actions, never fabricated source event IDs. `load_vertical_contract_fixture` rejects any changed bytes, duplicate JSON keys, invalid stage references or unreviewed graph/index.
- `vertical_contract_offline(replay(seed=20261018))` strictly validates the *entire* canonical replay and storyboard before projecting stage anchors. Each stage reuses the matching **synthetic** `source_event_id`, event time and CI from the seven source events; `anchor_is_runtime_proof=false`, `status=NOT_EXECUTED`, `runtime_id=null`, `runtime_evidence_ids=[]`.
- Golden replay: scenario `SCN-GOLDEN-PAYMENT-P1`, seed `20261018`, seven events, JSON SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`, 8,974 bytes. The projection is **not embedded** in this canonical replay. `source_event_ids` are fixture-local, not API-attested IDs.

## Planned stages, not completed lifecycle transitions

`EVENT_ALERT → GLPI_TICKET → CORE_INCIDENT → CORE_RUN → TWIN_IMPACT_CANDIDATE → ANALYST → CRITIC → EVIDENCE → POLICY_PROPOSAL → HITL_APPROVAL → SIMULATE → POST_ACTION_VERIFICATION → RESOLUTION → REOPEN → PROBLEM_KNOWLEDGE_CHANGE`.

All fifteen are `NOT_EXECUTED`, even where a Golden SQL action is named `INCIDENT_OPEN`, `POLICY_CHECK`, `VERIFY` or `RECONCILE`. Such actions are script anchors **only**. In particular `VERIFY` payload `status=OK` does **not** establish a verified post-action check, and `RECONCILE` does **not** establish resolution or reopen. The existing six runtime checkpoints `GLPI_TICKET,CORE_INCIDENT,CORE_RUN,EVIDENCE,RESOLUTION,REOPEN` remain `NOT_EXECUTED` with null IDs.

`tenant_id`, `ticket_id`, `incident_id`, `run_id` are null; `evidence_ids` is empty. Tenant authority is `UNKNOWN`. Analyst hypothesis, Critic disposition, Policy decision, HITL approval, observed impact, SLA/OLA/Change/maintenance authority and confirmed P1 are `UNKNOWN`. P1 is **candidate** from the offline synthetic impact/urgency matrix; HIGH is **estimated**, not observed. N1/N2/N3/incident commander are planned, not authenticated. No simulated action has been executed; `simulation_executed=false`, `post_action_verified=false`, `resolution_verified=false`, `reopen_verified=false`, `publishable_to_core_or_glpi=false`.

## Reproduce and qualify

```bash
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python tools/generate_acme_incidents.py --scenario REDUNDANT_SAN_PATH_LOSS --seed 20261018 --vertical-contract --output /tmp/acme-vertical-contract.json
python tools/generate_acme_incidents.py --scenario REDUNDANT_SAN_PATH_LOSS --seed 20261018 --output /tmp/acme-canonical-replay.json
sha256sum /tmp/acme-canonical-replay.json
```

The adversarial suite rejects a foreign tenant, forged source/event/CI, invented Incident/Evidence IDs, fake observed impact, confirmed P1, stale timestamps, unpinned plan steps, forged authorities, false checkpoint receipts and bool-as-integer step alias. Existing Quality discovery of the catalog test file is reused; **no shared workflow changes**.

## Schema boundary and next dependency

Core remains sole authority for Incident/Run/tenant/Policy/HITL and immutable Evidence IDs. Portal remains an API-backed consumer. GLPI owns tickets and native human permissions. This fixture is a **schema preflight** only; no cross-system IDs may be joined from titles, script event IDs or coincident timestamps. Before any positive status, require independently authenticated tenant-scoped Core/GLPI readback, signed/authorized actor, source timestamps and immutable Evidence receipt. Coordinate the wire contract with Core/Portal owners via #186; do not edit their files.

**Release:** `RELEASE_STABLE=NO_GO`. **Rollback:** revert only this focused ACME fixture, generator projection, catalog tests and document; preserve candidate #234, shared Quality, pinned 005 graph, seed and replay bytes.
