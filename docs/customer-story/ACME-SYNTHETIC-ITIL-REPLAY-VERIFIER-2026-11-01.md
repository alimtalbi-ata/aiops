# ACME — deterministic offline 15-stage ITIL replay verifier (2026-11-01)

**Status:** SYNTHETIC_FIXTURE / OFFLINE_FIXTURE_ONLY / NOT_EXECUTED. **Release:** NO_GO.

## Contract

`tools/acme_synthetic_itil_replay_verifier.py::verify_itil_replay_offline`
reuses the existing seven-event Golden Payments replay, pinned graph 005,
governance source index, event-impact projection, vertical 15-stage plan and
tenant-*test-partitioned* ingestion preflight. It creates **no** new Incident
Store, GLPI ticket, Core Run, Evidence record, model output or effect.

- Scenario: `SCN-GOLDEN-PAYMENT-P1`; seed `20261018`; seven SYNTHETIC events.
- Graph: `db/migrations/005_seed_acme.sql`, Git blob
  `67f0124a2c3b450e5249165e719a5d943fdd7237`, 18 CI / 17 edges.
- Canonical replay JSON SHA256:
  `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`.
- Event-impact contract blob `10a0dac5d41d39ce115e29d6363c458148361496`;
  vertical contract blob `e74e7b67d0d58e8eb1c2e4b54b1b0bf688694d13`;
  governance index blob `e77a0abbb53176488ec49d7c0c9f8581d4620b3f`.
- Dependency path SAN-A → Pure01 → PAY01 → OraclePay → Payments:
  `ACME-E08,E06,E04,E02`. ERP and Payments are reverse-reachable
  **CANDIDATES**, not verified outages. Estimated HIGH is not observed impact.
  P1 is a candidate, not a confirmed ITIL priority.

The verifier independently recomputes all three existing source projections,
matches each of the 15 ITIL stage anchors to one of the seven pinned events,
and validates the source event ID, CI, action, synthetic event/known-at time,
deduplication key, correlation key, content digest and simulated receipt clock.
Local exact duplicate deliveries are counted, not converted into incidents.
Any supplied projection must match the recomputed type-sensitive canonical
JSON exactly. Neither a SHA256 digest nor a synthetic timestamp is an Evidence
service receipt or a live freshness observation.

The two `SYNTHETIC_TEST_PARTITION_*` values are **not authenticated tenants**.
All runtime tenant, GLPI ticket, Core Incident/Run, Evidence, model, Policy,
HITL, SIMULATE, verification, resolution and reopen receipts are null/empty
or UNKNOWN. All 15 stages and six runtime checkpoints are `NOT_EXECUTED`.
Owner, team, datacenter, SLA/OLA, real Change and actual maintenance remain
UNKNOWN until read from a governed authority.

## Reproducible no-effect checks

```bash
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
python - <<'PY'
from tools import generate_acme_incidents as gen
from tools import acme_synthetic_itil_replay_verifier as verify
import json
result = verify.verify_itil_replay_offline(gen.replay(seed=20261018))
print(json.dumps(result, sort_keys=True, indent=2))
PY
```

The tests reject cross-partition deliveries, fake tenant/seed/source/CI,
forged event and known-at timestamps, stale/future/non-UTC simulated
deliveries, incomplete/conflicting deduplication, fabricated Core/GLPI/
Evidence/model receipts, false priority/observed impact and type aliases.

## Readback and handoff boundary

A real vertical run requires independently authenticated tenant and GLPI
human rights, Core Incident/Run and immutable Evidence readback, verified
Policy/HITL and a disposable SIMULATE receipt. This fixture does not perform
or qualify those steps. Coordinate any schema mapping with Core/Portal owners
through #186; never infer IDs from event names. Roll back only this focused
ACME module, the ten added tests and this document; do not revert integrated
source contracts or modify the sole architect candidate.
