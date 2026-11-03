# Portal / GLPI — READMY Ticket_User negative boundary (2026-11-01)

**Owner:** Portal/GLPI. **Scope:** existing `/itsm` and `/api/portal/itsm`, no second portal, no Core/Worker/ACME/shared CI/board edits.

## Executable delta

The Portal operator page separates native `Ticket_User` association from `Profile/Entity/Ticket READ|READMY`. Both remain **UNKNOWN**, and Commenter/Assigner/HITL remain disabled. The browser status client accepts only the strict 503 negative source contract, including `glpi_native_ticket_user_membership=NOT_ATTESTED`; any 200/CONNECTED/ALLOW or 403 is rendered as a refusal, never as permission.

A disposable GLPI TLS peer returns test-owned `getFullSession`, `User`, `Profile`, `Entity`, `Ticket` and `Ticket_User` readbacks. READ bit 1 is **not** READMY bit 2; even READMY plus a requester link is only a **necessary synthetic shape**, not effective GLPI rights. Missing/foreign/ambiguous membership, inactive user, wrong profile/entity, IdP subject/tenant mismatch and untrusted browser headers must fail closed. A separately pinned test IdP RS256 identity and a separately pinned test Core signer exercise expired/revoked/foreign/nonce-replayed decisions and signer rotation. No test-controlled signed ALLOW is a real human authorization.

## Acceptance and receipts

Run in disposable CI:

```sh
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
```

This includes the new `test_p0_readmy_ticket_user_and_core_replay_are_shapes_not_human_allow` and Chromium `test_10_glpi_readmy_ticket_user_boundary_browser_401_403_503`. With `AIOPS_E2E_ARTIFACT_DIR`, emit canonical SHA-256 redacted JSON receipts `portal-authority-readmy-ticket-user-core-signer-replay.json` and `portal-glpi-readmy-browser-negative.json`. Receipts are `CI_DISPOSABLE_SYNTHETIC_ONLY`, not GLPI/IdP/Core production proofs.

Expected: 401 missing/revoked explicit OIDC cookie, 403 explicit denial, 503 UNKNOWN valid identity without independently governed native rights; no Core/GLPI business GET, no ticket enumeration, no positive ALLOW. HTTPS callback `:7777` and `:17777` rejection remain covered by existing Host/OIDC tests; browser loopback HTTP tests do not establish external HTTPS.

## Host acceptance recipe (read-only, architect/operator)

The operator already verified the **local** `0.0.0.0:7777->777` binding and `/health` HTTP 200 on `aiops2-rebuild-portal`. External HTTPS/SSO/GLPI, public-entrypoint uniqueness and this source SHA on Debian are **NOT_ATTESTED**. Before any in-place update, independently inspect current Compose ownership, image digest, port bindings, proxy/TLS, traffic, mounts, DB dependencies, backup and rollback. Do not stop `aiops2-portal-candidate-web-20261029` without traffic/dependency evidence. Never treat `:17777` as an alias.

## Remaining independent trust inputs

A governed IdP issuer/audience/JWKS and subject-to-GLPI user/tenant mapping; native GLPI human session with active User/Profile/Entity/Ticket rights and authoritative READMY visibility; Core-owned Run→Incident→ticket signed actor-scoped proof with independently pinned signer, durable nonce/JTI replay and revocation. Until **all** are verified by the architect: `core_authz_read_permitted=False`, `dispatch_allowed=False`, `RELEASE_STABLE=NO_GO`.

**Rollback:** close this source Draft or forward-revert only its Portal-owned commits, then rerun exact-head CI. No main/candidate merge by owner, host deployment, real GLPI write, LIVE action, volume/DB mutation or stable branch push.
