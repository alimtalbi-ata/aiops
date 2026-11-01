# Portal P0 — revoked OIDC cookie cannot downgrade to viewer bearer

**Scope:** Portal-only source Draft, disposable API/HTML negative contract. **No independent IdP/Core/GLPI authority attested.** No GLPI writes, Debian host, SSH, Docker, LIVE or deployment.

## Security delta

`/api/portal/runs/{rid}` and `/runs/{rid}` now route **every request containing an OIDC session cookie**, including an expired, revoked, forged or malformed handle, through the revocable server-side session gate. Previously an invalidated cookie could fall through to the legacy shared viewer-bearer path and return 503 rather than the required 401. The bearer never grants access, but this downgrade obscured revocation semantics and allowed the identity context to change implicitly.

- Active OIDC session with valid viewer bearer: constant **503 UNKNOWN** for present, foreign and forged Run IDs.
- Revoked or forged OIDC cookie with valid viewer bearer: constant **401 UNAUTHORIZED** for the same API IDs, and 401 for the HTML Run journey.
- Viewer bearer without an OIDC cookie: legacy **503 UNKNOWN**, never an ACL grant. Browser actor/tenant/ticket headers are ignored.
- All denials remain no-store/CSP, with no Core business GET, GLPI ticket GET, foreign-origin fetch, ticket/Incident disclosure or service-bearer leakage.
- A test-only JSON receipt is emitted as `portal-authority-revoked-cookie-viewer-downgrade.json` in `AIOPS_E2E_ARTIFACT_DIR`, with canonical SHA-256, checked-out git HEAD, UTC time, synthetic provenance and explicit missing authority flags. It contains no bearer or cookie.

## Trust inputs still missing (do not infer from fixtures)

1. **Independent IdP authority:** pinned issuer/audience/JWKS, independent subject-to-GLPI-user mapping source and revocation status, not a browser header or synthetic tuple.
2. **Native GLPI human authorization:** independently authenticated `getFullSession`, User active state, Profile ticket READ/READMY semantics, active Entity scope and exact Ticket ownership/visibility under the human principal. GLPI remains the ticket/CMDB authority.
3. **Core authority:** independently verified Run→Incident→GLPI instance/ticket/entity tenant binding, response signer rotation/revocation and source-owned delegation, with exact nonce/JTI and atomic durable replay/revocation ledger across workers.
4. **Transport and proof:** pinned independent TLS origins and service credentials, auditable timestamps/freshness and negative parity without resource-presence or timing oracle. A synthetic signed `ALLOW` is not an authorization.

Until all are qualified, `dispatch_allowed=False`, `core_authz_read_permitted=False`, `RELEASE_STABLE=NO_GO`. No real or synthetic positive ALLOW is consumed.

## Exact-head reproduction

```sh
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_idp_glpi_rotation_contract.py -v
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_core_acl_consumer.py -v
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
```

The existing Quality browser entry point imports the IdP/GLPI contract class; no shared workflow changes. The receipt is generated only after passing assertions. CI success, N/N, exact SHA and artifact/checksum must be reported from the actual run, not assumed from this document.

**Rollback:** close the focused source-only Draft or revert its Portal-only commits. The architect alone may selectively integrate. Do not modify the sole #234 candidate directly.
