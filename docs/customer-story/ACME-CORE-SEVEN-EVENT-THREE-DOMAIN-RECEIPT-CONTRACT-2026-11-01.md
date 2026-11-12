# ACME synthetic seven-event / Core canonical three-domain receipt — 2026-11-01

**Owner:** ACME/Twin P1. **Scope:** offline source fixture only. **Release:** `RELEASE_STABLE=NO_GO`. This is a **machine-readable fixture receipt**, not an authenticated Core/GLPI/Evidence receipt. It neither ingests nor writes events.

## Immutable source and output

The canonical SAN→Payments fixture is replayed with seed `20261018`, seven source events, 18 CI / 17 dependency edges, and SQL 005 graph blob `67f0124a2c3b450e5249165e719a5d943fdd7237`. The pinned replay JSON is 8,974 bytes, SHA256 `bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8`. The dependency path is SAN-A → Pure01 → PAY01 → OraclePay → Payments (`ACME-E08,E06,E04,E02`); ERP/Payments are **reverse-reachable candidates**, not observed outages. HIGH is estimated; P1 is candidate only.

`docs/customer-story/ACME-SYNTHETIC-SEVEN-EVENT-THREE-DOMAIN-RECEIPT-2026-11-01.json` is an independently SHA256-pinned, deterministic output of `tools/acme_synthetic_three_domain_receipt.py`. Its seven ordered rows contain the original `source_event_id`, one-based sequence, and **three separate 64-character SHA256 domains**:

| Domain | Canonical bytes | Authority |
|---|---|---|
| `acme_full_event_sha256` | `SHA256(gen._canonical(acme_event))` | Full ACME fixture event, **not** Core full Run event |
| `acme_local_payload_sha256` | `SHA256(gen._canonical(acme_event.payload))` | Local payload candidate, **not** Core `source_payload_hash` |
| `proposed_core_payload_sha256` | `SHA256(gen._canonical({"schema":"aiops.core-source-event-payload.v1","event":acme_proposed_projection}))` | Core-style wrapper over an ACME proposal; **not** the Core PG16 persisted payload |

The proposal's `tenant_id`, `incident_id`, `run_id`, `ticket_id`, `glpi_entity_id` and `metric` are null. Its `acme_ci_id`, `acme_event_time`, `acme_payload`, sequence and source ID are fixture-only.

## Core-owned seven-event schema coordination

The Core owner has introduced a **negative-only** `aiops.core-canonical-seven-source-binding.v1` preflight in `app/core/actor_canonical_seven_source.py`. The disposable PG16 source computes `aiops.core-source-event-payload.v1` over its *actual persisted payload*, and `aiops.core-full-run-event.v1` over `event_id,run_id,incident_id,tenant_id,sequence,stage,event_type,status,evidence_id,source_event_id,source_payload_hash,observed_at,known_at`. Core's manifest also requires independent issuer/source identity, actor+tenant+Incident/Run/ticket/entity scope, seven distinct Evidence and source events, freshness, expiry, and revocation. Its successful test-only preflight does **not** grant actor ALLOW or native GLPI rights.

This ACME receipt maps `events[].source_event_id` and replay sequence only. `events[].payload_hash` is merely a **proposed** wrapper digest. `events[].full_event_hash`, `events[].evidence_id`, Core `event_id`, Incident/Run, tenant and actor are **UNAVAILABLE/UNKNOWN**. No digest is translated or promoted across domains; matching hexadecimal values would not establish provenance. No parallel receipt store is introduced.

**Core dependency:** Core/identity must publish a versioned seven-event runtime readback whose independently trusted actor+tenant authority binds the exact seven ACME IDs and their canonical byte representation to one Incident/Run, with a documented domain conversion (if any), revocation, audit, and immutable Evidence references. Until then, no ACME verifier may claim `VERIFIED`, `ALLOW`, GLPI ticket, model output, HITL action or effect.

## Fail-closed checks and reproducibility

```bash
python -m tools.acme_synthetic_three_domain_receipt --check
python -m tools.acme_synthetic_three_domain_receipt --emit
python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v
python -m unittest discover -s tests -p 'test_find_acme_demo_run.py' -v
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture.py' -v
python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v
```

The twelve new adversarial tests cover the seven ordered IDs and three hash domains, swapped/forged digests, missing/duplicate/reordered rows, foreign actor/tenant/partition, stale/future/expired/revoked proposals, fake authority, forged runtime IDs, altered seed/graph/event timestamp, and byte-identical CLI emission. All tests are synthetic and local; **CI is not Debian or Core readback evidence**.

The receipt and verifier leave **15 ITIL stages and six checkpoints `NOT_EXECUTED`**, `runtime_readback=NOT_EXECUTED`, tenant/actor/Incident/Run/GLPI/HITL `UNKNOWN` or null, observed impact and confirmed priority `UNKNOWN`, and `publishable_to_core_or_glpi=false`. No SSH, sudo, Docker, host, real GLPI write, LIVE, model or effect is used.

**Integration:** architect alone selectively reviews the four ACME paths and ports exact blobs to sole Draft #234; do not merge this Draft, overwrite shared Quality or change Core/Portal/Worker/Policy. **Rollback:** revert only this PR's focused commits in reverse order; do not modify candidate, main, or migration 013 audit rows.
