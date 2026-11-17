# Portal P0 — independent human authority boundary (source-only)

**Scope:** disposable Portal tests; no production or host access. Base: candidate #234 `e6381a6d7e8e088add37e6e28e9fde9ef543a9ff`. Architect owns selective integration. This is a **negative** contract, not a positive authorization implementation.

## Source authority required before any positive Run/ticket read

| Authority | Minimum independent evidence | Current qualification |
| --- | --- | --- |
| IdP | Trusted issuer, audience, JWKS/rotation, subject, expiry and revocation; subject-to-GLPI user binding from an independently governed directory | NOT_ATTESTED |
| GLPI | Authenticated *human* User/Profile/Entity/Ticket readback, active profile/entity, READ vs READMY, ownership and scoped ticket visibility from native GLPI API | NOT_ATTESTED |
| Core | Trusted signer pin/rotation and revocation, server-derived tenant+actor+Run+Incident+ticket+entity xref, immutable audit, source timestamps | NOT_ATTESTED |
| Anti-replay | Durable atomic nonce/JTI consumption, session revocation across workers, bounded clock skew and replay rejection | NOT_ATTESTED |
| Host | Read-only PortBindings, reverse proxy, TLS/Host, listener and firewall evidence for TCP 7777 | NOT_VERIFIED |

Browser headers `X-GLPI-User-ID`, `X-GLPI-Profile`, `X-GLPI-Entity`, `X-GLPI-Permission`, `X-Core-Signed-Decision`, `X-Actor-ID` and `X-Tenant-ID` are adversarial inputs, never authority. Synthetic Core signatures and GLPI fixtures are **not** source attestations. A browser bearer is not native GLPI permission. No synthetic ALLOW is generated or consumed.

## Test and receipt

`PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_host_cookie_negative_contract.py -v`

The new test `test_08_unattested_independent_human_authority_cannot_be_browser_supplied` checks all three Run identifiers (present-looking, foreign and forged) through API and HTML; a valid server session with every browser-forged authority claim remains **503 UNKNOWN**. Foreign session identity remains **503 UNKNOWN** with identical API projection. Explicit revoked OIDC cookie plus viewer remains **401**. HTTPS same-origin `:7777` is still **503 UNKNOWN**, `:17777` is **403**, and upstream business GET/POST counts remain zero. Existing tests separately cover HTTPS `:7777` callback and reject `:17777`/HTTP. No claim of a real Debian 7777 listener.

When `AIOPS_E2E_ARTIFACT_DIR` is set, the test writes `portal-host-cookie-independent-human-authority-unattested.json`: source SHA, UTC timestamp, `CI_DISPOSABLE_SYNTHETIC_ONLY`, redacted statuses, missing authority names, SHA-256 of canonical JSON, and negative-only flags. It contains no bearer, OIDC cookie or ticket content. CI is a source-only qualification, never a runtime or native GLPI attestation.

**Invariant:** `core_authz_read_permitted=False`, `dispatch_allowed=False`, `RELEASE_STABLE=NO_GO`. No second Portal, GLPI write, Core/Worker change, Docker/SSH, LIVE, deploy or host mutation. Rollback: close focused Draft or forward-revert only its Portal test/documentation commits; architect controls integration.
