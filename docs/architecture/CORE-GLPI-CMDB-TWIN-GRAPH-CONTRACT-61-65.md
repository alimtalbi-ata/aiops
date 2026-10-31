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

Local offline Python unit suite **13/13 PASS**: deterministic export/import, scoped IDs, cross-tenant, duplicate source/asset/MAC, unauthorized GLPI entity, stale/invalid UTC, dangling edge, forbidden cycle, graph diff/CI change/tombstone/rollback, hypothetical blast path and copied RUN text. No disposable GLPI/Twin/PostgreSQL integration or CI qualification of this new fixture has occurred.

## Integration gate and ownership

1. 1/5 Twin owner: map real GLPI itemtypes and relation APIs using authenticated GET-only adapter, server-derived entity ACL and source pagination; reuse Twin nodes/edges/facts, introduce versioned import only after schema/migration review.
2. 3/5 Core owner: preserve #205 authenticated xref and signed provenance, reject forged IDs and stale/cross-tenant data; no CI or ticket relationship becomes VERIFIED without authoritative Core read-back.
3. 5/5 integration: resolve migration 009 collision, qualify same SHA with disposable GLPI->Twin import/diff/rollback, Core xref and Evidence; reconcile CI/source ownership and secrets.
4. #65 blast radius: reverse DEPENDS_ON causal path is a **hypothesis**, not telemetry-backed outage. Confirm only with timestamped Evidence/observations.

No Portal/UI, Worker/Policy, packaging, GLPI write, production DB, SSH, sudo, deploy, merge, main push or LIVE. **RELEASE_STABLE=NO_GO.**
