# Portal P0 — independent IdP→GLPI and Core signer rotation (test-only)

**Status: SOURCE_ONLY / FAIL_CLOSED / NO_POSITIVE_ACL.** This focused Portal-owned test extension builds on the already integrated #281 fixtures. No runtime Core/Worker/GLPI code, integration candidate, shared workflow, or real infrastructure is changed.

## Disposable contract

- A synthetic RSA-signed OIDC ID token is verified by the existing server-side Portal verifier with pinned IdP JWKS, exact issuer, audience, PKCE callback nonce, subject and explicit tenant-group mapping. An explicit **test-only** tuple `(issuer, subject, tenant) → GLPI user ID` maps the verified subject to a synthetic GLPI User. It is not a production identity mapping or human authorization. Foreign, ambiguous, forged-key, expired and nonce-mismatched assertions are rejected.
- The independent disposable GLPI TLS peer returns native-shaped `getFullSession`, `User`, `Profile`, `Entity`, `Ticket` snapshots under its synthetic human session. The existing native-shape assertion checks User 77, Profile 4, native Ticket READ bit, Entity 42 and Ticket 123. These records have **no independently proven tenant ownership** and cannot grant Portal reads.
- The separate disposable Core TLS peer signs the proposed actor-resource envelope. Tests rotate the synthetic RSA signer with explicit `kid` and pinned JWKS overlap, then retire old keys. Old signatures become invalid after retirement; ambiguous `kid` is rejected. Re-signed foreign actor/tenant/Run/ticket/entity and revoked delegation fail. Signature matching, even under a valid overlapping key, remains `SIGNED_SHAPE_UNQUALIFIED`, HTTP `503 UNKNOWN`, `read_permitted=False`.
- A test-only set illustrates why nonce/JTI consumption requires an **atomic durable Core ledger**: offline verification of the same signed response twice still matches its shape. A new nonce rejects the replay; neither case authorizes a read. This test set is not an anti-replay implementation.
- All synthetic TLS traffic is initiated explicitly by tests; Portal dispatch remains disabled. No Core business GET, GLPI write, browser bearer or foreign-origin fetch is introduced. Existing browser/API revoked-session and presence non-enumeration suites remain required.

## Qualification

From repository root with existing Quality dependencies:

```sh
PYTHONPATH=app python -m unittest discover -s tests -p 'test_portal_idp_glpi_rotation_contract.py' -v
PYTHONPATH=app python -m unittest discover -s tests -p 'test_portal_core_acl_consumer.py' -v
PYTHONPATH=app python -m unittest discover -s tests -p 'test_explore_story_playwright_e2e.py' -v
```

The fixture and tests are synthetic. No real IdP→GLPI subject mapping, native GLPI human rights, source-owned Run→Incident→Ticket ownership, Core signer/rotation policy, atomic nonce/JTI ledger or cross-worker revocation has been independently attested. **`dispatch_allowed=False`, `core_authz_read_permitted=False`, `RELEASE_STABLE=NO_GO`.** Real session revocation remains 401 and otherwise non-qualified Run reads remain uniform 503 UNKNOWN.

Rollback: close the focused Draft or revert its Portal-owned commits only. Do not re-port #281, modify the sole #234 candidate, merge, deploy, access a host, or write to GLPI.
