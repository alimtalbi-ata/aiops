# P0 — Core Incident inventory and portal operator read API

**Scope:** code-level integration of canonical Core incidents/runs and Evidence metadata through the existing portal, with explicit read-role authorization. No direct portal database access and no fake runtime source.

## Contracts

- `GET /api/incidents` (Core internal network): read-only, latest 50 canonical incidents. No incident payload returned.
- `GET /api/portal/operator/snapshot` (portal): read-only, per-resource `incidents`, `runs`, `evidence` with `READABLE_UNVERIFIED`, `UNKNOWN`, or `FORBIDDEN_BY_ROLE`.
- `AIOPS_PORTAL_READ_TOKEN` (viewer): incidents and runs; **Evidence is not fetched**.
- `AIOPS_PORTAL_OPERATOR_TOKEN` (operator): incidents, runs and **metadata-only** Evidence; no Evidence `payload`, incident `payload`, or arbitrary Run fields.
- Both roles use `Authorization: Bearer <token>`; viewer token is mandatory and must be 32–256 printable ASCII characters; operator token optional but must differ from viewer. Missing/weak/conflicting configuration returns HTTP 503, missing/invalid token HTTP 401. No secret defaults; configure via Debian secret storage, not Git.
- All responses include `Cache-Control: no-store`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.

The portal calls Core `/api/incidents` and `/api/runs`, plus the actual Evidence service `/api/evidence?limit=50`. Network errors, malformed responses and unexpected fields are isolated per resource and reported `UNKNOWN`, never silently replaced by synthetic success. Even a successful HTTP read is **not runtime-authenticated evidence**; the envelope explicitly says `UNATTESTED_UPSTREAM_API_READ`. This API does not authorize remediation.

## Example (after configured, not yet qualified on Debian)

```bash
curl --fail-with-body --header "Authorization: Bearer $AIOPS_PORTAL_READ_TOKEN" \
  http://127.0.0.1:17777/api/portal/operator/snapshot
```

Never place tokens in GitHub Actions, URLs, screenshots or shared logs. The command is a future operator action, not evidence it was run.

## Limits and next security lot

This is **scoped API RBAC**, not complete portal authentication. Existing `/`, `/api/portal/bootstrap`, `/api/portal/components`, `/api/demo` and `/api/copilot` are unchanged and may still expose data or accept actions depending on deployment. Do not expose the portal publicly without a reviewed reverse proxy, session authentication, CSRF controls and comprehensive endpoint-level RBAC. A follow-up PR must close these gaps before claiming a secure single entrypoint.

Unit/HTTP contract tests substitute upstream fetchers and an in-memory HTTP client; they do **not** qualify real Core/PostgreSQL, Evidence/PostgreSQL, n8n, Thruk, Grafana, GLPI or Debian. No NGX/NIM inference occurs in this lot. No LIVE operations.

## Operator console UI (2026-10-27, follow-up in this PR)

The canonical portal mounts `GET /operator` and its same-origin `/operator/console.js` asset. The homepage links to it. The UI requests `GET /api/portal/operator/snapshot` with an operator-supplied bearer token held **only in page memory**, never in URL, cookies, localStorage, sessionStorage, or HTML. It clears credentials on logout, navigation, and 401/403/503; an incrementing generation fence discards responses arriving after logout or token replacement. Fetch uses `credentials: omit`, `cache: no-store` and `redirect: error`. The page enforces restrictive CSP, no-store, no-referrer and anti-framing headers. Display is text-only via `textContent`, with a strict field whitelist and no arbitrary upstream HTML.

The UI shows each resource as `READABLE_UNVERIFIED`, `UNKNOWN` or `FORBIDDEN_BY_ROLE`; no status is upgraded to LIVE attestation. The static page itself is public and contains **no protected data**; the API continues to enforce the RBAC boundary. This is a transitional read-only console, **not a full login/session system**. Existing unprotected dashboard/demo/copilot routes are not changed by this increment and require separate authentication/CSRF hardening before internet exposure. Tokens typed in a page remain sensitive to a compromised origin, browser extension or local device. Use TLS and a trusted reverse proxy in deployment; LAN HTTP does not provide confidentiality.

Tests: `tests/test_portal_operator_console.py` checks mounted HTTP routes, headers, static JS safety patterns, absence of browser persistence, and unauthorized API response. These are unit/HTTP/static tests, **not** real browser Playwright, Core/Evidence integration, Debian verification, or production qualification.
