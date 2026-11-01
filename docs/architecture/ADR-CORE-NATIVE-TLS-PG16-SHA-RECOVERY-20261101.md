# ADR — Core native TLS human authorities and PG16 same-major audit recovery (2026-11-01)

**Status:** Proposed; source-only DEV qualification. **Owner:** Core xref / NOC / Evidence / GLPI. **Target:** sole architect Draft #234, branch integration/enterprise-slice-main-20261031-2230. No production or real GLPI/IdP calls. No new schema or migration. This ADR does not supersede the 009–013 installation contract.

## Decision and fail-closed boundary

Keep aiops.core-actor-resource-authorization.v1 **negative-only**: 200 UNKNOWN for synthetic issuer, mapping and GLPI human-session success, revoked/foreign/expired/replayed actor or insufficient rights; 503 UNKNOWN when the durable replay ledger is unavailable. Never grant ALLOW, LINKED or VERIFIED from HMAC, verified=true, first nonce consumption, text RUN-*, or a synthetic GLPI read. GLPI remains ticket/CI authority; Core remains the sole cross-reference/Incident/Run authority. The existing service token, tenant ACL, exact Run→Incident→Ticket, source provenance and 013 replay fence remain required.

### Independent TLS authority test

tests/test_core_actor_native_tls_sources.py starts **three distinct HTTPS servers** bound to disposable loopback addresses (127.0.0.2/.3/.4:8443) for IdP introspection, independently keyed subject↔GLPI actor mapping, and native human GLPI getFullSession / User / Profile / Entity / Ticket. An ephemeral test CA and individual IP-SAN leaf certificates are generated with OpenSSL and deleted after the test. The actual requests.Session/HTTPAdapter is used with verify=True, certificate chain and hostname/IP-SAN validation, trust_env=False, no redirects, bounded timeouts and response sizes. The only test trust override is the *ephemeral CA bundle path*, not a TLS/HTTP bypass or a disabled verifier.

Adversarial cases include untrusted CA, valid CA but wrong hostname, wrong issuer, foreign tenant or Run, wrong human GLPI actor, missing native ticket:read, wrong ticket entity and revoked subject mapping. The only expected positive outcome is *source preflight succeeded*, **not** actor authorization. No external network or real GLPI is contacted. This is stronger than the previous test-only HTTP bridge but still **not** operational GLPI/IdP qualification.

### Same-major PostgreSQL 16 archive and restore

tests/test_core_actor_pg16_native_sha_restore.py requires executable /usr/lib/postgresql/16/bin/pg_dump and pg_restore, verifies both client versions are 16.x and server version is 16.x, and refuses non-loopback/non-disposable targets. It creates two *new* databases, installs 001→004→009→010→011→012→013, and populates tenant ownership, consumed JTI/nonce and immutable revocation.

It produces a custom pg_dump archive, computes SHA256, copies it to a separate restore input, verifies the SHA256 before restore, proves a deliberately tampered copy would fail the hash gate, then runs **native PG16 pg_restore --single-transaction --exit-on-error** directly into the empty destination. No SQL rewrite or PG18 client fallback is allowed. After recovery, the test checks all three populated tables row-for-row, replay/revocation refusals, 009–013 idempotence and untouched source audit data. The SHA256 is printed in the exact-head CI log; the ephemeral archive and private keys are deleted. This is an isolated recovery rehearsal, **not** an in-place persistent downgrade, a backup under concurrent writes or a retained production recovery artifact.

### Rollback and integration gates

Only Core-owned tests and this ADR change. Existing Core-owned discovery bridges run the additions under architect-owned Quality without editing that workflow. A code revert must **never DROP, TRUNCATE, DELETE or rewrite** installed 013 nonce/revocation audit rows. Keep the installed ledger and source database untouched. Integration is architect-only after exact-head CI and comparison against current candidate HEAD.

Remaining P0: real IdP/GLPI trust onboarding, user/profile/entity authorization proof, signed independent subject mapping, durable revocation ingestion, operational secrets and tenant ACL qualification, persistent downgrade rehearsal and ITIL runtime evidence. actor_authorization=UNKNOWN, link_status=UNKNOWN, RELEASE_STABLE=NO_GO.
