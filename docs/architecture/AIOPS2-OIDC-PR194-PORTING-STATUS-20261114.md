# AIOPS2 OIDC porting status — selective PR #194 reuse

Status: **code ported, CI pending, not production qualified**.

## Ported
- `app/shared/hitl_identity.py`: existing RS256/JWKS verifier and explicit simulator/live separation.
- `tests/test_hitl_identity.py`: original verifier tests, including RS256 group mapping and recent MFA checks.
- `app/shared/verified_principal.py`: new Core-side adapter that calls only the OIDC verifier and emits a frozen principal whose actor ID is the verifier-derived issuer+subject hash.
- `tests/test_verified_principal.py`: invalid/simulated claim rejection and no-fallback behavior.
- Pinned `PyJWT[crypto]==2.10.1` and quality workflow coverage.

## Explicitly not implemented / not claimed
1. **JTI replay/revocation:** verifier currently validates presence/shape of `jti` but does not persist or atomically consume it. Do not use the principal for critical approval or privileged operation until a durable replay/revocation gate is integrated.
2. **OIDC provider reachability:** tests mock the JWKS client; no real issuer, discovery, TLS trust, rotation, or outage behavior has been qualified.
3. **Generic endpoint integration:** this adapter is not wired into Portal/Core endpoints. The tenant reader remains non-routed.
4. **Tenant grants:** map the verified `actor_id` to #631 grants on the server; never accept tenant or actor from browser claims/headers.
5. **GLPI native ACL:** roles from OIDC do not imply GLPI profile/entity/ticket permissions.
6. **MFA policy:** the current verifier defaults to requiring `mfa`; deployment-specific claim semantics must be checked with the real IdP.
7. **Simulator routes:** the simulator is not copied into Core routes and cannot be used for LIVE.

## Next security gate
Implement a PostgreSQL-backed, atomic JTI replay/revocation store with issuer+JTI uniqueness, expiry cleanup, fail-closed DB errors, explicit revocation and race tests. Then integrate principal resolution into the tenant-scoped read path, and prove cross-tenant denial with no upstream call. Only after that add native GLPI ACL checks.

No deployment, production secret, real IdP/GLPI call, Debian access, migration application, or LIVE execution is authorized by this port.

## Durable JTI store tranche — 2026-11-14

Added:
- `db/migrations/010_oidc_jti_revocation_and_action_replay.sql`
- `app/shared/oidc_jti_store.py`
- `tests/test_oidc_jti_store.py`, `tests/test_oidc_jti_schema.py`, and `tests/test_oidc_jti_postgres.py`

Semantics:
- OIDC JWT JTI revocation is a durable issuer+JTI denylist; normal bearer use is not consumed per HTTP request.
- Sensitive approval/action replay is a separate atomic one-time key (issuer, JTI, action_id); concurrent duplicates must have exactly one winner.
- Database failures deny; no token bodies, access tokens, signing keys, automatic cleanup, or DDL-on-request.
- `principal_from_bearer` now requires a server-supplied durable `is_revoked(issuer, jti)` callback and refuses on missing, positive, null, or failed checks.

CI qualification:
- Offline OIDC verifier + principal tests and offline JTI store/schema tests passed on HEAD `8f52e05fe16a27c5013bc468ec5c06f33fe5b7f6` in run #43591525311 at the last observation.
- The PostgreSQL 16 JTI concurrency/revocation test was still pending in the same run.
- Earlier failing runs exposed a test fixture callback omission; corrected in the current HEAD. Do not treat earlier failed HEADs as current qualification.

Still not complete:
- The PostgreSQL migration/test has not yet been observed green on the latest HEAD.
- No endpoint wires the principal or JTI store; no IdP provider has been tested live.
- Tenant grant binding, GLPI native ACL, and action execution remain unconnected.

## Exact-head PostgreSQL qualification update

On branch HEAD `6462607f26ee839e9c202c3502baaa4ba865bdf2`, quality run #43591676559 has observed:
- Offline OIDC verifier + principal adapter tests: SUCCESS.
- Offline JTI store + schema contracts: SUCCESS.
- Real PostgreSQL 16 actor/tenant isolation and revocation: SUCCESS.
- Real PostgreSQL 16 OIDC JTI revocation and concurrent one-time action replay: SUCCESS (the concurrent race produced exactly one accepted consumption).
- Grafana real integration: SUCCESS.
- Overall quality job still running through Chromium/browser E2E at the time of this update. Do not call the full quality workflow green until the run concludes.

## OIDC principal → tenant-scoped Runs reader adapter — 2026-11-14

Added to `app/core/portal_tenant_runs.py`:
- `read_runs_for_bearer(connect, bearer_token, limit)` resolves the principal only through `principal_from_bearer`.
- The principal resolver performs the PostgreSQL-backed issuer+JTI revocation check before any Runs query.
- The subsequent Runs query uses the existing actor/tenant grant joins and bounded limit. Actor and tenant IDs are not accepted as caller parameters.
- Revoked token or unavailable revocation DB prevents the Runs query. No global fallback and no GLPI/upstream call exists in this adapter.
- Added `tests/test_portal_tenant_runs_oidc_adapter.py` and included it in the tenant/actor offline CI contract.

Exact-head qualification at branch HEAD `1efb2d603d7d3a2644d735c98e611996566f30ec`:
- Portal tenant/actor exact-head workflow #43591860320: SUCCESS.
- Quality offline tenant/actor suite (including the new bearer adapter), OIDC/JTI unit/schema suite: SUCCESS in #43591860325.
- Real PostgreSQL actor/tenant isolation and OIDC JTI concurrency/revocation suite: SUCCESS in #43591860325.
- Grafana real integration: SUCCESS in #43591860325.
- Overall quality workflow was still running its Chromium portal E2E at the last observation.

