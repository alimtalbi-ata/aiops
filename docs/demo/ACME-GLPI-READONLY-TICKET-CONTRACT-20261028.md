# ACME ITSM — GLPI Ticket read-only observation contract (2026-10-28)

## Scope and architecture

The existing SAN → ESXi → VM → Payments scenario from PR #50 is deterministic and synthetic. PR #56 adds signed NOC ↔ Core Run correlation, but explicitly leaves `ticket_id=null`. This increment provides the next **pure read-only GLPI ticket observation adapter**, without prematurely mounting it in the Portal.

`app/shared/glpi_ticket_read.py` can be used by a future integration-network bridge. It performs only `GET /apirest.php/Ticket/{numeric_id}` with operator-provisioned `App-Token` and `Session-Token`; it does not create sessions, create/update tickets, or mutate state. It validates the returned ticket ID, entity/tenant ID, status, bounded JSON response, content type and origin. It refuses redirects, ambient proxies, non-HTTPS origins outside isolated GitHub CI, synthetic ticket labels and unexpected entity IDs. No title, description or PII is returned in the projection.

Required environment variables: `AIOPS_GLPI_API_BASE_URL` (exact `https://<host>/apirest.php`), `AIOPS_GLPI_APP_TOKEN`, `AIOPS_GLPI_SESSION_TOKEN`, `AIOPS_GLPI_ENTITY_ID`. For ephemeral CI only, `CI=true` permits `http://aiops2-glpi/apirest.php`. Never commit actual tokens. Provisioned session expiry must be handled by a future dedicated bridge, not by the public Portal.

The returned `OBSERVED_UNCORRELATED` confirms only that the authenticated GLPI API responded with a matching ticket ID and entity. It **does not** establish linkage to the canonical Incident or Run, prove ticket freshness (GLPI `date_mod` lacks a qualified timezone), authenticate a browser capture or permit LIVE remediation. `correlation_state=UNKNOWN`, `runtime_attested=false`, `production_qualified=false` remain explicit.

The Portal in `compose.yml` is on `aiops2-control` and `aiops2-public`; GLPI is on `aiops2-integration`. **Do not connect the Portal directly to GLPI**. A future authenticated read-only bridge must be placed on the integration network, return a bounded and independently verifiable correlation receipt to the Core/Portal through a narrowly defined control boundary, and enforce RBAC, tenant isolation, freshness and ID cross-references. No Compose network changes are included here.

## Reuse assessment

Reviewed PR #36 `demo/noc_topology.py` (head `f353497f`): deterministic synthetic graph, no GLPI API reader. PR #50 already ported the useful ACME fixture/impact contract from PR #36; copying that topology again would introduce divergent duplicate graphs. This increment reuses the canonical ACME fixture and existing architecture, while adding only the missing GLPI read contract.

## Validation boundary

`tests/test_glpi_ticket_read.py` covers 14 offline tests, including entity mismatch, forged ID, synthetic ticket label, redirects, HTTP restrictions, missing credentials, duplicate keys, body limits, malformed JSON, secret redaction and negative LIVE authority. The existing `.github/workflows/quality.yml` runs these tests. **These are offline contract tests with controlled HTTP responses, not a real GLPI integration test**.

A genuine GLPI integration test needs a fully initialized ephemeral `glpi/glpi` + MariaDB service, REST API enabled, a provisioned test session token, test tenant and ticket. Until that environment is available, integration status is **NOT_TESTED**; do not substitute fake GLPI responses and label them integration PASS.

Next: land PR #56 or port its correlation function without conflict; build an authenticated integration-network bridge with a separate role; exercise it against real ephemeral GLPI, and only then expose a safe correlated ticket field in the Portal.
