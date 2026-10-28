# P0 — Core/Twin bootstrap read authentication (2026-10-28 10:04 Europe/Paris)

- Base: `111b3bd5988ac35cd5f83c1fc93813b96c09111e`. Target: source-only portal port `17777`; no Debian runtime accessed.
- Selective reuse: PR #74's anonymous UNKNOWN shell, one-shot text-only JS and negative HTTP/DOM tests; use the **already merged** `_require_portal_read_auth` / `_noc_json_response` from PR #36 NOC bridge instead of introducing a duplicate token guard.
- `GET /api/portal/bootstrap` now requires `AIOPS_PORTAL_READ_TOKEN` Bearer viewer; rejects 401/503 before any Core/Twin calls; no-store on all responses.
- `GET /` no longer calls Core/Twin anonymously, renders UNKNOWN until explicit token input; token is immediately cleared, fetch uses `credentials: omit`, no storage or HTML injection; stale responses ignored after clearing.
- This is **not** SSO, per-tenant ACL, or runtime attestation. Existing `POST /api/demo` and `POST /api/copilot` remain unprotected in main; PR #57/#70 convergence is still required. Core/Twin upstreams have not been qualified as isolated real services.
- Tests: `tests/test_portal_bootstrap_auth.py` (TestClient with patched upstream, no real integration), `tests/test_portal_bootstrap_client.mjs` (synthetic DOM), existing portal navigation regressions, and existing `quality.yml`.
- Rollback: revert the branch PR; no service configuration or state mutation.
