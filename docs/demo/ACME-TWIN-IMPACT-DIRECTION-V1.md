# ACME Twin impact — directed dependency contract (v1 additive)

Source: `db/migrations/003_seed_twin.sql`, `005_seed_acme.sql`, `app/twin/main.py` on main `793a5a03688dcb7c1a689d07e31bea770da4bd4f`.
The seed declares 25 nodes and 23 directed edges (7/6 + 18/17); this is a **repository seed**, not an authenticated snapshot of the Debian Twin.

## Root-only diagnosis

The stored relation direction is **consumer `source_id` → dependency `target_id`**:
`ACME-STO-PURE01 → ACME-SAN-FABRIC-A` (`ACME-E08`),
`ACME-VM-PAY01 → ACME-STO-PURE01` (`ACME-E06`),
`ACME-APP-ORACLEPAY → ACME-VM-PAY01` (`ACME-E04`),
`ACME-SVC-PAYMENTS → ACME-APP-ORACLEPAY` (`ACME-E02`),
`ACME-BIZ-PAYMENTS → ACME-SVC-PAYMENTS` (`ACME-E01`).
The former query traversed `e.source_id=d.id` then `e.target_id`: starting from a SAN dependency, it only found the root. The fix traverses **reverse** edges, `e.target_id=d.id` → `e.source_id`, restricted to the five existing dependency relation types, depth ≤ 8, deduplicated by minimum depth and stable ordering.

## Read-only API

`GET /api/twin/impact/{node_id}` requires `Authorization: Bearer <AIOPS_ADMIN_TOKEN>` (existing Twin CI/runtime secret). Missing/invalid auth → HTTP 401 without topology; unknown root → HTTP 404. No new writes, no production secrets, no LIVE actions. This is internal service authentication, **not tenant-scoped RBAC**; `tenant_acl_qualified=false`. Do not proxy this graph to tenant users until server-side tenant ACLs are implemented.

Additive fields preserve `root` and `affected` (node_id/type/name/criticality/depth). Example, shortened:
```json
{
  "root": "ACME-SAN-FABRIC-A",
  "affected": [
    {"node_id":"ACME-SAN-FABRIC-A","type":"SAN","name":"FABRIC-A","criticality":5,"depth":0},
    {"node_id":"ACME-STO-PURE01","type":"STORAGE","name":"PURE-PAY-01","criticality":5,"depth":1}
  ],
  "traversal_direction": "REVERSE_CONSUMER_TO_DEPENDENCY",
  "affected_semantics": "DEPENDENT_CANDIDATES_NOT_CONFIRMED_IMPACT",
  "max_depth": 8,
  "runtime_impact_state": "UNKNOWN",
  "runtime_authenticated": false,
  "redundancy_evaluated": false,
  "tenant_acl_qualified": false,
  "live_remediation_authorized": false,
  "provenance": "TWIN_DB_TOPOLOGY_READ_ONLY"
}
```
The sample omits eight other seeded dependent candidates; it is not a runtime observation. In the seeded graph the reverse traversal reaches `ACME-SVC-PAYMENTS` (depth 4) and `ACME-BIZ-PAYMENTS` (depth 5), but does **not** prove degraded Payments. SAN-B remains an independent sibling path; failover/redundancy is **not evaluated**. There is **no** edge from SAN/storage to host: `ACME-VM-PAY01 → ACME-SRV-RHEL01` is a separate dependency, so a strict SAN→host→VM chain cannot be asserted from these seeds. Do not add that edge without an authenticated CMDB source, or a clearly isolated synthetic fixture.

## Tests and boundaries

The existing `quality.yml` Core/PostgreSQL integration job now applies the two real seed migrations and starts a **real Twin HTTP Docker container** against ephemeral PostgreSQL 16. Tests cover exact 25/23 topology, reverse reachability, deterministic depths, no invented host/fabric/portal links, missing auth and unknown root. No mock or CI-only replacement of Twin. No claim of tenant A/B isolation, real Debian Twin, runtime degradation, Core/GLPI/Temporal correlation or E2E Payments outage. No deployment or migrations outside ephemeral CI.
