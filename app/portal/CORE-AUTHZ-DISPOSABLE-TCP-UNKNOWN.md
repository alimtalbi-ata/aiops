# Portal P0 — disposable HTTPS Portal → synthetic Core TCP UNKNOWN

**Scope:** Portal-owned test-only contract, based on the sole architect Draft #234.
No production transport, Core/Worker/GLPI changes, IdP connection, or positive ACL.

The existing Quality Playwright entry point imports
`tests/test_portal_acl_browser_e2e.py`, now including two extra cases.
A second, **independent** `ThreadingHTTPServer` is started on loopback with a
short-lived synthetic TLS certificate for `core.example.test`. The test-only
`HTTPSConnection` connects to the loopback TCP port while validating the
pinned `core.example.test` certificate and SNI; it does not use DNS, a proxy,
or a real Core origin. This is deliberately **not** a production HTTP client.
It explicitly sends the server-created wire plan even though
`dispatch_allowed=False` to observe Core's negative wire shape only.

## Commands

```sh
PYTHONPATH=app python -m unittest discover -s tests -p 'test_explore_story_playwright_e2e.py' -v
PYTHONPATH=app python -m unittest discover -s tests -p 'test_portal_core_acl_consumer.py' -v
```

The fixture receives the exact `POST
/api/tenants/ACME/runs/RUN-ACME-123/actor-resource-authorization` with a
server-held `actor:resource:authorize` service bearer, independent of the
viewer token. It records only test-memory request metadata and replies with
the current Core v1 `200 UNKNOWN` envelope plus no-store security headers.
A real browser and the Portal server continue to return uniform `503 UNKNOWN`
for present, foreign and forged Run IDs; the browser cannot dispatch to Core.
Revoked OIDC session returns `401` without a new Core request. A cross-tenant
binding cannot create a wire plan. Replaying a nonce against the deliberately
stateless mock remains `UNKNOWN`; **this is not a durable replay test**.
An unsigned, forged TCP `ALLOW` is rejected by offline assessment and never
enables a Portal read. No service bearer appears in browser requests or DOM.

The fixture cannot establish an authenticated delegated OIDC subject,
independent GLPI ticket ownership, native GLPI human rights by profile/entity,
Core response signer, or durable atomic nonce/revocation ledger. In particular,
the mock does not implement or attest these controls. No GLPI write or real
Core data read occurs. The existing `/api/portal/itsm` viewer gate is
separate from the OIDC identity-only session.

**Release gate:** `dispatch_allowed=False`,
`core_authz_read_permitted=False`, `RELEASE_STABLE=NO_GO`.
Rollback: close this Draft PR or revert its Portal-only commits. No main push,
candidate edit, merge, deploy, host/SSH/sudo or LIVE remediation.
