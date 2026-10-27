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
