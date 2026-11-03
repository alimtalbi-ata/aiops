# Portal P0 — server-session-bound Core v1 negative consumer (2026-11-01)

**Scope:** Portal-owned contract/test only, based on sole architect Draft #234.
This is a **disposable development fixture**, not production authorization or an
IdP/GLPI qualification. Historical Draft #269 is already selectively integrated;
no old blobs or branch history are imported.

## Delta

`assess_core_negative_for_session` in `app/portal/core_authz_transport.py`
re-reads the **server-held revocable OIDC session at response-consumption time**.
It takes no browser actor, tenant, bearer or delegated identity. With an absent,
expired or revoked session it returns `401 SESSION_REQUIRED`. With an active
session, a pinned exact-resource plan and the **actual Core v1 negative**
`200 UNKNOWN`, `401 UNKNOWN`, `403 UNAUTHORIZED` or `503 UNKNOWN`
it returns `503 UNKNOWN` and `read_permitted=False`. A malformed response,
foreign tenant/resource, forged `ALLOW`, altered plan or invalid headers is
also `503 UNKNOWN` without a read. The diagnostic `kind` is server-internal
and MUST NOT be exposed to clients as a resource-presence oracle.

The function **does not issue a request**. The disposable integration test
explicitly calls the independent Core ASGI route over loopback TLS/TCP,
then passes the reply to the session-bound consumer. The test-only TCP sender
is not imported into the Portal runtime. `dispatch_allowed=False` and
`core_authz_read_permitted=False` remain hard fences.

## Reproducible negative tests

```bash
PYTHONPATH=app python -m unittest discover -s tests -p 'test_portal_core_acl_consumer.py' -v
PYTHONPATH=app python -m unittest discover -s tests -p 'test_explore_story_playwright_e2e.py' -v
```

The two new Chromium/API methods exercise an actual disposable Core TLS
negative route and the server-session consumer: live OIDC identity-only cookie,
revocation after a reply is received, replay of the same nonce (no ledger
claim), foreign tenant/ticket/entity, forged ALLOW, and Core service bearer
401/tenant 403. Browser Run HTML/API remain 401 after revocation and 503
UNKNOWN while identity is valid; no business GET or ticket read occurs on
UNKNOWN. Browser requests never receive the Core service bearer.

**Limitations / owner dependency:** Core must independently attest signed
actor-resource response authenticity, real OIDC subject delegation and
revocation, atomic nonce/revocation ledger, exact Run→Incident→GLPI
ticket/entity source ownership, and native GLPI human permissions per
profile/entity. A legacy viewer token proves identity only, never those
permissions. A synthetic signed ALLOW does not satisfy the gate. No GLPI
writes, IdP access, host access or LIVE execution. GLPI remains the ticket/CMDB
authority; no parallel ITSM is created.

**Rollback:** revert the Portal-only commits in this Draft or close the PR.
No candidate/main merge by the Portal owner. `RELEASE_STABLE=NO_GO`.
