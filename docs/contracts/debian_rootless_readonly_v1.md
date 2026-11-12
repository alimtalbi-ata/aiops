# AIOPS2 read contracts / Debian collector — draft review

## Trust and semantics
Portal business read models (dashboard/health, incidents, services/CMDB, NOC, Twin, Runs/timeline, Evidence, Policy/HITL, Prometheus/Grafana, GLPI, Copilot) MUST use server-derived actor and tenant from validated authentication, never request body/query/browser identity. Deny missing actor/tenant (401), forbidden scope or tenant (403), and routes under TENANT_ACL_NOT_QUALIFIED (BLOCKED). Never infer READY from HTTP 2xx, a host probe, or client-provided status.

Common response envelope: `{state: READY|UNKNOWN|ERROR|BLOCKED, data: object|array|null, source: {system, resource, observed_at}, fetched_at, freshness: {max_age_seconds, stale}, error: {code, message}|null, page: {limit, next_cursor}|null}`. READY requires qualified authorization, verified provenance, valid schema and freshness; otherwise null data with explicit state. Never send secrets or raw source errors. Cursor scoped and signed to actor/tenant/filter, bounded limit. Backend timeout and cancellation, request-generation fencing, late-response discard, and no fallback to stale READY. `run_id`, `mode`, `incident_id` must be present and consistent for Runs/Evidence; reject inconsistent associations. Policy/HITL is read-only.

## Collector boundary
`scripts/observability/debian_rootless_readonly.py` emits **host telemetry**, not business model evidence. It runs only as UID 1001, uses nonblocking flock, subprocess timeouts, strict command allowlist, UTC timestamp, atomic 0600 JSON, 0700 directory and 24-file retention. It never reads container env, mounts, volumes, customer records, tokens or raw logs. Unconfigured endpoints/events/logs are UNKNOWN rather than fabricated OK. Docker metadata may still expose sensitive image names: security review required before ingestion or distribution. No external DNS; Docker socket must be rootless /run/user/1001/docker.sock. No host installation performed.

## Coordinator-only install proposal (after review)
```sh
install -d -m 700 -o aiops -g aiops /home/aiops/.local/state/aiops2-observe
install -m 700 -o aiops -g aiops scripts/observability/debian_rootless_readonly.py /home/aiops/bin/aiops2-readonly-collect
# In aiops UID 1001 crontab ONLY after approval:
*/15 * * * * /usr/bin/timeout 90s /usr/bin/python3 /home/aiops/bin/aiops2-readonly-collect >/dev/null 2>&1
```
Exit codes: 0 all sections observed (not expected while safe sources unconfigured); 2 partial/UNKNOWN; 3 unsafe identity/output directory; 4 lock held. Cron operator must monitor exit 2 separately from successful execution. The collector performs local JSON writes only, no runtime/GLPI/DB/Policy mutations.

## Negative recipe (isolated)
- 401 missing actor; 403 tenant mismatch; forged tenant header, cross-tenant pagination cursor; blocked bootstrap/components/copilot/demo.
- Absent/inconsistent run_id, mode, incident_id; malformed provenance and stale fetched_at; pagination over limit.
- Timeout, cancellation, hostile transport getter, stale generation, late success after cancellation, forged READY.
- Collector: wrong UID -> 3; lock contention -> 4; docker/socket missing -> 2 and UNKNOWN; command timeout -> UNKNOWN; output directory permissive -> 3; JSON schema and 0600 permissions; no env/log/volume/token contents; retention 24.
- Offline syntax: `python3 -m py_compile scripts/observability/debian_rootless_readonly.py`. Run only synthetic tests before host review.

## Handoff
Stacked from #665; coordinate #555 and #545. Compare integration before cherry-pick. No Core/Worker/Twin changes; no merge, Debian cron installation, deploy, GLPI/PG writes, Policy/HITL changes or live remediation. CODE draft; CI UNKNOWN; DEBIAN NOT_INSTALLED; E2E UNKNOWN; actor/tenant ACL NOT_QUALIFIED. Rollback: close Draft; on approved installation remove cron entry and collector binary after archival review.
