# P0 — Core/Twin bootstrap read boundary

**Scope:** source-only change to the existing portal (external target port 17777). Adapted the fail-closed dedicated read Bearer token pattern from draft PR #36; no mass merge and no second portal.

- `GET /api/portal/bootstrap` now requires `Authorization: Bearer <AIOPS_PORTAL_READ_TOKEN>`. Missing server-side configuration returns 503; invalid or missing token returns 401; neither contacts Core/Twin. Success and denials are non-cacheable and explicitly unverified.
- `GET /` is a public **shell** only: it never reads Core/Twin server-side. Metrics, Runs and Twin start at UNKNOWN. An operator may enter a one-shot read token to fetch the authenticated API. The token is cleared from the field before the request, is not saved to cookies/localStorage and is not embedded in URLs or HTML.
- The UI renders only text nodes and bounded Run rows, and discards responses after a clear or newer request. A failed or malformed upstream remains UNKNOWN; a configured integration browser link is not a live health claim.
- `GET /assets/portal-bootstrap.js` serves the local browser read script; it is public and contains no credentials.

## Browser envelope validation (2026-10-28)

Before rendering any Core/Twin read-model values, the browser now requires the exact `aiops.portal.readmodels.v1` schema, `UNATTESTED_UPSTREAM_API_READ` provenance, explicit `runtime_authenticated: false` and `live_remediation_authorized: false`. All three source states must be `UNKNOWN` or `READABLE_UNVERIFIED`, with matching null/payload shapes and bounded metric/Run/Twin values. A forged LIVE claim, contradictory UNKNOWN payload or malformed row leaves the entire panel UNKNOWN; HTTP 200 alone never implies a readable source. This is defense in depth against malformed upstream or gateway responses, not cryptographic attestation or tenant RBAC.

## Test and qualification boundary

`tests/test_portal_bootstrap_auth.py` uses in-process FastAPI TestClient with patched upstream HTTP adapter. It tests 401, 503, no unauthorized reads, authenticated read-only projection, degraded UNKNOWN, no anonymous Core reads, JS delivery. It is **not** a real Core/Twin integration test. The existing `.github/workflows/quality.yml` runs it in GitHub Actions. No Ollama/NGX inference or other service mock is presented as integration.

**Not yet complete:** The old `POST /api/demo` and `POST /api/copilot` are separately addressed by draft PRs #57/#70, not integrated into this branch. `/api/portal/components` and integration navigation are public, with configured URLs potentially visible. Global SSO, tenant-scoped RBAC, per-source ACL, real container E2E, Debian, authenticated captures and video remain NOT_TESTED/BLOCKED. Do not expose the portal to untrusted networks until these are resolved.

## Rollback

Revert this PR's commits to restore the previous public bootstrap (security regression; only for an isolated legacy environment). No schema migration, persistent data or service restart is included. No LIVE authorization is granted.
