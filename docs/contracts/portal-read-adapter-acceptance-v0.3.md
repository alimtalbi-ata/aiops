# AIOPS2 — tenant-safe read adapter acceptance harness v0.3

Status: **PROPOSAL / NOT EXECUTED / NOT QUALIFIED**. Extends read envelope v0.2 and its JSON Schema. This is an executable-test *specification*, not evidence that any deployed adapter passes.

## Adapter contract and instrumentation

The test harness MUST invoke the real HTTP adapter under test with a synthetic authenticated principal resolved by the server (not a caller-provided `X-Tenant` header). Inject a read-only spy source, spy cache and cancellable fake upstream. Capture calls **after** the authentication and authorization middleware. Assert that unauthorized requests never invoke source, cache lookup or external connector; a cache hit is a read and must not precede authorization. Include authorization version in cache keys and invalidate on scope changes.

Test principals: `A` in tenant `T1` with `incidents.read`, `B` in `T2` with the same capability, `C` in `T1` without that capability. Synthetic records `i1` owned by T1 and `i2` owned by T2. These labels are fixtures, not actual customer identifiers.

## Required test vectors (all synthetic)

| ID | Request / injection | Expected assertion |
|---|---|---|
| AUTH-01 | no authenticated principal, valid object ID | HTTP 401; source/cache/external spy calls = 0 |
| AUTH-02 | C reads i1 | HTTP 403; source/cache/external spy calls = 0 |
| TEN-01 | A supplies forged T2 actor/tenant headers | server still uses T1; no T2 source/cache access |
| TEN-02 | A requests i2 directly | tenant-safe 404 or 403, no i2 body/metadata/timing oracle |
| TEN-03 | A requests list, count and facets with both tenants seeded | only T1 data, counts and facets; no T2 cache key |
| CACHE-01 | warm T1 cache; request with B in T2 | no T1 cached result; tenant and ACL version in key |
| CACHE-02 | revoke A's capability after warm cache | HTTP 403 before cache access |
| PAGE-01 | change one byte in signed cursor | HTTP 400; no implicit first-page fallback |
| PAGE-02 | replay cursor across tenant, ACL version, family, filter, sort or expired snapshot | reject, never reuse or restart |
| RUN-01 | omit each of run_id, mode, incident_id independently | HTTP 400 before source read |
| RUN-02 | cross-associate an existing run_id with different mode or incident_id | 400 or tenant-safe 404; no timeline/evidence |
| TIME-01 | upstream exceeds configured deadline | documented 504/ERROR boundary; no READY or partial data |
| CANCEL-01 | abort while upstream pending | upstream signal aborted; no late cache write or READY |
| GEN-01 | response for generation n arrives after n+1 | n discarded; current UI and cache unchanged |
| FRESH-01 | missing/future/expired observed_at, absent watermark or provenance | UNKNOWN with data=null, never zero/empty READY |
| PART-01 | truncated page, inconsistent source counts or invalid cursor | UNKNOWN/ERROR; data=null and no false total |
| HOST-01 | healthy rootless Docker but no business source | business dashboard UNKNOWN, not READY |
| SOURCE-01 | GLPI/Prometheus/Copilot source lacks tenant mapping | BLOCKED/403, no arbitrary query fallback |

All assertions include correlation ID, sanitized logs, source-call ordering, cancellation propagation, and absence of foreign tenant identifiers in error bodies. Run across dashboard/health, incidents, services/CMDB, NOC, Twin, Runs/timeline, Evidence, Policy/HITL, Prometheus/Grafana, GLPI and Copilot with family-specific capabilities and sources. Do not treat schema validation as authorization evidence.

## Response classification and freshness

401 = no verified authentication; 403 = verified principal lacks capability or mapped scope. 404 is permitted to conceal foreign records. 400 = malformed or incomplete tuple/cursor, provided this does not leak foreign existence. UNKNOWN = unavailable, unverified, stale, incomplete observation. ERROR = confirmed adapter/upstream protocol failure. BLOCKED = known policy or access restriction, but never a cosmetic HTTP 200 substitute for a required 403. Cancellation is abort/499, not an empty success.

`observed_at` is the authoritative source time; `collected_at` is ingest time; `snapshot_watermark` establishes consistency. A source-specific freshness budget must be declared and clock skew bounded. An UNKNOWN response carries `data:null`, never an invented 0, empty list or fabricated timestamp.

## Debian host boundary / coordinator gate

`aiops2.host_observation.v1` is independent from `aiops2.read.v0.2`. Do not promote host CPU, memory, Docker health, systemd counts or cron counts to tenant incident/service health. Existing Debian collector requires review at a pinned SHA: UID 1001 rootless context, parent directory ownership and TOCTOU, O_NOFOLLOW lock and flock, timeout, JSON UTC timestamp, 0600 output, retention, identifier allowlist and log redaction. Health endpoints and events/logs must remain UNKNOWN until explicitly allowlisted and privacy-reviewed.

Coordinator-only validation before cron installation:

```bash
python3 -m unittest discover -s tests/observability -p 'test_debian_rootless*.py' -v
id -u aiops # must equal 1001; review effective rootless Docker context
# inspect and approve absolute script/output paths, parent owners, permissions and retention
# only after review, as aiops UID 1001:
# */15 * * * * /usr/bin/timeout -k 5s 120s /usr/bin/python3 /ABSOLUTE/REVIEWED/scripts/observability/debian_rootless_readonly.py
```

No installation, server inspection, executable adapter test or CI success is claimed. No Core/Worker/Twin, GLPI/DB writes, Policy/HITL changes or LIVE remediation. Coordinator must rebase the stacked Draft PR onto the approved integration branch before merge.
