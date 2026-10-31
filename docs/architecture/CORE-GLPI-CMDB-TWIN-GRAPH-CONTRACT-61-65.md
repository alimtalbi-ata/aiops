# GLPI CMDB -> Twin graph contract v1 (#61, #65)

**2026-10-31; status: OFFLINE CONTRACT / SYNTHETIC ONLY / NOT INSTALLED / NO_GO.** No GLPI or production DB writes.

## Existing systems reused

- GLPI is authoritative for tickets, CI/assets, entities and source relations. Existing #192 read-only client supports GET initSession, GET Ticket/{id}, GET search/Ticket and GET killSession with App-Token/session. It does **not** yet implement authenticated enterprise CI import, source entity ACL or ticket-Run verification.
- Core owns Incident/Run and authoritative ticket cross-reference. #205 implements GET /api/tenants/{tenant_id}/itsm/glpi/{instance_id}/tickets/{ticket_id}/xref with dedicated service Bearer, server actor/tenant ACL, permission itsm:xref:read, signed append-only provenance and Core Run->Incident join. #203 remains open: no trusted live GLPI adapter/ingestion/read-back. RUN-* text never yields LINKED.
- Evidence is append-only. Twin is a projection, **not** a second CMDB. Main Twin already exposes GET /api/twin/summary, /nodes, /graph, /impact/{node_id}, /at; existing 003 and 005 seeds define 7+18=25 CIs and 6+17=23 edges. The current Twin runtime graph is not a versioned tenant-scoped GLPI import.

## Proposed versioned projection (no runtime route or migration added)

Schema: **aiops.glpi-cmdb-twin-graph.v1**. Stable CI key is a scoped digest of (tenant, GLPI instance, itemtype, GLPI source ID); edge key is scoped digest of (tenant, instance, source CI, target CI, relation type). Preserve exact GLPI source identifiers, entity, source_event_id, actor, provenance, confidence, observed_at, known_at, valid_from/to, version, last_seen, lifecycle, environment, criticality, owner/support group, location, tags, serial/asset tag, OS/version, TEST-NET IP/MAC, warranty and contract. Preserve direction, temporal validity and source on edges.

Types: ENTITY, SITE, BUILDING, ROOM, RACK, DATACENTER, CLUSTER, HYPERVISOR, VM, SERVER, OS, STORAGE, SAN_FABRIC, NAS, LUN, VOLUME, SWITCH, HBA, VLAN, FIREWALL, LOAD_BALANCER, DATABASE, MIDDLEWARE, APPLICATION, API, BUSINESS_SERVICE, USER, GROUP, TEAM, SUPPLIER, CONTRACT, LICENSE, BACKUP, MONITORING, CLOUD_RESOURCE.

Relations: HOSTS, DEPENDS_ON, CONNECTS_TO, REPLICATES_TO, BACKS_UP, SUPPORTS, OWNS, LOCATED_IN, CONSUMES. Reject cycles in HOSTS/DEPENDS_ON/OWNS/LOCATED_IN; reject dangling/self/duplicate edges and duplicate source IDs, serials, asset tags and MACs. Never infer confirmed impact from a dependency path.

A separate **offline** Python contract/seed/test bundle was prepared for owner review (not committed to this PR, not wired to Twin). It normalizes GLPI-shaped synthetic snapshots, rejects duplicate JSON keys and unqualified tenant/GLPI entity ACL, computes deterministic version diff and tombstone/rollback *plans*, and returns hypothetical SAN->Payments blast paths only. Its SOURCE_READBACK status is an adapter assertion, **not** Core VERIFIED or proof of real GLPI ACL. No ticket/run/evidence binding is produced.

## Deterministic synthetic fixture and tests

Fixed UTC seed, three entities, HQ + Lyon + Lille + DR, prod/preprod/dev/dr, redundant SAN, Payments/ERP/IAM/AD, DB, network, cloud, backup and monitoring. Small **117 CI / 134 edges**, medium **213 / 230**, large **597 / 614**; all 35 CI types and nine relation types. Small relations: BACKS_UP 2, CONNECTS_TO 12, CONSUMES 8, DEPENDS_ON 28, HOSTS 16, LOCATED_IN 51, OWNS 10, REPLICATES_TO 1, SUPPORTS 6. No orphan CI in these **fixtures**, not an observed GLPI quality claim. All identifiers and network addresses are synthetic.

