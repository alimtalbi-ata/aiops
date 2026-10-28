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


## Additive path provenance (stacked PR, 2026-10-28)

The same authenticated, read-only endpoint now includes `shortest_path_edges` and
`path_semantics=SEEDED_TOPOLOGY_SHORTEST_HOPS_NOT_RUNTIME_CAUSALITY`.
Each edge is read from `aiops.twin_edges` in the **same PostgreSQL read
transaction** as `affected`, and is retained only when the consumer's
minimum depth is exactly one hop beyond its dependency. Edges are sorted by
`edge_id`; no topology link is inferred or synthesized. The list may omit
longer alternative routes and **does not prove outage, failover, or causality**.

Example excerpt for SAN-A (seeded synthetic CI graph, not Debian):
```json
{
  "root": "ACME-SAN-FABRIC-A",
  "shortest_path_edges": [
    {"edge_id": "ACME-E01", "source_id": "ACME-BIZ-PAYMENTS", "target_id": "ACME-SVC-PAYMENTS", "relation_type": "USES"},
    {"edge_id": "ACME-E02", "source_id": "ACME-SVC-PAYMENTS", "target_id": "ACME-APP-ORACLEPAY", "relation_type": "DEPENDS_ON"},
    {"edge_id": "ACME-E04", "source_id": "ACME-APP-ORACLEPAY", "target_id": "ACME-VM-PAY01", "relation_type": "RUNS_ON"},
    {"edge_id": "ACME-E06", "source_id": "ACME-VM-PAY01", "target_id": "ACME-STO-PURE01", "relation_type": "USES"},
    {"edge_id": "ACME-E08", "source_id": "ACME-STO-PURE01", "target_id": "ACME-SAN-FABRIC-A", "relation_type": "PATH"}
  ],
  "path_semantics": "SEEDED_TOPOLOGY_SHORTEST_HOPS_NOT_RUNTIME_CAUSALITY",
  "runtime_impact_state": "UNKNOWN",
  "tenant_acl_qualified": false
}
```
The excerpt is **not the full response** (other shortest-hop edges are
omitted). The documented path is SAN-A → storage → VM → application → service
→ business, **not SAN → host → VM**: the actual `ACME-E10` edge is
VM → RHEL host, and no storage → host edge exists. The alternative SAN-B
edge `ACME-E09` is excluded when SAN-A is the root; redundancy remains
unqualified. Consumers may render this topology path only with a
`SIMULATED / TOPOLOGY_ONLY` label and must not treat it as an observed
Payments incident or an authenticated tenant-scoped result.
