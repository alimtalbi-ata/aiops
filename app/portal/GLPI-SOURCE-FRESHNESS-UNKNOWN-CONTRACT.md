# Portal P0 — source and freshness boundary in the existing GLPI / ITSM journey

**Scope:** Portal-owned UI/API and disposable Chromium test only. **Base:** sole Draft #234 at `269d3b341de5140a6db2d452032c69b581b5dd13`. **Release:** NO_GO. No second portal, no Core/Worker/ACME/shared workflow edits.

## Visible operator slice

The existing `/itsm` page now shows a four-source readiness table: (1) governed IdP subject→native GLPI User mapping, (2) active native GLPI Profile/Entity/Ticket READ or READMY plus owner/visibility, (3) Core-owned PG16 Run→Incident→ticket binding and separate Core signer, (4) durable atomic nonce/JTI, revocation and freshness. Each remains **UNKNOWN**, with explicit provenance `PORTAL_CONTRACT_ONLY`, upstream observation time `null`, and freshness `UNKNOWN`. The Core PG16 producer is a source contract, **not** IdP actor identity or human authorization. No Core/GLPI GET occurs.

The same-origin cookie-only `GET /api/portal/itsm` adds `authority_sources` to its existing constant 503 response. It exposes no actor, tenant, ticket or Run identifier. Explicit invalid/revoked/ambiguous OIDC cookies continue to produce 401 without viewer downgrade; the existing callback pins HTTPS :7777 and refuses :17777. A viewer token or browser-provided READ/ALLOW cannot establish native human permission.

The JS check displays source-readiness information only for a strictly validated **negative 503** envelope. A synthetic or compromised `200 CONNECTED/ALLOW` response, malformed source metadata or network failure can never enable Commenter, Assigner or Approuver HITL. These actions remain disabled. This is a usable operator explanation of missing proofs, not an authenticated ticket detail or positive access path.

## Disposable test and receipt

`test_09_glpi_source_freshness_ui_rejects_forged_positive` in the existing Playwright entry point checks the real ephemeral Portal API (503, no-store, CSP, redacted, UNKNOWN source), renders the four-source table in Chromium, injects a test-only 503 negative response, then injects a forged 200/ALLOW/ticket/Run and verifies no elevation or disclosure. The test writes `portal-glpi-source-freshness-negative.json` under `AIOPS_E2E_ARTIFACT_DIR`, with actual checked-out `git rev-parse HEAD` (compared to `AIOPS_EXPECTED_HEAD_SHA` when set), `CI_DISPOSABLE_SYNTHETIC_ONLY`, UTC test time and SHA-256 of canonical JSON excluding its digest. No credentials or ticket data are recorded.

Reproduce in the existing Quality browser job:

```sh
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
```

**Limitations:** No independent real IdP→GLPI mapping, GLPI native rights/ownership, Core actor-bound signer/nonce/revocation, external TLS/SSO or unique public entrypoint is attested. The operator has verified the *local* Debian binding `0.0.0.0:7777->777` and `/health` HTTP 200, not the external path. :17777 is never an alias. The PG16 producer is source/CI-qualified separately by Core, not consumed by Portal as an ACL.

**Gates:** `core_authz_read_permitted=False`, `dispatch_allowed=False`, `RELEASE_STABLE=NO_GO`. **Rollback:** close this focused Draft or revert only its four Portal-owned commits. Architect alone selectively ports exact blobs into #234; no merge/main/stable push or host operation.
