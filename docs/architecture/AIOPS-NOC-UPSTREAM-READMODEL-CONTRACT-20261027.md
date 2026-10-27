# AIOps NOC upstream read-model bridge — contract v1

Date: 27 October 2026. This contract adds an optional **read-only API adapter** to the existing portal process. It does not create a service, listener, port, browser session, or backend write path.

## Route and authentication

- **GET /api/noc/runtime-state** is mounted by **app/portal/main.py** in the existing portal ASGI application.
- The caller must provide **Authorization: Bearer <AIOPS_PORTAL_READ_TOKEN>**. A missing configured portal token returns 503; a missing/invalid caller token returns 401 before any upstream access.
- The optional upstream must be configured with **AIOPS_NOC_READ_MODEL_URL**, **AIOPS_NOC_READ_MODEL_TOKEN**, **AIOPS_NOC_READ_MODEL_HMAC_KEY** and **AIOPS_NOC_ALLOWED_ORIGINS**. The URL origin must exactly match an explicitly allowlisted origin, including scheme and port.
- The upstream request is GET-only, has a three-second timeout, follows no redirects, disables ambient HTTP_PROXY/HTTPS_PROXY settings, accepts only application/json, reads at most 256 KiB and requires the received byte count to match Content-Length when provided. The Bearer token is sent only to that allowlisted origin.
- The response must include **X-AIOps-Read-Model-SHA256** and **X-AIOps-Read-Model-Signature**. The SHA-256 covers the exact response bytes; the HMAC-SHA256 uses the separately provisioned key and covers those same bytes. Duplicate JSON keys, non-standard JSON constants, invalid UTF-8, mismatched digest/signature, malformed schema, stale/future timestamps, invalid states and unverified 02→03 claims are rejected.

## Source payload

The JSON root must use schema **aiops.noc-runtime-readmodel.v1** and provenance **RUNTIME_READMODEL**. It must carry a stable run_id, incident_id, a canonical UTC observed_at timestamp ending in Z, and one to 100 timeline steps whose states are OK, WARN, CRIT or UNKNOWN. Ticket ID, event timestamp, correlation ID and evidence digest are optional and remain absent when not supplied.

The public projection contains only reviewed fields. It reports **source_payload_authenticated=true** and **source_authentication=HMAC_SHA256_VERIFIED** after signature verification, but keeps **runtime_attested=false**, **runtime_authenticated=false** and **live_remediation_authorized=false**. A ticket is a signed upstream claim, not an independently verified GLPI record. An evidence hash is a reported digest, not proof that the screenshot bytes were fetched and checked. The current portal image does not embed the canonical n8n 02→03 verifier; any payload attempting to include handoff details is rejected rather than accepted on a provider assertion.

## Configuration and deployment

The four environment variables are optional and blank in config/.env.example. The deployment template migration adds missing keys without inventing upstream credentials. When unset or incomplete, the route returns HTTP 503 noc_source_not_configured; the static /noc page and /api/platform/components remain unchanged and continue to describe the integration plan, not live health.

Configure the upstream token and HMAC key out-of-band on both sides. Use HTTPS for remote origins. An HTTP origin is only acceptable when the operator explicitly allowlists an internal origin on a trusted private network. Never commit the token, HMAC key, .env, response dumps, browser sessions or real evidence into the repository or release kit.

## Qualification

tests/test_portal_noc_runtime_adapter.py uses synthetic JSON and a synthetic key. It checks HMAC/digest integrity, bounded projection, timestamp and schema rejection, identity fail-closed behavior, caller auth, missing configuration and error redaction. The candidate-kit workflow runs these tests and embeds the adapter and tests in the cumulative ZIP.

This is an integration seam, not proof that Checkmk/Thruk is connected. Until a trusted provider is configured and independently qualified, there is no upstream runtime data. Even with a signed payload, the route does not attest exact application screenshots, a real GLPI ticket, a browser capture time, or production readiness. No writes, additional ports, production changes or LIVE remediation are permitted by this route.

## Rollback

Source-only rollback: revert the commit that mounts portal.noc_runtime.router, remove app/portal/noc_runtime.py and its tests from the branch, then regenerate and verify the cumulative candidate. Do not run deployment commands on the production host to roll back this source change.


## Preflight behavior

deploy/check-secrets.sh treats the bridge as an optional all-or-none feature. If all four settings are blank it emits a warning that the endpoint will return 503 and continues. If any setting is present, it requires all four, a token of at least 16 characters, an HMAC key of at least 32 characters, and an endpoint origin exactly present in the comma-separated allowlist. It never prints the values and never calls the upstream. tests/test_preflight_secrets.sh exercises disabled, partial, valid, origin-mismatch and short-HMAC cases with synthetic values.
