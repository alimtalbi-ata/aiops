# ADR — Core canonical seven-event binding v1 (2026-11-01)

**Owner:** Core/NOC/Evidence. **State:** DRAFT / SOURCE_CANDIDATE / SYNTHETIC_ONLY. **Release:** NO_GO. **Base:** sole integration Draft #234 at `6755405ffb8538470925163f1466b45686d9b4af`.

## Boundary and design

`app/core/actor_canonical_seven_source.py` introduces `aiops.core-canonical-seven-source-binding.v1` as a **negative-only, read-only precondition**. It does not replace the single-event `aiops.core-actor-run-event-binding.v1` or change the public actor-authorization endpoint. There is **no positive ALLOW**, no VERIFIED human ticket permission, and no claim that synthetic source responses establish native GLPI User/Profile/Entity/Ticket rights. The existing actor endpoint continues to return UNKNOWN. Runtime wiring of the v2 precondition requires a separate contract review before promotion.

A separately configured, tenant/GLPI-instance-pinned HTTPS authority with distinct Basic service credentials reads canonical Core Incident, Run, ownership, seven Evidence and seven run_events rows from disposable PostgreSQL 16 using `SET TRANSACTION READ ONLY`. TLS chain and host verification remain enabled; redirects and proxy environment are disabled. The authority checks actor issuer and subject, tenant, exact Run→Incident, GLPI instance/ticket/entity, `run:read`, grant expiry/revocation, freshness and all seven records. It returns a bounded versioned seven-entry manifest. The Core adapter independently validates schema, issuer, source identity, exact scope, seven unique sequential events/evidence IDs, SHA256 values, timestamps, record correlation and payload/full-event domain separation. An invalid/missing/foreign/revoked/stale response fails closed.

## Hash domains — deliberately not conflated

- **Payload:** `SHA256(UTF8(canonical_json({"schema":"aiops.core-source-event-payload.v1","event":payload})))`, where canonical JSON uses sorted keys, compact separators and ASCII escaping. This matches the existing *synthetic fixture* and its `source_payload_hash`.
- **Full Core run event:** `SHA256(UTF8(canonical_json({"schema":"aiops.core-full-run-event.v1","event":full_event})))`. The full event binds `event_id, run_id, incident_id, tenant_id, sequence, stage, event_type, status, evidence_id, source_event_id, source_payload_hash, observed_at, known_at`.
- **ACME seven full-event hashes:** **NOT_EQUIVALENT / NOT_VERIFIED**. No domain conversion, digest reuse or positive impact/ticket assertion is allowed until the ACME producer contract is independently aligned.

The manifest is source-attested by an authenticated TLS service, not by a client-supplied HMAC or a `verified=true` field. The server's synthetic grant is a **test-only** table, not a second CMDB or an authorization authority for real users. GLPI remains the CI/ticket authority; Core remains the Incident/Run authority; Evidence retains its separate immutability requirements.

## Disposable qualification

`tests/test_core_actor_canonical_seven_binding_pg16.py` reuses the existing PG16 fixture: installed `001/004/009/010/011/012/013`, one Incident/Run, five tenant ownership records, seven Evidence and seven Run events, one synthetic scoped grant, and existing immutable 013 nonce/JTI/revocation rows. The new independent HTTPS handler recomputes both domains from the actual PostgreSQL rows in a read-only transaction. It tests tampered full/payload hashes, ordering, missing entries, issuer, future timestamps, revocation, actor issuer/subject, tenant/Run/Incident/ticket/entity/permission, wrong xref source hash, untrusted CA, expiry, and audit preservation. No real IdP/GLPI, host, SSH, external network, GLPI writes or executor.

Dedicated `.github/workflows/core-canonical-seven-binding-pg16.yml` runs PostgreSQL 16 and disposable TLS with exact PR-head checkout. **Expected 10/10 tests and zero skips** (six inherited fixture tests plus four v2 tests). This is an acceptance target, not a claimed CI result until the exact-head run succeeds.

```bash
AIOPS_XREF_CI_DISPOSABLE=1 GITHUB_ACTIONS=true PYTHONPATH=app \
python -m unittest discover -s tests -p 'test_core_actor_canonical_seven_binding_pg16.py' -v
```

## Revert and dependencies

Revert this focused PR's module, tests, workflow and ADR only; **never DROP/TRUNCATE/UPDATE the immutable 013 audit tables**. No schema change or migration rollback is required. Remaining gates: source service trust qualified outside disposable tests; native human GLPI rights and OIDC subject mapping; installed production-grade Evidence/Run-event immutability; ACME full-event hash equivalence; HTTP API contract/versioning; integrated ITIL and release D1–D4. Worker-requested audited terminal DEAD API is **subsequent Core-owned backlog** and must not share this PR's files.
