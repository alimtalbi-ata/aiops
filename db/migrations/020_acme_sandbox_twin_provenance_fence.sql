-- RG-ACME-019-REPLAY: additive, read-only qualification fence for migration 019.
-- Migration 019 is immutable and ON CONFLICT DO NOTHING deliberately preserves rows.
-- Therefore its original post-insert check does not reject pre-existing rows with
-- a correct ID/type but a foreign name, criticality, confidence or redundancy.
-- This follow-on check rejects those collisions without rewriting any Twin row.
-- Re-running 020 is safe. This is NOT a runtime lock, Run binding or LIVE proof.
DO $acme$
BEGIN
  IF (SELECT count(*) FROM aiops.twin_nodes
      WHERE node_id LIKE 'ACME-TEST-%' OR site = 'ACME-TEST-SIMULATION') <> 9 THEN
    RAISE EXCEPTION 'acme_sandbox_twin_node_provenance_conflict';
  END IF;

  IF EXISTS (
    SELECT 1 FROM (VALUES
      ('ACME-TEST-SAN-ARRAY-DELL-01','SIMULATED_SAN_ARRAY','ACME-TEST Dell SAN array',5),
      ('ACME-TEST-SAN-ARRAY-PURE-01','SIMULATED_SAN_ARRAY','ACME-TEST Pure SAN array',5),
      ('ACME-TEST-SAN-FABRIC-A','SIMULATED_FC_FABRIC','ACME-TEST FC fabric A',5),
      ('ACME-TEST-SAN-FABRIC-B','SIMULATED_FC_FABRIC','ACME-TEST FC fabric B',5),
      ('ACME-TEST-HOST-RHEL-MPATH-01','SIMULATED_RHEL_MULTIPATH','ACME-TEST RHEL multipath host',5),
      ('ACME-TEST-SVC-PAYMENTS','SIMULATED_BUSINESS_SERVICE','ACME-TEST payments service',5),
      ('ACME-TEST-SVC-ERP','SIMULATED_BUSINESS_SERVICE','ACME-TEST ERP service',4),
      ('ACME-TEST-SAN-REPLICATION-01','SIMULATED_REPLICATION','ACME-TEST replication target',3),
      ('ACME-TEST-SAN-BACKUP-01','SIMULATED_BACKUP','ACME-TEST backup target',3)
    ) AS expected(node_id,node_type,node_name,criticality)
    LEFT JOIN aiops.twin_nodes n ON n.node_id = expected.node_id
    WHERE n.node_id IS NULL
       OR n.type IS DISTINCT FROM expected.node_type
       OR n.name IS DISTINCT FROM expected.node_name
       OR n.site IS DISTINCT FROM 'ACME-TEST-SIMULATION'
       OR n.state IS DISTINCT FROM 'SIMULATED'
       OR n.criticality IS DISTINCT FROM expected.criticality
       OR n.confidence IS DISTINCT FROM 1::numeric
       OR n.valid_from IS NULL OR n.valid_to IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'acme_sandbox_twin_node_provenance_conflict';
  END IF;

  IF (SELECT count(*) FROM aiops.twin_edges
      WHERE edge_id LIKE 'ACME-TEST-%'
         OR source_id LIKE 'ACME-TEST-%'
         OR target_id LIKE 'ACME-TEST-%') <> 8 THEN
    RAISE EXCEPTION 'acme_sandbox_twin_edge_provenance_conflict';
  END IF;

  IF EXISTS (
    SELECT 1 FROM (VALUES
      ('ACME-TEST-SIM-EDGE-001','ACME-TEST-SAN-ARRAY-DELL-01','ACME-TEST-SAN-FABRIC-A','SIMULATED_FC_PATH'),
      ('ACME-TEST-SIM-EDGE-002','ACME-TEST-SAN-ARRAY-PURE-01','ACME-TEST-SAN-FABRIC-B','SIMULATED_FC_PATH'),
      ('ACME-TEST-SIM-EDGE-003','ACME-TEST-SAN-FABRIC-A','ACME-TEST-HOST-RHEL-MPATH-01','SIMULATED_FC_PATH'),
      ('ACME-TEST-SIM-EDGE-004','ACME-TEST-SAN-FABRIC-B','ACME-TEST-HOST-RHEL-MPATH-01','SIMULATED_FC_PATH'),
      ('ACME-TEST-SIM-EDGE-005','ACME-TEST-HOST-RHEL-MPATH-01','ACME-TEST-SVC-PAYMENTS','SIMULATED_DEPENDS_ON'),
      ('ACME-TEST-SIM-EDGE-006','ACME-TEST-HOST-RHEL-MPATH-01','ACME-TEST-SVC-ERP','SIMULATED_DEPENDS_ON'),
      ('ACME-TEST-SIM-EDGE-007','ACME-TEST-SAN-ARRAY-DELL-01','ACME-TEST-SAN-REPLICATION-01','SIMULATED_REPLICATION'),
      ('ACME-TEST-SIM-EDGE-008','ACME-TEST-SAN-ARRAY-PURE-01','ACME-TEST-SAN-BACKUP-01','SIMULATED_BACKUP')
    ) AS expected(edge_id,source_id,target_id,relation_type)
    LEFT JOIN aiops.twin_edges e ON e.edge_id = expected.edge_id
    WHERE e.edge_id IS NULL
       OR e.source_id IS DISTINCT FROM expected.source_id
       OR e.target_id IS DISTINCT FROM expected.target_id
       OR e.relation_type IS DISTINCT FROM expected.relation_type
       OR e.redundancy IS DISTINCT FROM 1
       OR e.confidence IS DISTINCT FROM 1::numeric
       OR e.valid_from IS NULL OR e.valid_to IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'acme_sandbox_twin_edge_provenance_conflict';
  END IF;
END
$acme$;
