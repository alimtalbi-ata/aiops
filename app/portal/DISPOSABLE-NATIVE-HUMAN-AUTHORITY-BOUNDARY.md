# Portal P0 — disposable native human authority boundary

**Scope:** source-only Portal test, one existing test module and this document. **Base:** sole Draft #234 `466cc80e7d1c651ad48791cbbfa7ac7fc6d1c6c6`. The architect alone selectively integrates. No production authority, GLPI writes, host access or second portal.

## Source and permission separation

The test `test_p0_disposable_glpi_human_readmy_core_expiry_never_promotes` uses two separately pinned, short-lived loopback TLS origins from the existing disposable fixture: Core's signed actor-resource response and native-shaped GLPI `getFullSession`, `User`, `Profile`, `Entity`, `Ticket` GETs. Their keys, human session and records are **test-controlled synthetic inputs**. They are not independently governed IdP, GLPI or Core authorities.

A valid synthetic OIDC issuer/audience/subject maps to a **test-only** GLPI User 77; the matching active Profile 4 has native Ticket READ bit `1`, active Entity 42 and Ticket 123 in that entity. Seven native negative readbacks independently change READ to READMY-only `2`, remove READ, deactivate User, change ticket entity, change active Profile, change session User or remove active Entity. All seven fail the test-only shape predicate. Foreign tenant/subject mapping is absent. Even the positive-shaped native snapshot **never authorizes** a Portal read: GLPI tenant ownership and human permission provenance have not been independently attested.

The separate synthetic signed Core `ALLOW` mock tests **parsing only**, not authorization: its result is `SIGNED_SHAPE_UNQUALIFIED`, HTTP `503 UNKNOWN`, `read_permitted=False`. Six signed mutations (expired decision, foreign Run, foreign ticket, foreign tenant, revoked decision, wrong nonce) are `INVALID` and still `503`. Core fixture POSTs and native GLPI fixture GETs are explicitly counted; they are **not Portal business GETs**. A revoked explicit OIDC session with a viewer bearer returns `401`, without upstream. There is no positive Portal read or dispatch.

## Remaining independently controlled trust inputs

Before any real human ALLOW, the architect/Core/GLPI owners must provide **all** of: (1) IdP issuer/audience/JWKS, subject and revocation independently validated, with a governed subject→GLPI User mapping; (2) a GLPI human session bound to that User, active native Profile and Entity, Ticket READ or scoped READMY plus ownership/visibility, tenant and instance identity, and source timestamps; (3) Core-owned actor+tenant+Run+Incident+ticket+entity binding with signer rotation/revocation and immutable 013/014 audit; (4) durable atomic nonce/JTI consumption, cross-worker revocation and freshness; (5) a documented positive authorization decision approved by the architect. None of these is established by synthetic TLS peers or browser headers.

Existing Portal Host/OIDC tests separately pin the callback to HTTPS `:7777`, reject HTTP downgrade and `:17777` alias, and prove no Run presence enumeration. Operator-reported **local** Debian `0.0.0.0:7777->777` and `/health` HTTP 200 do not establish external TLS, SSO/GLPI E2E, traffic ownership or unique public entrypoint. Do not deploy or stop a container on this evidence alone.

## Exact-head qualification and receipt

Run `PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v` in disposable CI, and optionally `PYTHONPATH=app:tests python -m unittest discover -s tests -p test_portal_idp_glpi_rotation_contract.py -v`. With `AIOPS_E2E_ARTIFACT_DIR`, the existing receipt helper emits `portal-authority-disposable-native-human-boundary.json`, containing source HEAD, UTC timestamp, `CI_DISPOSABLE_SYNTHETIC_ONLY`, canonical SHA-256, test-only request counts, and no credentials or ticket content. Receipt PASS is **not** an attestation of real GLPI human permissions or Debian runtime.

**Gates:** `core_authz_read_permitted=False`, `dispatch_allowed=False`, `RELEASE_STABLE=NO_GO`. Rollback: close the focused source Draft or forward-revert only its Portal test/doc commits. Never alter candidate, Core, Worker, shared Quality, volumes or deploy/aiops2-stable.
