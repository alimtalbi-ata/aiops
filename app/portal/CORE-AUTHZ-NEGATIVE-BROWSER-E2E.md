# Portal P0 — disposable negative actor-resource browser/API contract

Scope: Portal-owned test only. This is a **negative** integration contract, not a
Core authorization implementation, GLPI human permission attestation, or
production browser capture.

Run under the existing Quality Chromium step (no shared workflow changes):

```sh
python -m unittest discover -s tests -p 'test_explore_story_playwright_e2e.py' -v
```

The browser entry point imports `test_portal_acl_browser_e2e.py`, which
starts a disposable loopback **HTTPS** Uvicorn server in-process and a real
headless Chromium. Its certificate, actor contexts, session store, RSA key,
JWKS and Core ALLOW envelope are synthetic; the browser may only reach its
ephemeral loopback Portal. No real IdP, Core, GLPI, DNS, database or LIVE
service is contacted. The tests do not persist screenshots or credentials.

Negative assertions:
- Anonymous and forged browser actor/tenant/GLPI headers remain 401;
  valid server-held OIDC identity remains **503 UNKNOWN** for exact, foreign
  and forged Run IDs; API and HTML deny without resource existence oracles.
- Expired, revoked and replayed session handles return 401; a revoked handle
  cannot restore identity or business access.
- Synthetic RS256-signed ALLOW is accepted only by the *offline signature
  checker*, never by `core_authz_read_permitted`; a fresh request nonce,
  foreign tenant/Run/ticket/entity, forged actor/issuer/audience and expired
  proof all fail the offline check.
- Service-scoped bearer is never exposed in browser requests or responses.
  No browser route may contact the pinned Core origin or any foreign origin.
- Run/ITSM response headers remain no-store, CSP frame-ancestors none,
  X-Frame-Options DENY; GLPI write controls remain disabled. The ITSM API
  has a separate legacy viewer gate: OIDC-only yields 401, and even a valid
  legacy viewer bearer yields 503 UNKNOWN, never GLPI authority.

Important limitation: a process-local fake OIDC session is **not** a real IdP
callback or Core/GLPI delegated permission. This suite cannot qualify durable
atomic nonce/revocation ledger, independent GLPI ownership, native N1/N2/N3/
manager rights or positive Core response signer. The real browser uses a
throwaway TLS certificate and `ignore_https_errors` **only in this test**.

No network dispatch: `dispatch_allowed=False`,
`core_authz_read_permitted=False`. No CONNECTED or positive business reads.
Rollback: revert the focused Portal test/doc commits or close its Draft PR.
