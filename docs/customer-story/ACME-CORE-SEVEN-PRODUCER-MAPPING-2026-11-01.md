# ACME/Twin — Core #291 seven-event producer cross-domain mapping (2026-11-01)

**Owner:** ACME/Twin P1. **Status:** SOURCE_ONLY / SYNTHETIC / RELEASE_STABLE=NO_GO. The architect alone may selectively integrate this focused source PR.

The canonical SAN→Payments replay remains seed `20261018`, seven events, 18 CIs/17 dependency edges, SQL 005 graph Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`, replay JSON SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`. The independently pinned three-domain source receipt SHA256 is `ed53b7b254b80e01b6ee87ad6b2949dfb3f93bb8e4904f48e0b90e75cb8ad4e7`.

`tools/acme_synthetic_core_producer_mapping.py` emits a deterministic **machine-readable fixture receipt** (JSON on stdout) with the seven ordered source event IDs and three independent SHA256 domains: (1) full ACME event, (2) local ACME payload, and (3) a Core-style payload *proposal*. The third uses the Core-owned canonical byte rule `SHA256(ASCII JSON sorted keys, compact separators, {"schema":"aiops.core-source-event-payload.v1","event":proposal})`. All proposed Core runtime scope fields are null; this is **not** a PG16 persisted payload or a Core readback.

Core #291 owns `aiops.core-canonical-seven-source-binding.v1`, `aiops.core-canonical-seven-source-receipt.v1`, `aiops.core-full-run-event.v1`, `aiops.core-canonical-seven-transport-proof.v1`, and `aiops.core-canonical-seven-receipt-hash.v1`. Its informational TLS source receipt is not a portable signature, native GLPI human permission, or ACME/Core hash equivalence. ACME does not import Core credentials, call Core, create parallel receipts or assert an actor/tenant binding.

The fixture output always has `core_runtime_receipt=null`, `core_runtime_status=UNAVAILABLE`, `core_hash_domain_equivalence=false`; Core persisted payload/full-event hashes and Evidence IDs are null. Actor, tenant, Incident, Run, GLPI, HITL, observed impact and confirmed priority remain `UNKNOWN`/null. **All 15 ITIL stages and six checkpoints are `NOT_EXECUTED`**. HIGH and P1 remain estimated/candidate, as do reverse-Twin Payments/ERP impacts.

Ten new adversarial tests in the existing Quality-discovered `test_acme_fixture_override_types.py` suite cover foreign actor/tenant/partition, stale/future/expired/revoked synthetic proposals, fake receipts/authority, missing/duplicate/reordered/forged hashes, replay seed/graph/timestamp tampering and byte-deterministic JSON emission. Even a perfectly matching synthetic proposal returns `UNAVAILABLE`.

```bash
python -m tools.acme_synthetic_core_producer_mapping --emit > /tmp/acme-core-producer-synthetic.json
python -m tools.acme_synthetic_core_producer_mapping --check
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
```

**Core/identity dependency:** independently actor+tenant-authorized Core PG16 readback for seven persisted events with documented canonical bytes, fresh/nonrevoked audit, immutable Evidence, and separate native GLPI human authorization. No source-only CI or matching hashes can satisfy this. No host, SSH, Docker, deploy/aiops2-stable, real GLPI writes or LIVE. Rollback: revert only the focused ACME branch commits, preserving Core audit 013 and architect candidate.
