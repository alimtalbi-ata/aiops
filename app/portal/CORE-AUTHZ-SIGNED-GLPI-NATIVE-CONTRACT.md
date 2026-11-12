# Portal P0 — independent signed Core + native GLPI human readback contract (test only)

**Status: SOURCE_ONLY / FAIL_CLOSED / NO_POSITIVE_ACL.** Portal owner; sole integration candidate is Draft #234. This branch adds **no production network client**, no Core/Worker/Evidence edits, no shared Quality edits, and no GLPI write. The new peers are disposable loopback TLS fixtures; their certificates, RSA signer and GLPI records are generated in memory/on temporary disk and destroyed after tests.

## Contract exercised

1. The Portal constructs an exact server-held `POST /api/tenants/ACME/runs/RUN-ACME-123/actor-resource-authorization` blueprint with scoped service bearer, six-field body, request nonce and pinned HTTPS Core origin. `dispatch_allowed=False` remains immutable. The browser cannot supply actor/tenant/Run→Incident→ticket/entity authority.
2. A separate **synthetic Core TLS peer** returns a detached RS256-signed proposed `ALLOW` envelope, bound to the request nonce, issuer/audience/subject, tenant, Run, Incident, GLPI instance/ticket/entity and expiry/revocation. The Portal offline verifier may report `SIGNED_SHAPE_UNQUALIFIED`, but `read_permitted=False`, HTTP `503 UNKNOWN`. Re-signed foreign/forged/revoked claims and replay against a fresh nonce are `INVALID`. This is **not** the current Core wire format: real Core v1 returns negative `UNKNOWN`/`UNAUTHORIZED` only, with no response signer.
3. A **different synthetic GLPI TLS origin** returns native-shaped `getFullSession`, `User`, `Profile`, `Entity` and `Ticket` records under a test human session. Test-only assertions require exact active User, active Profile, native Ticket READ bit `1` (not READMY `2`), active Entity membership and exact ticket/entity IDs. Wrong User, disabled User, profile, READ bit, entity or ticket fails. These synthetic GETs are explicitly initiated by the test fixture; **the Portal never performs them**.
4. Run API and HTML routes preserve non-enumerating `503 UNKNOWN` for present/foreign/absent/forged Run IDs and `401` after opaque OIDC session revocation. The suite patches Core/GLPI business fetch functions and verifies no Core GET, no Portal→Core authorization dispatch, no extra GLPI GET, no service bearer/ticket/Incident disclosure. Existing Chromium tests remain separate browser evidence.

The Core owner's `app/core/actor_native_authority.py` remains the sole native GLPI authorization preflight owner. The test-only native shape assertion is **not** an alternative Portal GLPI authority implementation and is never imported by runtime code. A valid fixture signature, positive GLPI-shaped response, service token, OIDC viewer session or Portal N1/N2/N3/manager role cannot authorize a ticket.

## Exact-head qualification

Run from repository root under existing Quality dependencies:

```sh
PYTHONPATH=app python -m unittest discover -s tests -p test_portal_core_acl_consumer.py -v
PYTHONPATH=app python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
```

The first command includes the new independent TLS contract and negative matrix; the second is the existing Chromium/API no-leak regression. Do not claim native real GLPI, production Core response signing, durable nonce/JTI ledger, real IdP mapping or human profile/entity rights are independently attested. No real GLPI API, host access, LIVE, deploy or mutation is used.

**Activation blockers:** Core-owned independently authenticated OIDC subject→GLPI user mapping; native human Profile/Entity/Ticket permission from a real independently authenticated GLPI session; source-owned Run→Incident→ticket/entity linkage; atomic durable nonce/JTI and revocation ledger; Core response signing and trusted key rotation; architect approval. Until all are qualified: `dispatch_allowed=False`, `core_authz_read_permitted=False`, `RELEASE_STABLE=NO_GO`.

**Rollback:** close the focused Draft or revert only its Portal-owned test/helper/documentation commits. Do not revert #277/#273 or modify the sole architect candidate, Core, Worker, shared workflows or append-only 013 audit.
