# V30 read-only source contract — 2026-11-12

Scope: source-level validation helper only; NOT wired into the deployed V30 router. No Debian host or Prometheus connectivity attested.

## Endpoint decision
- `/prometheus`: route must use a fixed server-side metric registry, fixed recording queries selected by metric key; no browser PromQL, target URL, label selector, arbitrary query, or tenant header. Session actor/tenant validated server-side before cache/query; cache key includes tenant, actor scope, mode, generation, metric and window.
- `/databases`: metadata/health from an authorized read-only service catalog only. No SQL, connection string, database browsing, schema listing or raw query endpoint. UNKNOWN when adapter/ACL unavailable.
- `/cmdb`: GLPI authoritative for CI/ticket identifiers only after connector identity, ACL, provenance and freshness are qualified. Twin is a versioned derived graph, not a second authoritative CMDB. Conflicts are UNKNOWN, not silently reconciled.

## Metric envelope
`{state, http_status, reason, data:{metric,value,unit,window_seconds,observed_at,freshness_seconds,source,mode,generation}}`. READY only with validated finite sample, allowed source, UTC-aware observation, generation match and age <= registry threshold. UNKNOWN contains no data. Units: ratio, bytes, requests/second; these are contract units, **not observed live values**. Window is requested aggregation interval, not freshness. Backend must verify actual Prometheus query expression, series label tenant scope, timestamp, source endpoint and HTTP response before calling the helper. Do not accept caller-controlled `authorized_tenants` in HTTP code.

## Required adapter gates (not yet qualified)
1. 401 no verified session; 403 cross-tenant, including cache, cursor and GLPI IDs.
2. 400 unknown metric/mode/window and malformed run_id/incident_id; reject tuple mismatches with 403/409 before any upstream read.
3. Timeout/cancellation: cancel upstream request, return UNKNOWN/ERROR with null data; never reuse previous READY. Stale generation cannot publish to cache/UI.
4. Paginate CMDB/incident/timeline via signed opaque cursor bound to actor/tenant/filter/mode/generation/expiry; reject replay and tampering.
5. Provenance: source identifier, observed_at, ingested_at, graph/source version and retrieval status. Never promote synthetic DEMO/REPLAY to LIVE.
6. Network: V30 -> Prometheus only after validating existing topology, firewall and proxy ACL; prefer existing private service path. No network expansion or deployment in this PR.
7. Debian: reuse existing cron only after owner/UID1001, script hash, schema, retention, permissions, lock and observed run receipt are independently attested. No second collector.

## Test and rollback
`python3 -m unittest tests.test_metric_read_contract -v` (proposed; NOT_EXECUTED in GitHub). Existing test suite and V30 E2E remain UNKNOWN. Rollback: revert the two source/test commits and this documentation commit; no deployment or database migration.