Local offline Python unit suite **16/16 PASS** (re-executed 2026-10-31 with `PYTHONPATH=app python -m unittest discover -s tests -p 'test_core_cmdb_twin_graph.py' -v` against the supplied v1.1 bundle): deterministic export/import, scoped IDs, cross-tenant, duplicate source/asset/MAC/IP, unauthorized GLPI entity, strict typed relation IDs, documentation-only TEST-NET IPs, stale/invalid UTC, dangling edge, forbidden cycle, graph diff/CI change/tombstone/rollback, hypothetical blast path and copied RUN text. The v1.1 normalizer and snapshots remain **outside the repository** and are not Core/Twin runtime code; no disposable GLPI/Twin/PostgreSQL import or CI qualification of this bundle has occurred.

## Integration gate and ownership

1. 1/5 Twin owner: map real GLPI itemtypes and relation APIs using authenticated GET-only adapter, server-derived entity ACL and source pagination; reuse Twin nodes/edges/facts, introduce versioned import only after schema/migration review.
2. 3/5 Core owner: preserve #205 authenticated xref and signed provenance, reject forged IDs and stale/cross-tenant data; no CI or ticket relationship becomes VERIFIED without authoritative Core read-back.
3. 5/5 integration: resolve migration 009 collision, qualify same SHA with disposable GLPI->Twin import/diff/rollback, Core xref and Evidence; reconcile CI/source ownership and secrets.
4. #65 blast radius: reverse DEPENDS_ON causal path is a **hypothesis**, not telemetry-backed outage. Confirm only with timestamped Evidence/observations.

No Portal/UI, Worker/Policy, packaging, GLPI write, production DB, SSH, sudo, deploy, merge, main push or LIVE. **RELEASE_STABLE=NO_GO.**

## 2026-10-31 17:15 — offline temporal blast-radius v1.2 (not installed)

- A separate, **uncommitted** offline v1.2 normalizer/test bundle retains schema `aiops.glpi-cmdb-twin-graph.v1` and the same deterministic source profiles (small 117 CI/134 edges, medium 213/230, large 597/614; 35 CI types/9 edge types). Local source-only tests **18/18 PASS** (up from 16/16), without GLPI/DB/network calls; its archive has a per-file SHA256 manifest and no Python bytecode. This is NOT GitHub CI coverage or an installed Twin adapter.
- New `potential_blast_radius(graph, failed_ci_id, as_of=...)` traverses only `DEPENDS_ON` edges and CIs valid at a timezone-aware UTC instant (`valid_from <= as_of < valid_to`, open-ended when null). Default `as_of` is the graph's `known_at`. An expired edge is excluded, future edges are not prematurely traversed, and naive/string `as_of` is rejected. Empty-string relation `valid_to` now fails normalization rather than being silently treated as null.
- SAN Fabric A → Payments remains **HYPOTHESIS_NOT_CONFIRMED**, never confirmed impact without independent, timestamped Evidence telemetry. GLPI ticket/CI/entity read-back, tenant/actor ACL, real import/versioned Twin runtime and rollback integration are still absent; Core #203 is the only authority for ticket↔Incident/Run and a text `RUN-*` never establishes a link.
- Core #205 independently hardened signed association-history ordering: a standalone `mapping_version=2` with no version 1 is now `CONFLICT`, no exposed IDs. [Quality 41218220600](https://github.com/alimtalbi-ata/aiops/actions/runs/41218220600) SUCCESS 3/3 on code SHA `740f75e7eeef76260704f0ae91d54a5e25c3d003` (16/16 Core HTTP, 17/17 readback contract, 8/8 disposable PG16). This does not qualify a live GLPI→Twin read-back or an integrated #201/#205 SHA.

