# Portal P0 — split Cookie fields, HTTPS 7777 callback and GLPI UNKNOWN

**Status:** SOURCE_ONLY / CI_DISPOSABLE_SYNTHETIC_ONLY / NO_POSITIVE_ACL / RELEASE_STABLE=NO_GO.

This focused source-only Draft starts from sole candidate #234 exact base `e484f2e17bf4c72e4c5319e2e92f32430b4ec3b0`. It does not re-port #305, modify the candidate, or claim a Debian runtime change. It compares the older #298 callback pin to the current candidate and restores the explicit HTTPS `:7777` callback exception lost in the subsequent cookie-fence source. `:17777` is never an alias.

## Fail-closed contract

- **Raw Cookie fields:** `_oidc_cookie_supplied` scans every Cookie header, not Starlette's collapsed `request.cookies` mapping. `_session_from_cookie` rejects multiple Cookie fields, even when only one contains an OIDC session handle. Explicit invalid/revoked/ambiguous OIDC attempts remain **401**, never fall back to the shared viewer bearer. The API and HTML Run routes are tested for present/foreign/forged IDs, both cookie orders, duplicate handles and an unrelated first Cookie field. No upstream Core/GLPI business GET/POST, Set-Cookie on rejection or bearer disclosure.
- **Human authority:** A valid server OIDC identity plus forged browser GLPI Profile/Entity/READ claims remains **503 UNKNOWN**. GLPI User/Profile/Entity/Ticket native rights and the IdP subject mapping have not been independently attested. No synthetic `ALLOW` or positive read/dispatch is introduced. Run projections remain identical for present/foreign/forged IDs.
- **Callback origin:** Only the configured Portal redirect URI may use explicit `https://...:7777/auth/oidc/callback`; the IdP issuer and authorization/token endpoints still forbid explicit ports. `https://...:17777`, other ports and `http://...:7777` are rejected as **503 OIDC_UNAVAILABLE** at login configuration. The local 303 redirect is only a configuration-shape check, **not** evidence of a reachable listener, TLS termination or IdP authority. Same-origin Run-session remains 503; foreign/alias origin remains 403.

## Reproduce and evidence

```sh
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_host_cookie_negative_contract.py -v
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
```

The existing browser Quality entrypoint imports the Host/OIDC suite. When `AIOPS_E2E_ARTIFACT_DIR` is set by disposable CI, successful tests write `portal-host-cookie-split-cookie-fields.json` and `portal-host-cookie-callback-7777-only.json`, in addition to existing receipts. Each receipt contains the exact checkout SHA, UTC timestamp, provenance `CI_DISPOSABLE_SYNTHETIC_ONLY`, negative statuses, explicit `host_port_binding_verified=false` and canonical SHA-256 over sorted compact JSON excluding the digest itself. No raw bearer, OIDC handle, JWT, GLPI ticket contents or IdP secret is emitted. A test failure does not write a PASS receipt. Attach CI URL, N/N and artifact/checksum only after verification.

## Missing trust inputs and runtime boundary

Independent native GLPI User/Profile/Entity/Ticket permission and tenant ownership readback, source-attested IdP subject→GLPI User mapping, Core actor-resource signer and Run→Incident→Ticket binding, durable atomic nonce/JTI/revocation, cross-worker session revocation and Debian 7777 PortBindings/Host/TLS/proxy/firewall remain **NOT_ATTESTED**. Existing `aiops2-rebuild-portal` is KEEP; no second portal, new persistent stack or host modification is authorized.

`dispatch_allowed=False`; `core_authz_read_permitted=False`; `RELEASE_STABLE=NO_GO`. Rollback: close this Draft or forward-revert only its Portal-owned commits. Architect alone integrates selectively; no main push, merge, host SSH/Docker, GLPI write, LIVE or deploy.