Boundary remains explicit: this is a callable Core reader adapter, NOT a mounted HTTP route or deployed authorization surface. Real IdP/JWKS reachability, grant provisioning/lifecycle, GLPI native ACL and authenticated GLPI readback are not qualified. No GLPI calls, writes, deployment, migration application on a server, Debian access, or LIVE execution.

## OIDC-bound signed GLPI xref gate — 2026-11-14

Selective read-only/security components from draft PR #520 have been ported:
- HMAC signed-xref verifier and canonical resolver boundary.
- PostgreSQL unique-key nonce replay consumer.
- Additive migration `011_glpi_xref_nonce_replay_barrier.sql`.
- `make_verified_principal_glpi_xref_resolver` in `app/shared/verified_principal_glpi_xref.py`.

Security semantics:
- Bearer verification and durable OIDC JTI revocation lookup occur on every `resolve_ticket(bearer_token, ticket_id)` call, not once when a reusable resolver is constructed.
- Actor identity comes only from the verified OIDC principal. Tenant candidates come only from active `portal_actor_tenant_grants`; there is no caller-supplied actor or tenant parameter.
- The signed xref must bind actor, tenant, ticket, issuer, audience, expiry, unique active association, and identity fields.
- A fresh active tenant grant is checked before an injected GLPI-native ACL callback. That callback must return exactly `True` for the precise actor/tenant/instance/entity/ticket read.
- The event nonce is consumed atomically in PostgreSQL. Zero or multiple valid tenant associations deny.
- The resolver does not perform GLPI HTTP reads, writes, Copilot queries, HITL proposals, or execution.

Qualification observed on HEAD `a2c83a03d7bc05577e388f19c00feafe9527286b`:
- OIDC-bound xref offline contract suite: SUCCESS.
- PostgreSQL 16 xref nonce durability, tenant scoping, concurrency and outage-denial suite: SUCCESS.
- Portal exact-head workflow: SUCCESS.
- The overall quality workflow was still running Chromium portal E2E at the last observation.
- A further ambiguity-denial test was added after this observation on HEAD `0143d435057c01a7e55559d8a0ee399e2e0a2522`; that exact HEAD is pending CI.

Not yet qualified:
- No concrete GLPI-native ACL provider/callback is installed; tests use a controlled fake. This remains a mandatory integration dependency.
- No real GLPI instance, GLPI session credential, IdP/JWKS provider, signed-event producer, or tenant-grant provisioning workflow has been tested live.
- No HTTP route is mounted. The resolver is an unmounted security adapter only.
- Migration 011 has been tested only against disposable CI PostgreSQL; it has not been applied to any deployment database.
- No GLPI ticket GET, PUT, CREATE, Copilot query, HITL proposal, deployment, Debian access, or LIVE execution was performed.

## Per-request OIDC → signed xref → authenticated GET-only readback — 2026-11-14

Added a server-side composition candidate:
- Bounded HTTPS JSON GET transport for Core with fixed origin, no redirects/proxy inheritance, response-size/type checks, and server-owned token provider.
- GLPI REST session adapter using server-owned App-Token/User-Token, exact ticket URL binding, ticket/entity response checks, and mandatory killSession cleanup.
- Separate Core and GLPI raw readers with independent actor/tenant/resource authorization callbacks.
- Raw readback normalization/comparison against the canonical signed xref.
- `make_verified_principal_glpi_readonly_qualifier` accepts only `bearer_token` and `ticket_id`. It resolves OIDC principal and JTI on every request, derives tenant from active grants, verifies signed xref/native GLPI ACL, then performs independently ACL-gated Core and GLPI GETs. It returns a comparison-only result with Copilot/HITL/write/execution flags false.

The assembly remains unmounted and requires real server providers for:
- OIDC issuer/JWKS verification and JTI revocation database;
- signed xref event source and HMAC key management;
- GLPI-native actor/entity/ticket ACL;
- separate Core Run and GLPI ticket read ACLs;
- Core service token and GLPI App/User tokens;
- trusted, distinct HTTPS origins.

Offline composition tests were added in `tests/test_verified_principal_glpi_readonly.py` and included in quality CI. Exact-head CI for commit `5c571d65a14da47e2e2292290b4ad134a1582abf` was in progress at the time of this update. No real upstream GLPI/Core calls, route registration, Copilot query, HITL proposal, mutation, deployment or LIVE execution.

## Native GLPI per-actor Ticket read authorization — 2026-11-14

Added `shared.glpi_native_ticket_acl.make_glpi_native_ticket_acl` and wired it into the OIDC read-only qualifier. The callback now performs a real GLPI REST `GET Ticket/{id}` using the user-token provider scoped by the verified OIDC actor, tenant, ticket and GLPI instance. GLPI's own permission check must allow that request; the adapter then requires exact ticket ID and exact signed-xref entity ID. Session cleanup failure, HTTP 403, timeout, malformed response, entity mismatch or any other exception returns deny. Only `read_ticket` is accepted.

This removes the externally injected boolean native-ACL decision from the qualifier composition. It does **not** remove the deployment requirement for a credential broker: `glpi_user_token(actor, tenant_id, ticket_id, glpi_instance_id)` must return that actor's own GLPI credential and must never fall back to a shared integration user. The app token remains application identity only and is not treated as user authorization. The credential broker must enforce the actor↔GLPI-user mapping and instance/tenant binding from trusted server configuration.

Added offline tests for actor/tenant/instance-bound credential invocation, exact ticket/entity matching, GLPI denial, malformed scopes and non-read actions. These tests are included in the quality workflow. This remains an unmounted candidate; real GLPI 11 integration with distinct least-privilege GLPI users and cross-entity denial is still required.
