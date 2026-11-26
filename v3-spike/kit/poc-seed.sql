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

-- E1 fictional enterprise: persistent canonical Twin nodes, not live customer data.
INSERT INTO aiops.twin_nodes(node_id,type,name,site) VALUES
('NODE-CI-ENT-COMPANY','enterprise','ACME enterprise (fictional)',NULL),
('NODE-CI-ENT-SITE-PAR','site','Paris office','PAR'),
('NODE-CI-ENT-SITE-LYO','site','Lyon office','LYO'),
('NODE-CI-ENT-INFRA-PAR','infrastructure','Paris compute and network','PAR'),
('NODE-CI-ENT-INFRA-LYO','infrastructure','Lyon compute and network','LYO'),
('NODE-CI-ENT-ASSET-PAR','asset','Paris application host','PAR'),
('NODE-CI-ENT-ASSET-LYO','asset','Lyon application host','LYO'),
('NODE-CI-ENT-APP-PAY','application','Payments','PAR'),
('NODE-CI-ENT-APP-CRM','application','Customer CRM','PAR'),
('NODE-CI-ENT-APP-HR','application','HR portal','LYO'),
('NODE-CI-ENT-GROUP-FIN','user_group','Finance','PAR'),
('NODE-CI-ENT-GROUP-SALES','user_group','Sales','PAR'),
('NODE-CI-ENT-GROUP-HR','user_group','Human resources','LYO'),
('NODE-CI-ENT-USER-FIN-01','user','Synthetic finance user 01','PAR'),
('NODE-CI-ENT-USER-FIN-02','user','Synthetic finance user 02','PAR'),
('NODE-CI-ENT-USER-SALES-01','user','Synthetic sales user 01','PAR'),
('NODE-CI-ENT-USER-HR-01','user','Synthetic HR user 01','LYO'),
('NODE-CI-ENT-USER-DIRECT-01','user','Synthetic direct payments user 01','LYO')
ON CONFLICT (node_id) DO NOTHING;
INSERT INTO aiops.twin_edges(edge_id,source_id,target_id,relation_type,confidence) VALUES
('EDGE-CI-ENT-01','NODE-CI-ENT-COMPANY','NODE-CI-ENT-SITE-PAR','contains',1),
('EDGE-CI-ENT-02','NODE-CI-ENT-COMPANY','NODE-CI-ENT-SITE-LYO','contains',1),
('EDGE-CI-ENT-03','NODE-CI-ENT-SITE-PAR','NODE-CI-ENT-INFRA-PAR','contains',1),
('EDGE-CI-ENT-04','NODE-CI-ENT-SITE-LYO','NODE-CI-ENT-INFRA-LYO','contains',1),
('EDGE-CI-ENT-05','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-ASSET-PAR','contains',1),
('EDGE-CI-ENT-06','NODE-CI-ENT-INFRA-LYO','NODE-CI-ENT-ASSET-LYO','contains',1),
('EDGE-CI-ENT-07','NODE-CI-ENT-ASSET-PAR','NODE-CI-ROOT','hosts',1),
('EDGE-CI-ENT-08','NODE-CI-ENT-APP-PAY','NODE-CI-ROOT','depends_on',1),
('EDGE-CI-ENT-09','NODE-CI-ENT-APP-CRM','NODE-CI-ROOT','depends_on',1),
('EDGE-CI-ENT-10','NODE-CI-ENT-APP-HR','NODE-CI-ENT-ASSET-LYO','depends_on',1),
('EDGE-CI-ENT-11','NODE-CI-ENT-GROUP-FIN','NODE-CI-ENT-APP-PAY','uses',1),
('EDGE-CI-ENT-12','NODE-CI-ENT-GROUP-SALES','NODE-CI-ENT-APP-CRM','uses',1),
('EDGE-CI-ENT-13','NODE-CI-ENT-GROUP-HR','NODE-CI-ENT-APP-HR','uses',1),
('EDGE-CI-ENT-14','NODE-CI-ENT-USER-FIN-01','NODE-CI-ENT-GROUP-FIN','member_of',1),
('EDGE-CI-ENT-15','NODE-CI-ENT-USER-FIN-02','NODE-CI-ENT-GROUP-FIN','member_of',1),
('EDGE-CI-ENT-16','NODE-CI-ENT-USER-SALES-01','NODE-CI-ENT-GROUP-SALES','member_of',1),
('EDGE-CI-ENT-17','NODE-CI-ENT-USER-HR-01','NODE-CI-ENT-GROUP-HR','member_of',1),
('EDGE-CI-ENT-18','NODE-CI-ENT-USER-DIRECT-01','NODE-CI-ENT-APP-PAY','uses',1)
ON CONFLICT (edge_id) DO NOTHING;
COMMIT;
