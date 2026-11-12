# AIOPS2 portal read-only API contract — proposal v0 (2026-11-12)

Status: DRAFT / NOT IMPLEMENTED / NOT ACL-QUALIFIED. This document specifies desired behavior, not an assertion that existing routes comply. No Core, Worker, Twin, GLPI, PG, Policy/HITL or Debian runtime changes.

## Security boundary

All portal reads MUST authenticate the actor server-side and resolve tenant membership and permissions from trusted server session/identity sources. Never trust actor_id, tenant_id, role, mode, or permissions supplied by the browser. Cross-tenant resources MUST be filtered at the query boundary and fail with 403 or indistinguishable 404 (policy-defined), without metadata leakage. Missing authentication: 401. Authenticated but insufficient permission: 403 with `BLOCKED`; no fallback to demo data. bootstrap/components/copilot/demo remain disabled under `TENANT_ACL_NOT_QUALIFIED` until separately qualified.

All endpoints are GET, safe, idempotent and read-only. No implicit run creation, policy approval, GLPI synchronization or remediation. No browser-persisted secrets.

## Common response envelope

```json
{
  "schema_version": "readmodel.v0",
  "state": "UNKNOWN",
  "data": null,
  "error": {"code": "SOURCE_UNAVAILABLE", "retryable": true},
  "provenance": {"system": "runs", "source_ref": null, "observed_at": null, "collected_at": null},
  "freshness": {"as_of": null, "max_age_seconds": 60, "stale": true},
  "page": {"limit": 50, "next_cursor": null},
  "request": {"generation": "opaque-client-generation", "request_id": "server-generated"}
}
```

State enum: `READY` (source verified and authorized), `UNKNOWN` (not observed/unverifiable/stale), `ERROR` (transport, parse, timeout, or upstream failure), `BLOCKED` (ACL/policy gate). `data:null` for UNKNOWN/ERROR/BLOCKED; never synthesize OK/empty collection from failed reads. `source_ref` must be opaque and non-secret. `observed_at` describes source measurement, `collected_at` adapter ingestion; both UTC RFC3339 or null. Missing provenance implies UNKNOWN. `stale:true` never promotes to READY. Never infer service health from host inventory.

Error mapping: 400 INVALID_QUERY; 401 UNAUTHENTICATED; 403 TENANT_FORBIDDEN / TENANT_ACL_NOT_QUALIFIED; 404 RESOURCE_NOT_FOUND (tenant-safe); 408/504 UPSTREAM_TIMEOUT; 499 CLIENT_CANCELLED only if supported by gateway, otherwise aborted request without response; 502 UPSTREAM_TRANSPORT_ERROR; 503 SOURCE_UNAVAILABLE. Explicit `error.code` on all non-READY responses. A 200 UNKNOWN is allowed only for a valid authorized read with unavailable source, not for authorization failures.

## Endpoint families and source expectations

| GET path (proposed) | Primary read source | Required qualifiers |
|---|---|---|
| /api/read/dashboard/health | service registry + health adapter | tenant, per-source freshness |
| /api/read/incidents | incident store | cursor, limit, filters |
| /api/read/services | CMDB/registry | tenant, service_id optional |
| /api/read/noc | NOC events | cursor, time window |
| /api/read/twin | Twin snapshot adapter | mode, snapshot_id; no simulation mutation |
| /api/read/runs | Runs read model | run_id for detail, cursor for list |
| /api/read/runs/{run_id}/timeline | immutable run events | run_id, mode, incident_id consistency |
| /api/read/evidence | evidence index | run_id, mode, incident_id |
| /api/read/policy-hitl | policy decisions read model | actor scope; no approval action |
| /api/read/observability | Prometheus/Grafana query adapter | allowlisted metric/query; no arbitrary proxy |
| /api/read/glpi | GLPI read adapter | CMDB entity and tenant mapping |
| /api/read/copilot | explanation/suggestion history | authorized incident/run references; no tools that mutate |

Each family must declare a source-specific freshness SLA, explicit authorization capability, cursor semantics and response schema before implementation. Do not reuse these proposed paths as proof of deployed routes. Cursor must be opaque, tenant-bound, filter-bound, expiring and tamper-evident; default limit 50, maximum 100; stable sort by (timestamp, immutable id). Reject invalid cursor 400. Timeout budget: adapter 5s, upstream less than adapter budget; cancellation propagates via abort signal; no background side effects. Response generation must match active request generation before UI promotion; stale responses discarded even if HTTP 200.

## Required negative contract tests (not yet executed)

1. No session -> 401, no source call; forged actor/tenant header cannot elevate permissions.
2. Authenticated unauthorized tenant -> 403/404 with no existence or provenance leak; same tenant-bound cursor rejected across tenants.
3. Missing run_id, mode or incident_id on detail/evidence -> 400; inconsistent tuple -> 400 or tenant-safe 404, never READY.
4. Upstream timeout -> ERROR/UPSTREAM_TIMEOUT and data null; transport exception -> ERROR/UPSTREAM_TRANSPORT_ERROR.
5. Cancelled request -> no READY promotion or mutation; old generation completing after new generation -> ignored, data null.
6. Missing observed_at/source_ref -> UNKNOWN, data null; stale observation -> UNKNOWN, never healthy.
7. Partial or malformed upstream payload -> UNKNOWN/ERROR, no invented count, no unfiltered records.
8. ACL-unqualified bootstrap/components/copilot/demo -> BLOCKED, no bypass via query or fallback.

## Debian telemetry separation

The existing proposed collector `scripts/observability/debian_rootless_readonly.py` runs as UID 1001 against rootless Docker socket. Its output is host telemetry only, never a portal business read model or tenant authorization source. It may include identifiers in OBSERVED inventories: review disclosure policy before any portal ingestion. Missing health endpoints, events or sanitized logs remain UNKNOWN until a vetted allowlist exists. Do not collect env, secrets, volume content, customer records or tokens. A cron install is reserved for coordinator review.

Coordinator-only proposed validation (not executed here):
```sh
python3 -m unittest discover -s tests/observability -p 'test_debian_rootless*.py' -v
# after code/security review, verify UID 1001, trusted path ownership, symlink/TOCTOU exposure,
# lock permissions, timeouts, rotation and redaction in an isolated host test.
# coordinator chooses reviewed absolute paths and installs cron; no installation in this PR.
```

## Handoff and gates

Parent commit: 4851695a4482ad151a0c8b70dfac5efa130d8941 (#691). Coordinate on issue #555 and PR #545. CODE: documentation-only proposal; CI: UNKNOWN until exact SHA run; DEBIAN: NOT_INSPECTED/NOT_INSTALLED; E2E: NOT_EXECUTED; ACL: NOT_QUALIFIED. Require independent security review and explicit tenant qualification before activating any blocked route. No merge or deployment authorized by this proposal.
