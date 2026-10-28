# NOC signed event → canonical DEMO Run → synthetic RAG context (2026-10-28)

## Narrow scope and reuse

The canonical portal reuses the signed NOC read-model bridge from PR #47, exact Core Run/Incident correlation from PR #52, and **only** the six PR #36 synthetic RAG fixtures ported in PR #54. No large PR #36 merge. The new read-only `GET /api/noc/demo-context` binds **three exact identities** before returning any synthetic citation: HMAC-verified signed NOC Run/Incident identity, the independently fetched Core Run/Incident identity in mode `DEMO`, and a signed NOC `asset` + `event_key` pair matching one catalog entry.

The NOC signed source may optionally include `asset` and `event_key`, each checked against the existing bounded identifier regex. Malformed identifiers and tenant-related claims (`tenant_id`, `tenant`, `organization_id`, `org_id`) are rejected at the signed projection boundary. The Core Run is also rejected if any of those tenant fields is present, because **this shared operator token is not a tenant-scoped authorization mechanism**. This is an explicit multi-tenant fail-closed fence, **not** qualified tenant RBAC.

The endpoint first checks the existing operator Bearer token, then reads the signed NOC source and the exact Core Run via GET-only no-proxy/no-redirect adapters. If the source or Core is unavailable, it returns HTTP 503 with no secret or URL leakage. Identity mismatch, non-DEMO mode, missing asset/event, or no exact synthetic fixture match return `UNKNOWN` and **zero citations**. No fixture is loaded before the DEMO Run and signed identities match. The UI exposes a new **Contexte RAG DEMO lié** button under the existing NOC section and clears the transient operator token field after use.

The only positive state is `SYNTHETIC_CONTEXT_ONLY`: a deterministic reference crosswalk, **not** a Checkmk/Thruk observation, Grafana metric, LLM response, vendor-authoritative document, screenshot attestation or LIVE remediation permission. Output includes the signed payload digest, exact canonical identifiers, the catalog digest and individual synthetic document SHA-256. All runtime/production/tenant qualification flags remain false.

## Qualification

- Unit and HTTP contract tests: `python -m unittest discover -s tests -p 'test_noc_demo_context.py' -v`.
- Existing `.github/workflows/quality.yml` includes this suite on pull requests, with Python compilation and static/Compose gates.
- Tests use synthetic signed payloads, mocked source/Core reads and the committed synthetic fixture. They do **not** prove an actual Checkmk/Thruk provider, Core+Temporal integration, Grafana datasource, Ollama 4B, NVIDIA NIM, real evidence, tenant ACL or Debian deployment.
- Existing Grafana readiness work is separate draft PR #58; no cherry-pick or parallel workflow was introduced.

## Next micro-lot

Qualify an actual read-only Checkmk/Thruk service provider in isolated CI and supply signed `asset`/`event_key` metadata; then design tenant-scoped identity from caller through source/Core before allowing any observed RAG retrieval. Add real Grafana datasource queries and source-backed cited diagnostics only after ACL, provenance and freshness gates. Preserve DEMO/SIMULATION/LIVE separation and the existing policy HITL fences.
