# Portal P0 — disposable real Core negative authorization TCP contract

**Scope:** Portal-owned tests and documentation only, based on the architect's sole
Draft #234. The real Core `core.main:app` is imported unchanged into a
separate disposable Uvicorn **process** listening on loopback TLS. This is
not a Core code change, real IdP/GLPI integration, production transport,
native GLPI human permission, or a positive authorization test.

## Contract and trust boundary

- The existing Portal HTTPS Chromium suite runs an identity-only OIDC session
  with an exact tenant/Run API and HTML denial. A test-only Core TLS process
  uses a short-lived certificate for `core.example.test`; the test client
  connects to 127.0.0.1 with certificate verification and pinned SNI, no
  DNS/proxy/real network. Core's actual
  `POST /api/tenants/{tenant_id}/runs/{run_id}/actor-resource-authorization`
  route handles the requests; only the test ASGI wrapper records method/path.
- The server-held service bearer is configured via a SHA-256 digest in Core's
  disposable `AIOPS_XREF_READ_AUTHZ_JSON` (tenant ACME, scope
  `actor:resource:authorize`). No browser-provided actor, tenant, ticket or
  bearer is accepted as a delegation. No `X-Actor-Delegation` token is
  supplied, and IdP introspection/GLPI readback are intentionally absent.
- Exact service token + tenant returns Core `200 UNKNOWN`; replay of the
  identical nonce remains `UNKNOWN` (not proof of durable replay fencing).
  Forged service bearer returns `401 UNKNOWN`; foreign tenant returns
  `403 UNAUTHORIZED`. All are strictly negative responses and must never
  become Portal `ALLOW`.
- Portal Run API/HTML remains uniform `503 UNKNOWN` for valid, foreign or
  forged Run IDs, including browser-forged headers. Expired/revoked OIDC
  sessions return `401`; replaying their cookies does not restore authority.
  No Core business GET, xref or GLPI fetch follows `UNKNOWN`. The test-only
  explicit Core POST is not wired into the Portal runtime.
- The `/api/portal/itsm` legacy viewer gate is separate from OIDC identity
  and still **not** native GLPI human ticket permission. It returns 401
  without its viewer bearer and 503 UNKNOWN with the viewer bearer.
- Browser requests and DOM contain no service bearer, foreign Core origin,
  GLPI ticket/CI details, or CONNECTED state. All Portal denial responses
  retain no-store/CSP protections.

## Disposable qualification

```sh
PYTHONPATH=app python -m unittest discover -s tests -p 'test_explore_story_playwright_e2e.py' -v
PYTHONPATH=app python -m unittest discover -s tests -p 'test_portal_core_acl_consumer.py' -v
```

The first command imports `tests/test_portal_acl_browser_e2e.py` and runs
the two new cases `test_08_real_core_tcp_unknown_401_403_and_replay_contract`
and `test_09_real_core_tcp_no_business_fetch_revocation_and_browser_leak`
in addition to the existing Chromium cases. A short-lived TLS certificate,
Core subprocess, session registry, temporary logs and ports are disposed
after each test. The logs record only HTTP method/path and are deleted.
No screenshot of authenticated GLPI or real IdP is created by this lot.

## Release blockers and rollback

`dispatch_allowed=False` and `core_authz_read_permitted=False` are
unchanged. A correctly signed synthetic ALLOW is not GLPI human permission.
Core must independently qualify issuer/subject delegation, tenant-scoped
native GLPI user/profile/entity rights, independent ticket/CI ownership,
a response signer and an atomic durable nonce/revocation ledger before any
positive Portal read can be considered. `RELEASE_STABLE=NO_GO`.

Rollback: close the focused Draft PR or revert only its Portal test/doc
commits. No candidate/Core/Worker/Quality edit, merge, main push, GLPI write,
host/SSH/sudo or LIVE.
