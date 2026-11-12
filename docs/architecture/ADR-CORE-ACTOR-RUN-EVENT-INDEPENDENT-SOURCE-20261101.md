# ADR — Core actor/tenant Incident–Run–source-event readback (2026-11-01)

**Status:** proposed Core P0 negative-only contract, source branch of Draft #234. **No positive actor authorization.** Existing xref schema `aiops.core-itsm-xref-read.v1` and installed migrations `001/004/009→013` are unchanged.

## Authority boundary

The existing actor endpoint `POST /api/tenants/{tenant_id}/runs/{run_id}/actor-resource-authorization` retains its response schema `aiops.core-actor-resource-authorization.v1`, returning only `200 UNKNOWN` (or `401/403/503` for existing service/tenant/availability fences). The new Core-only preflight `aiops.core-actor-run-event-binding.v1` is a necessary **read-only** independent source check after IdP introspection, exact xref verification and native human GLPI preflight, and **before** durable nonce/JTI consumption. Missing source config, inconsistent source, stale source, foreign actor/tenant, or an unverifiable event hash yields `UNKNOWN` without consuming the nonce.

`AIOPS_XREF_ACTOR_CORE_SOURCE_JSON` is an operator-held list of pinned `tenant_id`, `glpi_instance_id`, HTTPS `url`, `issuer`, `client_id`, `client_secret`. No request can choose the source URL. This adapter uses a fresh server-authenticated Basic client, `requests.Session(trust_env=False)`, TLS certificate/hostname validation, no redirects, 2s/3s timeouts and a 16-KiB response cap. The upstream authority MUST independently authenticate its caller, read Core's canonical tenant-scoped Incident and Run plus source event from the actual authority, recompute the source event SHA256 from immutable canonical source bytes, and reject requests without exact actor/tenant/Run/Incident/ticket/entity/permission scope. A response flag, HMAC fixture, or copied signed xref row is not proof that the upstream fulfilled these obligations.

The request binds ten string fields: `tenant_id`, `run_id`, `incident_id`, `glpi_instance_id`, `ticket_id`, `glpi_entity_id`, `permission`, `actor_subject`, `source_event_id`, `source_event_hash`. The source event ID/hash come from the validated Core xref record, **never** from a browser or ticket text. The response must echo all ten exactly, with `schema`, pinned `issuer`, `source_system=CORE_CANONICAL_READBACK`, integer `observed_at`, `known_at`, `expires_at`, `revoked=false`, `verified=true`. Require `now-300 ≤ observed_at ≤ known_at ≤ now < expires_at ≤ min(now+300, actor.exp)`. Every additional field, mismatched type, stale observation, revoked event or inconsistent hash is refused. A matching synthetic response is **only a preflight**, not `ALLOW` or `LINKED`.

The separate GLPI human session must still independently prove User/Profile/Entity native `ticket:read` and exact ticket entity. No synthetic TLS endpoint, HMAC, OIDC identity alone, or first nonce consume qualifies real human authority. Future positive authorization requires a separate signed, reviewed ADR and source attestation. The existing 013 nonce/JTI/revocation audit is append-only and must not be dropped or rewritten on revert.

## Adversarial qualification and integration

`tests/test_core_actor_run_event_source.py` uses a disposable in-process HTTPS-shaped transport (not real TLS or real source) to assert authenticated credentials, strict no-redirect/no-proxy/TLS flags, full ten-field binding, hash tamper, tenant isolation, issuer, freshness, revoke, malformed JSON/content type and oversize responses. It is loaded by the existing Core test bridge; the shared Quality workflow is not modified. The previously qualified separate native TLS tests remain the TLS evidence; this new suite alone is **not** end-to-end TLS qualification.

Run `PYTHONPATH=app python -m unittest discover -s tests -p 'test_core_itsm_xref_api.py' -v`; run the dedicated native PG16 recovery workflow unchanged for installed 001/004/009→013 and audit preservation. No migration is introduced. If source readback is absent, return `200 UNKNOWN` without external IDs; if Core DB is unavailable, `503 UNKNOWN`. No cross-tenant resource enumeration.

## Revert and limitations

Revert only this focused Core module, actor gate, tests and ADR; **retain all 013 audit rows and migration files**. No schema/data downgrade is needed. No real IdP/GLPI/Core source was called, no GLPI write, no Portal/Worker/Policy/shared Quality changes, no LIVE. Source trust provisioning and independent real-world attestation remain unqualified; `RELEASE_STABLE=NO_GO`.
