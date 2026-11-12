# ACME SAN→Payments — independently supplied Core PG16 readback intake (SYNTHETIC)

**Scope:** ACME-only, offline, source review and disposable CI. This is an input
consumer, **not** a Core receipt producer, authenticated Core transport,
PostgreSQL query, GLPI adapter, human approval or runtime attestation.

## Contract

`tools/acme_synthetic_pg16_independent_intake.py` reuses the pinned seed
`20261018`, graph `005_seed_acme.sql`, the existing seven-event local
three-domain receipt and the existing 15-stage/six-checkpoint ITIL replay.
It accepts an optional **Core-owned** `aiops.core-canonical-seven-source-receipt.v1`
JSON file and a separate optional audit/revocation document, both read from
bounded local files. Core, not ACME, owns generation, authentication and
verification of the PG16 full-event/payload digests.

Each row distinguishes:
- `acme_full_event_sha256`: SHA256 of canonical full ACME event;
- `acme_local_payload_sha256`: SHA256 of local ACME payload;
- `proposed_core_payload_sha256`: local proposed Core-schema projection,
  **not** a persisted Core hash;
- `supplied_core_full_event_sha256` / `supplied_core_payload_sha256`:
  bytes in an *untrusted, structurally valid* input, never promoted to PG16;
- `core_pg16_full_event_sha256` / `core_pg16_payload_sha256`: **null**
  until an independently authenticated Core adapter qualifies the source.

The consumer delegates Core shape, source IDs/order, tenant/actor comparison
hints, clock and expiry checks to the existing Core readback UNKNOWN gate.
It rejects/marks UNKNOWN missing, foreign, duplicate and reordered events,
foreign actor/tenant, invalid hashes, missing Run and stale/expired claims.
Matching bytes are explicitly `SAME_BYTES_NOT_AUTHORITY`, not `VERIFIED`.

A JSON assertion about immutable migrations 013/014, revocation, Evidence or
GLPI/HITL is not a verifiable audit, identity or authorization proof. Even
a structurally correct seven-event Core-shaped JSON with a matching tenant,
actor and Run remains `UNVERIFIED`. No caller-controlled runtime identifiers,
bearer, signatures, approval claims or audit details are copied to output.

## Machine-readable negative receipt

`ACME-CORE-PG16-INDEPENDENT-INTAKE-UNKNOWN-2026-11-01.json` pins seven
source IDs and three independent local SHA256 values per event. It has
`readback_status=UNAVAILABLE`, `core_pg16_hash_equivalence=UNKNOWN`,
zero verified ITIL stages (15 `NOT_EXECUTED`) and zero verified checkpoints
(six `NOT_EXECUTED`). Tenant, actor, Incident, Run, GLPI, Evidence and HITL
remain null/UNKNOWN. No observed business impact, policy ALLOW or effect.

```bash
python -m tools.acme_synthetic_pg16_independent_intake --check
python -m tools.acme_synthetic_pg16_independent_intake --emit
python -m tools.acme_synthetic_pg16_independent_intake --readback /path/to/operator-supplied-core.json
python -m unittest discover -s tests -p 'test_acme_san_payments_fixture_contract.py' -v
```

The readback command is **offline** and does not establish authenticity.
Do not use it with real secrets; its inputs are not a permission to access
PG16, GLPI or a host. The synthetic CI tests construct only disposable,
clearly `TEST_ONLY` in-memory negative shapes.

## Core/identity dependency and release boundary

To advance a stage, the **Core owner** must provide an independently
authenticated and tenant/actor-authorized seven-event PG16 readback,
with same Run/Incident binding, canonical full/payload serialization,
freshness, revocation and independently checked immutable 013/014 audit.
The Evidence owner must separately attest immutable source/tenant/Run
bindings. GLPI must independently attest native human rights and ticket
entity; HITL requires its own scoped, unexpired human decision. The ACME
consumer cannot verify these by reading portable JSON and deliberately
contains no positive promotion path. Only after these independent
authorities exist should a separate integration gate be designed.

Local portal host binding/health on TCP 7777 was operator-reported healthy;
external TLS, SSO/GLPI end-to-end and portal uniqueness remain unverified.
Port 17777 is distinct. No Debian, Docker, host, network, volume, GLPI write
or LIVE operation is performed here. `RELEASE_STABLE=NO_GO`.

Rollback: revert only this focused source PR's ACME files. Never revert or
rewrite Core 013/014 audit, the sole architect candidate or stable deploy.
