# Portal P0 — signed ALLOW negative browser/API matrix (2026-11-01)

**Scope:** Portal-owned test-only change, based on sole architect Draft #234 at `5d06311c6bc53d6d60c54483f485acfa5df8eba8`. No Core, Worker, Evidence, shared Quality, or candidate branch edits. No real IdP/GLPI/host/LIVE.

## What this verifies

The disposable HTTPS Portal Chromium/API fixture builds an **offline** RSA/JWKS signed future Core v1 `ALLOW` response. It demonstrates that a cryptographically valid synthetic envelope is only `SIGNED_SHAPE_UNQUALIFIED`, never permission. The server-only negative consumer rejects even that shape. Fifteen independently re-signed adversarial variants mutate tenant, subject, issuer, audience, Run, Incident, ticket, GLPI entity/instance, nonce, expiry, revocation, delegation and native GLPI permission. All must be rejected.

For a valid OIDC identity, existing, foreign and forged Run API/HTML routes remain uniform `503 UNKNOWN` with `no-store` and CSP, without resource presence, ticket, actor, or service bearer disclosure. Browser-supplied actor/tenant/ticket/entity headers are not authority. The test patches business Core GET and upstream JSON reads to fail if called. After server session revocation, all routes return `401`; a previously constructed plan and signed mock do not restore identity. Browser network requests must stay at the Portal origin.

**Important separation:** the legacy viewer bearer is an identity-only ITSM gate, not native GLPI human profile/entity permission. The test uses a disposable signing key and synthetic GLPI-shaped fields, not independently authenticated Core/GLPI rights. Existing real Core TCP negative tests remain in place; this addition does not invent Core `ALLOW`.

## Exact-head qualification

Run in the existing Chromium Quality entry point:

```bash
PYTHONPATH=app python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v
PYTHONPATH=app python -m unittest discover -s tests -p test_portal_core_acl_consumer.py -v
```

Record the exact source SHA, per-suite N/N, GitHub Actions run/job conclusions and actual artifact digest in the PR handoff. A passing synthetic fixture is not an independent GLPI readback.

## Activation fence and dependencies

`CoreAuthzWirePlan.dispatch_allowed=False`, `core_authz_read_permitted=False`. No business GET or positive `CONNECTED`. Core/identity/GLPI owners must separately attest OIDC subject mapping, native human rights per GLPI profile/entity, independent ticket ownership and exact Run→Incident→ticket/entity binding, Core response signer and atomic nonce/revocation ledger before a new reviewed activation PR. Until then `RELEASE_STABLE=NO_GO`.

**Rollback:** revert the focused test/doc commits or close the Draft PR; no deployment, merge or GLPI mutation.
