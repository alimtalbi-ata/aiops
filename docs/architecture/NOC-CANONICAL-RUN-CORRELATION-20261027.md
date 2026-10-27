# NOC signed payload → canonical Core Run (read-only, 2026-10-27)

This is a **targeted continuation of PR #36's NOC read-model contract**, following the signed upstream bridge merged through PR #47. It is **not** a Checkmk/Thruk integration qualification or a runtime screenshot attestation.

## Operator path

Portal NOC panel → enter `AIOPS_PORTAL_READ_TOKEN` into the transient password field → `GET /api/noc/correlation` → signed NOC read model (same HMAC and freshness gate as `/api/noc/runtime-state`) → Core `GET /api/runs/{run_id}` → exact comparison of both Run and Incident IDs.

The portal makes no write request for this path. The token is used in the same-origin Authorization header and cleared from the input after clicking; never placed in the URL or browser storage. If token is absent, provider is unavailable, Core cannot be read, or identities differ, no positive correlation is claimed.

**Safety boundaries:** allowlisted Core hostname, no proxy or redirect, GET only, 3-second timeout, bounded JSON, duplicate-key rejection, no untrusted raw Core fields in output, no credentials sent to Core. The portal's existing shared read token is not per-tenant RBAC; **multi-tenant ACL isolation is NOT_IMPLEMENTED** and must be designed before multi-tenant deployment. The Core read API itself is not authenticated in the inspected baseline. Do not expose it publicly.

`MATCHED_UNATTESTED` proves only that a signed provider's asserted identifiers equal an independently readable Core Run. It does **not** prove a live Checkmk/Thruk observation, signed evidence bytes, ticket authenticity, Grafana metrics, NIM inference or RAG grounding. DEMO/REPLAY/STORY are labelled `SYNTHETIC_CANONICAL_RUN`; LIVE is labelled `LIVE_MODE_UNATTESTED`. No remediation or state transition is possible through this endpoint.

## Verification and limitations

- Offline unit/security suite: `python -m unittest discover -s tests -p test_noc_canonical_correlation.py -v`. It uses a temporary local import shim for the existing NOC module during isolated authoring; this is **not a real upstream integration test**. Full-repository GitHub Actions checks must be independently confirmed.
- Existing `.github/workflows/quality.yml` invokes the new suite on PRs.
- No real Checkmk/Thruk service, Grafana datasource, GLPI ticket, NIM server, Ollama model or Debian portal was accessed.
- PR #36 `demo/noc_drilldown.py` and `demo/rag_ops_fixture_catalog.json` were reviewed as **synthetic-only**; they are not wired to this runtime route because their simulated corpus cannot ground a live claim.
- Next micro-lot: authenticated tenant-scoped Core read model, observed Checkmk/Thruk adapter from a real CI container, Grafana correlation and cited RAG with a source-backed read-only diagnostic.
