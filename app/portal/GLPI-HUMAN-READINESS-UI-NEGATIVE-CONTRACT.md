# Portal/GLPI P0 — native human-rights readiness gate (source-only)

**Scope:** existing Portal `/itsm`, `/api/portal/itsm`, one static same-origin client, and Portal tests. Base: sole integration Draft #234 at `b31cdbae926f8feb80af2fb42e05900286c28457`. This is a focused source Draft, not a deployment or a second portal.

## Operator-visible behavior

The existing `/itsm` screen now distinguishes native GLPI `Ticket READ` (active User/Profile/Entity) from `READMY` (the same native rights **plus** independently verified ticket ownership/visibility). A **Vérifier mon état d'accès** button makes a same-origin, credential-cookie-only request to the existing Portal status API. It sends **no viewer bearer**, actor, tenant, ticket ID or Run ID. The result is displayed as `401 UNAUTHORIZED` when no valid OIDC session exists, or `503 UNKNOWN` when identity exists but GLPI human permissions and Core Run↔ticket authority are not qualified. Unavailable responses also display UNKNOWN. The button cannot enable Commenter, Assigner or Approuver HITL; all remain disabled. This is a functional *readiness diagnostic*, not a ticket reader or approval interface.

The API rejects an explicitly supplied invalid, revoked, duplicated or split OIDC cookie with `401` even when a valid shared viewer bearer is present. A valid server-stored OIDC identity or legacy viewer-only request yields the same constant `503 UNKNOWN` body, including `human_authority.human_allow=false`. Browser-supplied GLPI User/Profile/Entity/Ticket, READ/READMY, Core Run, actor and tenant claims are ignored. Present, foreign and forged Run IDs are indistinguishable. No business GET/POST, no ticket existence probe, no browser bearer upgrade. All responses retain no-store/CSP.

## Source authority requirements before any positive human read

An independently governed IdP issuer/JWKS, session revocation and subject→GLPI User mapping; an independently authenticated GLPI human session with native active User/Profile/Entity, ticket READ or READMY with *ticket ownership* and tenant/instance binding; Core-signed actor+tenant+Run+Incident+ticket+entity binding with signer rotation/revocation; durable atomic nonce/JTI consumption and expiry; and an architect-approved positive contract are **all missing**. The existing separately controlled disposable GLPI and Core peers from #315 validate only synthetic shapes, not human authorization. There is **no synthetic positive ALLOW** in this slice.

## Qualification, provenance and runtime

Run `PYTHONPATH=app:tests python -m unittest discover -s tests -p test_explore_story_playwright_e2e.py -v` at the source branch exact HEAD. New tests: `test_09_glpi_native_readmy_unknown_oidc_cookie_never_downgrades` (TestClient) and `test_08_glpi_human_readiness_ui_stays_unknown_and_actions_disabled` (real disposable Chromium). The TestClient test writes `portal-host-cookie-glpi-readmy-human-gate.json` when `AIOPS_E2E_ARTIFACT_DIR` is set, using the existing redacted canonical SHA-256 receipt helper and `CI_DISPOSABLE_SYNTHETIC_ONLY` provenance. CI does not attest a Debian deployment.

The operator separately reported **local** `aiops2-rebuild-portal` healthy, `0.0.0.0:7777->777`, and `/health` HTTP 200. This is local host binding/health evidence, **not** external HTTPS/TLS, SSO/GLPI E2E, unique public entrypoint or absence of traffic on other portals. `:17777` is never a canonical alias. No host/Compose/volume changes are part of this PR.

**Gate:** `core_authz_read_permitted=False`, `dispatch_allowed=False`, `RELEASE_STABLE=NO_GO`. Rollback: close the focused Draft or forward-revert only its Portal commits; no main/candidate merge by owner.