## 2026-10-31 18:05 — offline CMDB graph v1.3 reconciliation

- A separate **offline, uncommitted** v1.3 artifact retains `aiops.glpi-cmdb-twin-graph.v1`; reproducible snapshots remain **117/134**, **213/230**, **597/614** CI/edges, 35 CI types and 9 relation types. Local pure Python **20/20 PASS**; deterministic archive SHA256 `369a0dd884dc1b1638299ecf1cdf142bf19aafe47b548b08c0e7009a81a32ab7`, 12 files with SHA256 manifest. **Not installed, not GitHub CI tested, no real GLPI/Twin import.**
- Fixed workload location/entity in medium/large seeds: workload VM/application/API/service now use HQ, Lyon, Lille or DR rather than accidental literal `SITE`; six workload VMs per site in medium, thirty per site in large. GLPI entity IDs remain synthetic 0/1/2.
- Added `source_snapshot_sha256` to normalized projection as a deterministic **content checksum only**, never an authenticated GLPI source signature. Reconciliation rejects reused `source_event_id` and reversed `known_at` across versions; CI source-ID rekeys retaining the same serial are flagged as `identity_drift` and `requires_manual_reconciliation`. Tombstones and rollback are plans, not database operations.
- Core xref #205 independently validates temporal integrity of **every** signed association-history row before `VERIFIED` ([Quality 41222836102](https://github.com/alimtalbi-ata/aiops/actions/runs/41222836102) SUCCESS 3/3, Core 17/17 HTTP, 17/17 readback, 9/9 disposable PG16). #61/#65 still require a trusted read-only GLPI entity/CI connector, tenant ACL, source pagination, versioned Twin import and rollback integration. SAN→Payments remains `HYPOTHESIS_NOT_CONFIRMED` without independent Evidence telemetry. No text-derived ticket↔Run linkage.

## 2026-10-31 19:00 Europe/Paris — offline CMDB reconciliation v1.4 (not installed)

- New separate **offline-only** bundle `offline-v1.4` (12 files, SHA256 manifest) uses unchanged schema `aiops.glpi-cmdb-twin-graph.v1`. Reproducible small/medium/large snapshots remain **117 CI/134 relations**, **213/230**, **597/614**, covering 35 CI types and 9 relation types. **24/24 local Python tests PASS**, not GitHub CI, not a runtime adapter. Archive SHA256 `542f004f47cc123eacfdd2cd8c459676d8b80f1ccacef7031ee336464c2935b2`.
- **Pagination/completeness gate:** non-synthetic normalization requires `snapshot_complete=true` after the caller's full GLPI entity-scoped read traversal. The flag is a **caller assertion, not authenticated source proof**; a real adapter must derive it from bounded, successful pagination and server-enforced entity ACL. Version diff refuses incomplete or stale incoming snapshots, preventing a partial/stale fetch from producing a misleading tombstone plan.
- **Bulk deletion risk:** a disappearance of more than 20% of previous CI IDs sets `bulk_tombstone_risk=true` and `requires_manual_reconciliation=true`; plans are never applied automatically. Mixed `HOSTS` + `LOCATED_IN` cycles now fail validation even if each individual relation type is acyclic.
- Four new negative tests cover incomplete real source traversal, incomplete/stale reconciliation, bulk tombstone review and mixed structural cycles. No GLPI write, production DB, Twin runtime import, migration, CI modification or LIVE. GLPI remains CMDB authority, Twin a projection, Core #203/#205 the only ticket↔Run xref authority; SAN→Payments remains `HYPOTHESIS_NOT_CONFIRMED` without sourced Evidence.
- Source refs rechecked at this checkpoint: #195 `ffa0d7083d9fbe0deefa90a9b5c3f560984d66e4`, #201 `230feb52f64c4480f72a33e7e7c56bb12909b2ab`, #198 `1eab448a88ca15ee7992a03d0e8bdf5f16b949a2`, #205 prior code/doc HEAD `ba97148275e26b936c8631f87839450a49cb8025`; all base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`. #203 is an issue, no Git SHA/base.
