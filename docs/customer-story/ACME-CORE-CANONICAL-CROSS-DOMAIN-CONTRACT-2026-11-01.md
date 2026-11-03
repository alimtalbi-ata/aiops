# ACME — proposed Core canonical seven-event cross-domain fixture (2026-11-01)

**P1 / SOURCE_ONLY / SYNTHETIC / UNAVAILABLE.** Owner: ACME/Twin. Sole architect Draft #234 is not modified. This is a fixture-to-contract comparison, **not** a Core receipt issuer, actor authentication service, parallel Incident store or GLPI connector.

## Independently pinned inputs and explicit domain mapping

- ACME golden SAN-A → Pure01 → PAY01 → OraclePay → Payments: `SCN-GOLDEN-PAYMENT-P1`, seed `20261018`, seven SYNTHETIC source events, canonical replay file SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`, SQL 005 Git blob `67f0124a2c3b450e5249165e719a5d943fdd7237`, 18 CI/17 edges and path edges `ACME-E08,E06,E04,E02`. ERP/Payments remain reverse-reachable **CANDIDATE** services; HIGH is estimated and P1 is a proposal.
- ACME full-event domain: `SHA256(gen._canonical(event))`, where `_canonical` is sorted compact ASCII JSON. ACME payload candidate: `SHA256(gen._canonical(event["payload"]))`. Both are local fixture hashes, not Core/Evidence receipts.
- Core's **disposable PG16 test-only** `aiops.core-source-event-payload.v1` domain (ADR `docs/architecture/ADR-CORE-CANONICAL-SEVEN-EVENT-SOURCE-20261101.md` and `tests/test_core_actor_canonical_seven_pg16.py`): `SHA256(json.dumps({"schema":"aiops.core-source-event-payload.v1","event":event},sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii"))`. Its `event_at(i)` contains Core test-specific `EVT-SOURCE-0i`, tenant, Incident, Run, ticket, entity and metric values, **not** the seven ACME events. Its current `aiops.core-actor-run-event-binding.v1` wire binds **one** event per readback, never seven in one attestation.

`tools/acme_synthetic_core_canonical_cross_domain.py` builds exactly seven **local proposed** wrapped-event rows with source event ID, one-based sequence, synthetic flag, ACME CI/time/payload and explicit `null` for unknown tenant, Incident, Run, ticket, GLPI entity and Core test metric. The proposal is deliberately **not** the Core `event_at(i)` shape; it does not assign the test-only Core IDs to ACME. Every row carries three separately named SHA256 domains. The mapping `LOCAL_PROPOSAL_NOT_CORE_EVENT` is not qualified as equivalent to any runtime Core `source_payload_hash`.

## Negative contract and authority boundary

The already-discovered ACME catalogue suite adds eleven tests: Core serializer source pin; seven independent digest recomputations; unknown ownership fields; no-proposal and seven matching proposals both `UNAVAILABLE`; foreign actor, tenant or partition; full-event/payload/Core-wrapped hash swaps; missing, duplicated, reordered and forged source records; stale/future/expired/revoked claims and boolean timestamp aliases; forged Core authority or runtime IDs; seed/graph/payload tampering; and unchanged ITIL stages/checkpoints.

All optional proposal envelopes have `source=OFFLINE_TEST_INPUT_NOT_CORE`, `authority=UNVERIFIED_SYNTHETIC_PROJECTION`, `TEST_ONLY_*` principals, `verified=false`, and an independently supplied test clock. A matching envelope is **not** independently authenticated, tenant-authorized or an observed Core readback. No HTTP, model, HITL, SIMULATE, GLPI write, host access or LIVE effect is performed.

## Core owner dependency and release gate

Core/identity must publish an **owned, versioned runtime source-event serialization** and a read-only seven-event Incident/Run readback with independent actor authentication, tenant ACL, issuer, revocation, observed/known/expiry times, audit and stable source IDs/hashes. Establish whether each ACME full-event hash, payload hash and proposed wrapped-event hash is equivalent or must be mapped to a different Core authority domain. Test the mapping with **actual disposable Core receipts**; do not promote a synthetic PG16 source server or single-event v1 xref to a verified ACME seven-event binding. No parallel receipt store.

Until that dependency is satisfied, `result=UNAVAILABLE`, `tenant_id/actor_subject/incident_id/run_id/glpi_ticket_id=null`, `evidence_ids=[]`, `observed_impact=UNKNOWN`, `priority_confirmed=UNKNOWN`. All **15 ITIL stages and six runtime checkpoints remain NOT_EXECUTED**. No sourced SLA/OLA, Change, maintenance, model output, effect or verification. `RELEASE_STABLE=NO_GO`.

## Qualification and revert

The shared Quality workflow already discovers the catalogue test file; no shared CI modification. Commands for exact source HEAD:

```bash
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
```

Scope: only `tools/acme_synthetic_core_canonical_cross_domain.py`, `tests/test_acme_synthetic_incident_catalog.py`, and this `docs/customer-story` contract. Revert only the focused ACME source commits in reverse order; the architect alone may selectively port reviewed blobs into #234. No main push, integration merge, migration or shared workflow overwrite.
