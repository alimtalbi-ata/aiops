# Portal P0 — duplicate OIDC cookie / HTTPS Origin negative fence

**Scope:** Portal app and tests only. Sole integration Draft #234 exact starting SHA `5045dfa0784c267ca839d16d5b32d9d1d8d09234` (main `ae7c3e5102b99a66bd7806d602146f1309a9749d`). Source-only Draft: do not merge or edit #234. Historical #301 was selectively integrated already; do not re-port #301 or #298.

## Narrow regression and authority boundary

1. The OIDC session parser rejects **duplicate** `__Host-aiops_portal_session` cookie names before the framework's last-value-wins collapse. Forged+valid, valid+forged and valid+valid are all `401` on Run JSON and HTML even when a valid shared viewer bearer accompanies them. Revoked/invalid single explicit OIDC cookies remain `401`; valid identity without native GLPI rights remains `503 UNKNOWN`. Presence of a present, foreign or forged Run is never disclosed.
2. `POST /api/portal/run-session` refuses an **HTTP ASGI request** carrying an apparently valid `https://...:7777` Origin and browser-provided `Forwarded` / `X-Forwarded-Proto` headers (`403`). A disposable HTTPS request with matching Host and Origin `:7777` still returns `503 UNKNOWN`, **not** a capability; Origin `:17777` remains `403`. This tests request/Origin coherence, **not** a Debian listener or TLS termination.
3. The existing negative tests still enforce `no-store`, CSP, no Set-Cookie on the exchange, no Core/GLPI business GET, no upstream POST, no service bearer in browser, and no ticket/tenant/Run presence oracle. All fixtures and OIDC handles are disposable synthetic test data.

Source #298 had 55/55 negative tests and a proposed explicit-port OIDC callback change. The current candidate's OIDC callback configuration is **not** independently qualified for `:7777`; this PR does not re-port #298, assert callback success, or equate `:17777` with `:7777`.

## Independent trust inputs still missing

- Read-only host evidence: Docker PortBindings, reverse proxy Host/TLS, `ss -lnt`, firewall, DNS, health, dependency and rollback mapping for canonical host TCP 7777. Last reporter's container health is not port proof; existing healthy `aiops2-rebuild-portal` remains KEEP.
- Independently authenticated IdP issuer/JWKS, subject-to-tenant-to-GLPI User mapping, revocation and native GLPI User/Profile/Entity/Ticket permission (READ/READMY, ownership, entity recursion, freshness).
- Core-owned Run→Incident→ticket/entity binding, independently attested signer rotation/revocation and durable atomic nonce/JTI replay ledger.

**No synthetic ALLOW, positive read, dispatch or GLPI write.** `core_authz_read_permitted=False`, `dispatch_allowed=False`, `RELEASE_STABLE=NO_GO`.

## Reproduction and receipts

```sh
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_host_cookie_negative_contract.py -v
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_run_detail.py -v
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
```

With `AIOPS_E2E_ARTIFACT_DIR` set by the existing disposable CI, successful new cases emit `portal-host-cookie-duplicate-oidc-cookie.json` and `portal-host-cookie-http-origin-downgrade.json`, containing only negative status counts, UTC timestamp, exact checkout SHA, `CI_DISPOSABLE_SYNTHETIC_ONLY` provenance and canonical SHA-256. They are **not** independent GLPI or host receipts. Publish exact-head CI URL/N/N and artifact checksum only after the jobs finish and are inspected.

**Rollback:** close the source-only Draft or revert its Portal-only commits; no main/candidate rewrite, host action, second stack, volume removal, GLPI mutation or LIVE execution.
