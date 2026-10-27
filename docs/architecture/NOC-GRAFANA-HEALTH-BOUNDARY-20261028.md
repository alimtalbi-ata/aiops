# Grafana readiness is not Grafana observation (P0 NOC)

Date: 2026-10-28. Reuse review: PR #36 provides `demo/integrations/v21315/grafana/acme-synthetic-observability.json` tagged `SIMULATED_TARGET`. It is **not** imported as runtime monitoring evidence or claimed to be live. This micro-lot instead probes the actual Grafana `GET /api/health` endpoint through the existing portal, without any synthetic Grafana substitute.

The authenticated `GET /api/noc/grafana-health` route requires `AIOPS_PORTAL_READ_TOKEN` before network access. It accepts only an exact internal Grafana URL `AIOPS_GRAFANA_READ_URL` from `http://aiops2-grafana:3000`, `http://localhost:3000` or `http://127.0.0.1:3000`; no path, query, userinfo, redirect, proxy, arbitrary port or TLS downgrade. The request is GET-only, timeout 3s, JSON-only, max 4096 bytes, duplicate-key rejection and database readiness check. Missing configuration, invalid response or unreachable service is 503 with a redacted error and no-cache headers.

A successful response says `GRAFANA_HTTP_READY_UNATTESTED` and `grafana_observation=NOT_TESTED`. It **does not** assert the presence of SAN/Payments metrics, Checkmk/Thruk connectivity, tenant ACL, dashboard identity, browser capture or LIVE evidence. The portal exposes a button for this limited check.

**Deployment blocker:** existing Compose places portal on `aiops2-public/aiops2-control` and Grafana on `aiops2-observability`; the portal cannot resolve/reach Grafana over the current network isolation. We intentionally do not join these networks in this PR. A future narrow, authenticated observability gateway or reviewed network policy is required before configuring `AIOPS_GRAFANA_READ_URL` on Debian. No server was accessed.

CI reuses `.github/workflows/quality.yml` with contract tests and a separate job containing a **real Grafana container**, not a mock. If the image cannot start, report BLOCKED; do not silently replace it with a fake. Tests do not cover actual dashboards, tenancy or NIM inference. No new deployment pipeline, secrets or remediation action.
