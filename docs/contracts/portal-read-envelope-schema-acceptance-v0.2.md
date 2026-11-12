# AIOPS2 read-envelope schema acceptance — proposal

Status: **NOT_IMPLEMENTED / NOT_EXECUTED**. Companion to `portal-read-envelope-v0.2.schema.json`; schema is a structural guard, **not** an authorization certificate.

## Required checks

Validate using a JSON Schema Draft 2020-12 implementation with `format` assertion for RFC3339 timestamps (format is annotation-only in some validators). Reject extra fields, missing mandatory keys, invalid family/state, READY with null data, READY with absent source reference or observation time, READY with stale=true, and UNKNOWN/ERROR/BLOCKED with non-null data. Check timestamps against server time, skew budget, and per-source max age in application logic; JSON Schema cannot prove temporal truth, source ownership, completeness or provenance.

## Negative adapter acceptance (synthetic fixtures only)

| Case | Expected behavior | Spy assertion |
|---|---|---|
| No authenticated principal | HTTP 401 | 0 source/cache reads |
| Missing tenant membership/capability | HTTP 403 | 0 source/cache reads |
| Forged tenant or actor header | Authenticated context wins | No foreign rows/counts/facets |
| Foreign object | Tenant-safe 404 or 403 | No existence leak |
| Tampered/foreign/expired cursor | 400/403 | No fallback first page |
| Missing run_id, mode or incident_id | 400 | 0 upstream reads |
| Inconsistent immutable run tuple | 400 or tenant-safe 404 | No evidence disclosure |
| Upstream timeout | 504 or documented error | No READY or partial data |
| Cancellation | Aborted or 499 | Upstream abort signal observed |
| Response generation older than active generation | Discard | UI/cache unchanged |
| Source timestamp missing/future/expired | UNKNOWN, data=null | No fabricated age or count |
| Docker host healthy, business source absent | UNKNOWN business state | No host-to-business promotion |

For each family (dashboard/health, incidents, services/CMDB, NOC, Twin, Runs/timeline, Evidence, Policy/HITL, Prometheus/Grafana, GLPI, Copilot), require authorization-before-read, per-object ACL, tenant-scoped cache keys, safe pagination, provenance and cancellation. HTTP 401/403 are transport denials, never successful 200 envelopes. `BLOCKED` is only for an authorized request that is blocked by a documented non-auth policy.

## Operational separation

Debian host collection uses `aiops2.host_observation.v1`, not this schema. No Debian host inspected, cron installed, CI or adapter tests executed. Coordinator must review `scripts/observability/debian_rootless_readonly.py` at pinned SHA and execute `python3 -m unittest discover -s tests/observability -p 'test_debian_rootless*.py' -v` before approving a reviewed absolute-path cron invocation under aiops UID 1001. Confirm secure directory ancestry, lock, timeout, JSON UTC, retention, redaction and UNKNOWN failure behavior. No Core/Worker/Twin, GLPI/DB, Policy/HITL or LIVE changes.
