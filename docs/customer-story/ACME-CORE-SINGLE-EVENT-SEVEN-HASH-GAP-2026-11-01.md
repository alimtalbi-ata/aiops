# ACME — Core v1 single-event versus seven-event hash authority gap (2026-11-01)

**P1 / SOURCE_ONLY / SYNTHETIC.** The sole Draft #234 remains architect-owned. This ACME-only contract does not implement a Core API, a parallel Incident store, an identity service, a GLPI connector, a model, or a receipt issuer. It makes a specific unresolved source-binding mismatch visible.

## Pinned inputs and the actual mismatch

- Golden scenario `SCN-GOLDEN-PAYMENT-P1`, seed `20261018`, **seven SYNTHETIC events**, canonical replay JSON SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`.
- SQL 005 graph Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`, 18 CI/17 edges, SAN-A → Pure01 → PAY01 → OraclePay → Payments, sourced by `ACME-E08,E06,E04,E02`. ERP and Payments are reverse-reachable **CANDIDATE** blast radius only.
- ACME `tools/acme_synthetic_future_core_binding.py` pins **seven full-event SHA256 digests** over `gen._canonical(event)`. Core `app/core/actor_run_event_source.py` `aiops.core-actor-run-event-binding.v1` binds **one** `source_event_id` and `source_event_hash` per independent readback, from its xref `source_payload_hash`. These scopes are **not established as equivalent**. A hash of locally canonicalized `event["payload"]` is only a candidate comparison value, not a Core-issued payload hash or immutable Evidence receipt.

The new `tools/acme_synthetic_core_event_hash_gap.py` exposes both hash domains for all seven events, source ID, CI and event time, the single-event cardinality, and the **unqualified** semantic mapping. It cannot establish seven-event Core ingestion from a single valid-looking response. Even seven matching TEST_ONLY shapes return `UNAVAILABLE`, never `VERIFIED`.

## Adversarial contract

The ten new tests in the already discovered ACME catalogue suite cover absent authority; independent recomputation of seven hashes; one-versus-seven shape coverage; foreign actor, tenant and partition; missing/duplicate/reordered/forged event IDs; swapped payload/full-event hashes; stale/future/expired/revoked proof fields; forged Core issuer/schema/verified flags and runtime IDs; seed/replay tampering; and stable 15-stage/six-checkpoint nonexecution.

All input envelopes use `OFFLINE_TEST_INPUT_NOT_CORE`, `UNVERIFIED_SYNTHETIC_PROJECTION`, `TEST_ONLY_*` actor/tenant and `verified=false`. They are not authenticated actor or tenant claims. A structural match does not imply a valid Core readback. There is no HTTP call, token, host access, GLPI write, runtime model invocation or HITL action.

## Dependency for Core/identity owner

Publish and independently qualify the exact canonical source-event **hash domain and serialization** used by the Core source authority, with a tenant- and actor-authorized Incident/Run readback that binds **all seven** source event IDs and immutable digests to the same pair, including revocation, issuer, audit, observed/known/expiry times, and replay/graph versions. Test on disposable infrastructure and return redacted real source receipts before any promotion. Do not equate a service Bearer or matching internal xref to actor authorization.

Until then: `result=UNAVAILABLE`, `tenant_id/actor_subject/incident_id/run_id/glpi_ticket_id=null`, `evidence_ids=[]`, `observed_impact=UNKNOWN`, `priority_confirmed=UNKNOWN`. All **15 ITIL stages and six checkpoints are NOT_EXECUTED**. SLA/OLA, maintenance, Change, analyst/critic output, Policy/HITL, SIMULATE, verification and resolution have no sourced runtime receipts. `RELEASE_STABLE=NO_GO`.

## Exact-head qualification and rollback

```bash
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
```

Only `tools/acme_synthetic_core_event_hash_gap.py`, the existing ACME test suite and this customer-story contract are changed. No shared workflow or candidate edit. Roll back by reverting the three focused ACME commits on the source branch; architect alone may selectively port reviewed blobs into #234.
