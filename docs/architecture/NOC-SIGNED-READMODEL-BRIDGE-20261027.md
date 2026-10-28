# NOC signed read-model bridge — targeted PR #36 reuse

Date: 2026-10-27. Source ported from PR #36 `app/portal/noc_runtime.py` and `tests/test_portal_noc_runtime_adapter.py` rather than merging its large, divergent tree.

The existing Portal now mounts `GET /api/noc/runtime-state`. This is an **authenticated, read-only** upstream seam, not a Checkmk/Thruk integration proof. A browser visiting the public NOC panel sees **UNKNOWN**, not a fabricated live state. The signed response contains incident/run IDs, a timeline, optional ticket ID and optional evidence digest. Neither the ticket nor digest is independently verified; all runtime/production attestations remain false. No LLM call or autonomous remediation is enabled.

## Operator configuration (never commit actual values)

- `AIOPS_PORTAL_READ_TOKEN`: operator Bearer token required to read the route. Unconfigured returns 503, invalid returns 401, before contacting the upstream.
- `AIOPS_NOC_READ_MODEL_URL`: absolute upstream GET endpoint.
- `AIOPS_NOC_READ_MODEL_TOKEN`: upstream Bearer credential.
- `AIOPS_NOC_READ_MODEL_HMAC_KEY`: independent shared HMAC key (32+ UTF-8 bytes).
- `AIOPS_NOC_ALLOWED_ORIGINS`: explicit comma-separated origin allowlist, including scheme and port.

The upstream must emit `application/json` with `X-AIOps-Read-Model-SHA256` and `X-AIOps-Read-Model-Signature` headers covering the exact JSON bytes. Schema: `aiops.noc-runtime-readmodel.v1`, `provenance=RUNTIME_READMODEL`, `run_id`, `incident_id`, `observed_at` UTC Z, and 1–100 `steps` with OK/WARN/CRIT/UNKNOWN states. Responses older than 300 seconds are rejected. No redirects or ambient proxies, 3-second timeout, max 256 KiB. All outputs set no-store and never authorize remediation.

The portal's **read token is an operator-wide read privilege**, not per-tenant ACL. Do not configure this bridge for a multi-tenant source or expose tokens to untrusted browsers. Per-run/tenant authorization and source ownership checks must be implemented before a multi-tenant rollout. The authenticated source payload is not authenticated as a screenshot or proof of production runtime. The adapter does not currently ingest raw Checkmk Livestatus or read Grafana; that needs a separate, qualified upstream provider.

## Tests and deployment limits

`python -m unittest discover -s tests -p 'test_portal_noc_runtime_adapter.py' -v` is included in the existing quality workflow. Tests exercise synthetic signed envelopes and fake HTTP transport for **unit/security contracts only**; they are not integration tests of Checkmk, Thruk, Grafana or a running NOC provider. Runtime qualification and Debian rollout are NOT_TESTED. No new service, network port, database mutation, or action endpoint is introduced. Rollback is source-only: revert this PR's merge commit and rebuild Portal through the normal reviewed process.

## 2026-10-28 — Tenant-scope refusal before projection

The shared portal read token is not a tenant-scoped authorization credential. After HMAC and JSON validation, the adapter rejects any tenant/organization/workspace/account/customer scope claim, including nested or null fields, instead of dropping it from the allowlisted projection. Normalization catches common case, separator and Unicode compatibility variants; the walk is bounded. Errors are redacted, no-store 503. This does **not** establish cross-tenant ACL; it is a deny-by-default interim guard. Future qualified Core/IdP authorization must bind a verified tenant identity and pre/post-filter results before scoped data is exposed. PR #36 remains a source of selected read-only contracts only, not runtime attestation.
