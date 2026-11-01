# ADR — Core canonical seven-event source readback (2026-11-01)

**Status:** TEST_ONLY / SOURCE_CANDIDATE; **authorization = UNKNOWN**; release NO_GO.
**Owner:** Core xref / NOC / Evidence. **Base:** sole Draft #234, exact source base `ab06b95bca2caeffdc4757d671a83700930c8267`.
**Contract:** `aiops.core-actor-run-event-binding.v1` remains a *single-event* negative-only precondition; no runtime or database schema change in this PR.

## Problem and authority boundary

ACME's seven full-event hashes are not proven equivalent to the current xref `source_payload_hash`. A signed xref/HMAC, `verified=true`, OIDC subject, or synthetic GLPI rights cannot establish that equivalence. The Core API is authoritative for Incident/Run; GLPI is authoritative for ticket, entity and native human rights. Evidence is append-only only when its own immutability contract is installed and qualified. The source adapter's positive *preflight* is never an actor `ALLOW`.

## Disposable qualification contract

The new isolated PG16 test applies **installed** `001,004,009,010,011,012,013` to a newly created loopback database, seeds one Core Incident and its exact Run, five tenant resource ownership facts, seven Core run_events and seven evidence records, plus one synthetic issuer/subject resource grant. It uses a separate HTTPS server (127.0.0.5) that checks Basic service credentials, a locally generated trusted CA, the exact actor subject, tenant, Run→Incident, GLPI instance/ticket/entity, permission `run:read`, freshness, expiry and revocation. The server's read-only PostgreSQL transaction recomputes and checks **all seven** event hashes on every request; an absent, reordered, stale or mismatched event denies the entire read. The Core adapter then checks its v1 single-event response, issuer, hash and freshness. No external network, real IdP/GLPI or GLPI write occurs.

Canonical synthetic hash domain (not yet asserted equal to ACME or Evidence production hash):

```python
sha256(json.dumps(
    {"schema": "aiops.core-source-event-payload.v1", "event": event},
    sort_keys=True, separators=(",", ":"), ensure_ascii=True
).encode("ascii")).hexdigest()
```

Seven events are uniquely identified by `EVT-SOURCE-01` through `EVT-SOURCE-07` and carry an explicit sequence. The test-only PostgreSQL triggers reject UPDATE/DELETE of the seven evidence and run-event rows. **These triggers are not an installed migration**, so the test does not qualify production immutability of either table. The installed 013 nonce/JTI and revocation tables are populated, compared before/after and never dropped or modified by the readback tests. Test-only actor grants are confined to the disposable database and do not constitute a second CMDB or a production authorization source.

Adversarial tests: seven independent readbacks; actor/tenant/Run/Incident/ticket/entity/permission/hash tampering; revoked/expired grant; attempted evidence/run-event mutation; untrusted TLS root; preservation of immutable 013 audit. The source returns generic UNKNOWN without enumerating foreign identifiers. All upstream successes still result in `actor_authorization=UNKNOWN`, never `ALLOW`.

## CI and rollback

Dedicated Core-only `.github/workflows/core-canonical-seven-source-pg16.yml` runs on the focused PR with PostgreSQL 16 server/client in disposable containers, a loopback-only database forwarder, ephemeral TLS material, exact PR HEAD checkout and **five tests with zero skips**. No shared Quality edits. Execute:

```bash
AIOPS_XREF_CI_DISPOSABLE=1 GITHUB_ACTIONS=true PYTHONPATH=app \
  python -m unittest discover -s tests -p test_core_actor_canonical_seven_pg16.py -v
```

Requires isolated PG16 `DATABASE_URL` with `127.0.0.1:5432/aiops`, `psycopg[binary]`, `requests`, `fastapi` and OpenSSL. The test creates and drops only its own named disposable database. The source server and ephemeral CA are removed on teardown. No persistent backup artifact is emitted; the dedicated CI logs are the evidence. Revert only this PR's Core test/workflow/ADR commits; **never DROP, truncate or mutate installed 013 audit tables**.

## Explicit remaining gaps

This test does **not** establish ACME's seven full-event hashes as the same hash domain, nor an independent Evidence receipt, real GLPI native human User/Profile/Entity/Ticket rights, real OIDC issuer trust, operational source-event ingestion, production immutable event storage or a positive actor permission. Core's v1 wire still returns one event per request; a future versioned seven-event response and source-owned signature/attestation require separate design and integration approval. D1/D2/D3/D4 and LIVE remain NO_GO.
