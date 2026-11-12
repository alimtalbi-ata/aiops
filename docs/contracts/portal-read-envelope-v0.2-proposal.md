# AIOPS2 portal read envelope v0.2 — normative proposal

Status: **PROPOSAL / NOT_IMPLEMENTED / NOT_TESTED**. Complements `portal-readmodels-v0-proposal.md` and `portal-readmodels-negative-matrix-v0.1.md`. This document does not certify any deployed adapter.

## Boundary and common envelope

Server must derive actor, active tenant, membership, capability and scope version from verified authentication on **each** request. Never accept browser actor/tenant/role claims as authority. Resolve tenant ownership and ACL **before** querying any record, aggregation, search index, cache, external connector or metric. No cross-tenant existence, count, facets, error details, source URLs, cache hits or timing-dependent hints.

For an authorized read, response schema (illustrative values below are **synthetic**, not observations):

```json
{
  "schema_version": "aiops2.read.v0.2",
  "family": "incidents",
  "state": "UNKNOWN",
  "reason_code": "SOURCE_UNAVAILABLE",
  "data": null,
  "provenance": {
    "source_kind": "incident_read_store",
    "source_ref": null,
    "observed_at": null,
    "collected_at": null,
    "snapshot_watermark": null
  },
  "freshness": {"max_age_seconds": 60, "age_seconds": null, "stale": null},
  "request": {"generation": "synthetic-g1", "correlation_id": "synthetic-c1"},
  "page": null
}
```

Fields are required even when null, except `page` which is null for detail. `data` MUST be null for UNKNOWN/ERROR/BLOCKED; no fabricated zero or empty array. `READY` requires complete authorized data, validated provenance, observed timestamp, a documented source-specific freshness budget and valid snapshot. `UNKNOWN` = insufficient/unavailable/stale observation; `ERROR` = validated upstream/protocol failure; `BLOCKED` = known authorization or policy denial. HTTP 401/403 MUST remain transport errors; do not return HTTP 200 with a cosmetic BLOCKED state. 403 bodies MUST NOT include forbidden resource metadata. HTTP 404 may conceal foreign tenant resources. Cancellation is a terminated request (or documented 499), not a successful empty response.

Provenance `source_ref` must be a server-generated opaque, authorized reference, **never** a raw GLPI/Grafana/Evidence URL or secret. `observed_at` is source observation time; `collected_at` is adapter ingest time; `snapshot_watermark` is the consistency boundary. They are not interchangeable. Future timestamps beyond bounded clock skew, malformed timestamps, missing source refs or expired freshness => UNKNOWN. The freshness threshold is configured per family and source, not inferred from Docker uptime.

## Family source and security contract

| Family | Authoritative projection | Mandatory qualifier | Read-only boundary |
|---|---|---|---|
| dashboard/health | registry + service health adapters | tenant, dashboard.read | no host telemetry as business health |
| incidents | tenant-scoped incident read store | incidents.read | no unqualified count |
| services/CMDB | approved service/CMDB snapshot | cmdb.read + entity map | no unmapped GLPI fallback |
| NOC | tenant event stream + watermark | noc.read | no stale watermark READY |
| Twin | immutable Twin read snapshot | twin.read + explicit mode | no simulation or engine calls |
| Runs/timeline | immutable run event projection | runs.read + run_id/mode/incident_id | reject mismatched tuple |
| Evidence | evidence index + content ACL | evidence.read + verified tuple | no raw object URI |
| Policy/HITL | immutable decision audit view | policy.read | no approvals or mutations |
| Prometheus/Grafana | allowlisted query adapter | observability.read + tenant label mapping | no arbitrary PromQL proxy |
| GLPI | read-only connector + approved entity mapping | cmdb.read | no ticket/entity writes |
| Copilot | stored explanation + authorized evidence references | copilot.read + referenced ACL | no tool execution |

For list APIs use `limit` 1..100 (default 50), opaque authenticated cursor bound to tenant, actor scope version, family, normalized filters, sort, snapshot watermark and expiry. Stable order: source observation time plus immutable ID; reject expired/tampered/foreign cursors rather than silently restarting. All list counts and facets obey the same row/object ACL. Do not claim total counts when the source cannot guarantee them.

## Request lifecycle

Server adapter deadline <= 5 seconds (proposal, subject to source review); upstream deadline shorter, bounded safe retries only. Propagate cancellation to upstream and prevent any late response promotion. Client accepts a result only when generation, authenticated tenant context, filter hash and verified run tuple equal the current request. Discard stale generation responses even if they arrive with READY. Cache key includes tenant scope, ACL version, family, filters and snapshot; invalidate on ACL change.

Run-scoped endpoints require all three `run_id`, `mode`, `incident_id` and an authoritative immutable association. Missing => 400 before source access. Mismatch => 400 only when safe to reveal, otherwise tenant-safe 404; never infer the missing value.

## Negative acceptance suite — implement against actual adapters

| Case | Expected HTTP / state | Critical spy assertion |
|---|---|---|
| unauthenticated | 401 | zero upstream reads |
| authenticated, capability absent | 403 | zero upstream reads |
| forged tenant/actor headers | session tenant enforced | zero foreign records |
| foreign object, list, count, facet | 403/404 | zero foreign disclosure |
| cursor tampered, foreign, expired, changed filter or ACL | 400/403 | no page fallback |
| missing run_id/mode/incident_id | 400 | zero upstream reads |
| inconsistent run tuple | 400/404 | zero evidence/timeline disclosure |
| timeout | 504 or documented gateway error + ERROR | no READY, data null |
| cancellation | aborted/499 | upstream cancellation observed |
| generation n after n+1 | n discarded | current UI unchanged |
| stale/future/missing observation timestamp | UNKNOWN | data null |
| missing provenance or partial page | UNKNOWN/ERROR | no invented count |
| unqualified GLPI/Prometheus/Copilot | 403/BLOCKED | no permissive fallback |
| healthy Docker + absent business health | UNKNOWN | never READY |

Use synthetic fixtures only. Tests must verify HTTP status, schema, authorization-before-read call ordering, cache isolation, no sensitive log output and cancellation signal. No live GLPI, DB or Policy/HITL writes.

## Debian collector separation and coordinator gate

Host output schema namespace: `aiops2.host_observation.v1`; it MUST NOT be serialized as `aiops2.read.v0.2` or used to infer incident/service health. Docker rootless aiops UID 1001, systemd user, cron count, versions, CPU/RAM/disk and reviewed health endpoints are host observations. Events/logs remain UNKNOWN unless a reviewed allowlist and expurgation prove safe; never collect environment dumps, volume contents, tokens or customer payloads. Preserve UNKNOWN for command failure/timeout and incomplete Docker inventories.

Review existing `scripts/observability/debian_rootless_readonly.py` at pinned SHA before installation: UID, secure directory parents, symlink/TOCTOU, flock, command timeout, JSON UTC, 0600, retention, exit codes, Docker identifiers and log redaction. Coordinator-only proposed command after review:

```bash
python3 -m unittest discover -s tests/observability -p 'test_debian_rootless*.py' -v
# proposed aiops (UID 1001) crontab line; replace absolute paths after review:
# */15 * * * * /usr/bin/timeout -k 5s 120s /usr/bin/python3 /ABSOLUTE/REVIEWED/scripts/observability/debian_rootless_readonly.py
```

No host inspection or installation is claimed here. No Core/Worker/Twin changes, DB/GLPI writes, Policy/HITL modifications, LIVE remediation, merge or deployment.
