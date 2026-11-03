# Portal P0 — disposable IdP/GLPI source authority and negative receipts

**Status: SOURCE_ONLY / SYNTHETIC / NO_POSITIVE_ACL / RELEASE_STABLE=NO_GO.**

This Portal-owned increment extends the existing IdP→GLPI/Core TLS contract tests. It does not re-port #285 or modify sole candidate #234. Both TLS peers are independent loopback fixtures, not real or independently attested IdP, Core or GLPI authorities. No host, SSH, Docker, volume, LIVE, deployment or real GLPI write is used.

## Contract boundaries

- **Identity is not native GLPI authorization.** RSA/JWKS OIDC issuer/audience/subject and an explicit test-only `(issuer, subject, tenant) → User 77` mapping are checked against synthetic GLPI `getFullSession`, User, Profile, Entity and Ticket. Foreign tenant/actor/Run/Incident/instance/ticket/entity, inactive User, and READMY (`2`) in place of native READ (`1`) are rejected. The source-owned binding is a synthetic tuple, not independent proof. Even matching shape never grants read.
- **Signer and replay are not qualified.** The separate disposable Core TLS peer signs **UNKNOWN only** in these new tests, never ALLOW. Pinned key overlap and retirement, foreign/revoked/nonce variants and a test-only lock/set accepting one of 16 concurrent `(issuer, subject, JTI, nonce)` attempts are checked. The set is not a durable distributed Core ledger. Signed UNKNOWN is not a supported positive Core envelope and remains 503.
- **Portal API and browser.** Actual Portal ASGI routes return indistinguishable `503 UNKNOWN` for present, foreign and forged Run IDs with an active server OIDC session, and `401 UNAUTHORIZED` after revocation. The viewer bearer is not native GLPI human permission. Core business GET and foreign network access are blocked and asserted unused; existing Chromium negative tests remain in the same Quality entry point.

## Machine-readable CI receipts

The existing Quality browser job sets `AIOPS_E2E_ARTIFACT_DIR` and uploads that directory. Three successful tests write `portal-authority-source-binding.json`, `portal-authority-signed-unknown-replay.json`, and `portal-authority-api-revocation.json`. Each contains a `receipt` object and SHA-256 over canonical JSON, exact checked-out `source_head`, UTC observation time, `CI_DISPOSABLE_SYNTHETIC_ONLY` provenance, negative statuses, non-authority labels and aggregate check counts. No bearer, JWT, cookie or raw token is serialized. A failing test does not emit its PASS receipt. These are test observations, **not** GLPI Evidence or runtime attestation.

## Reproduction

From repository root with existing Quality dependencies:

```sh
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_idp_glpi_rotation_contract.py -v
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_core_acl_consumer.py -v
```

Inspect exact-head GitHub Quality after PR finalization. Do not invent artifact IDs or checksums.

**Release fence:** `dispatch_allowed=False`, `core_authz_read_permitted=False`, `RELEASE_STABLE=NO_GO`. Independent IdP→GLPI mapping, GLPI human profile/entity rights, Core signer, source-owned Run→Incident→Ticket, durable atomic nonce/JTI/revocation and cross-worker session revocation are NOT_ATTESTED. No positive read, no CONNECTED.

**Rollback:** close focused source-only Draft or revert its Portal-only commits. Architect alone may selectively integrate into #234. No main push or merge.
