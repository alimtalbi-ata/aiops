BEGIN;
INSERT INTO aiops.incidents(incident_id,external_id,title,severity,state,opened_at,source,synthetic,payload)
VALUES ('INC-CI-CONTEXT','CI-CONTEXT','Synthetic latency regression','P1','OPEN',now(),'poc-kit',true,'{}')
ON CONFLICT (incident_id) DO NOTHING;
INSERT INTO aiops.runs(run_id,incident_id,mode,scenario_id,status,idempotency_key)
VALUES ('RUN-CI-CONTEXT','INC-CI-CONTEXT','DEMO','CI-CONTEXT','CREATED','ci-context')
ON CONFLICT (run_id) DO NOTHING;
INSERT INTO aiops.twin_nodes(node_id,type,name) VALUES
('NODE-CI-ROOT','service','Synthetic application'),('NODE-CI-CHILD','service','Synthetic dependency')
ON CONFLICT (node_id) DO NOTHING;
INSERT INTO aiops.twin_edges(edge_id,source_id,target_id,relation_type,confidence)
VALUES ('EDGE-CI-01','NODE-CI-ROOT','NODE-CI-CHILD','depends',1)
ON CONFLICT (edge_id) DO NOTHING;
COMMIT;
