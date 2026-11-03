# ADR — Core-owned HTTPS adapter for canonical seven-source PG16 readback (2026-11-01)

**Status:** source-only Draft; disposable qualification. **Owner:** Core/NOC. **No runtime mount, no new migration, no external writes.**

## Decision

Introduce `core.canonical_seven_https_adapter.dispatch_canonical_seven` as the reusable Core-owned HTTP dispatch boundary in front of the existing `core.canonical_seven_pg_source.read_canonical_seven`. The disposable TLS listener delegates to this code instead of implementing authentication, scope parsing and SQL calls inside the test. A trusted listener must attest a real TLS connection, never `X-Forwarded-Proto`; the client verifies an ephemeral CA and authenticates with separate Basic service credentials. The adapter compares credentials in constant time before inspecting the request and pins SQL connection, source and Core source issuer in server-side configuration.

**Two issuer domains remain independent:** `source_issuer=core-source-disposable-authority` is pinned by the Core service and HTTPS consumer; `actor_issuer=https://idp.synthetic.invalid` belongs to the actor claim and is matched to the synthetic PostgreSQL grant. They must not be compared for equality. The producer requires exact actor/tenant/Incident/Run/GLPI instance/ticket/entity, `run:read`, five-minute freshness, unrevoked grant, seven Evidence and seven run_events, and two distinct SHA256 domains `aiops.core-source-event-payload.v1` and `aiops.core-full-run-event.v1`.

The adapter emits a full source proof to the HTTPS consumer; `canonical_seven_source_receipt` derives a redacted machine receipt **only inside the authenticated readback flow**. It is not a portable signature or bearer credential. The ACME consumer must independently validate transport, trusted issuer, actor/tenant scope, hash domains, freshness, revocation and the original seven events; the redacted JSON artifact alone never authorizes a request. No native IdP/GLPI human right is asserted, and no ACME full-event equivalence is claimed.

## Negative-only HTTP contract

- 200: synthetic source proof returned, **not** `ALLOW`, `VERIFIED` or `LINKED`; downstream decision stays `UNKNOWN`.
- 401: invalid service Basic credentials, before any scoped lookup.
- 404: unsupported path, malformed request, foreign actor/tenant/Run/ticket/entity or absent/revoked/expired grant, without resource enumeration.
- 503: TLS not attested, missing service configuration, SQL outage or unexpected server failure.

All non-200 bodies are `{"decision":"UNKNOWN"}`; no secret or SQL error is returned. No writes occur: the SQL producer sets the PostgreSQL transaction read-only before queries. The existing 013 nonce/revocation and 014 terminal receipt audit are untouched.

## Qualification and handoff

The dedicated PostgreSQL 16/TLS workflow installs 001/004/009–014 in disposable databases, asserts native `pg_dump`/`pg_restore` and 013/014 immutability, runs 16/16 tests with zero SKIP, and uploads redacted `core-https-adapter.json` plus SHA256. The new test checks a trusted TLS listener, bad Basic over actual TLS, no TLS, malformed scope, foreign actor and injected SQL failure, exact seven full/payload hashes, issuer-domain separation, and unchanged audit counts. The prior 7/7 foreign/revoked/expired and freshness tests remain mandatory.

**Limitations:** No production TLS deployment, no real IdP/GLPI rights, no ACME-domain equivalence, no 15-stage ITIL runtime, no Debian execution, no new portal or CMDB. Local host 7777 was operator-verified separately; this CI does not establish external access, SSO or GLPI E2E. `RELEASE_STABLE=NO_GO`.

**Rollback:** revert the adapter, bounded Core test/workflow edits and this ADR. Never DOWN/DROP or mutate immutable 013/014 audit. No host container, DB, volume or deployment action.
