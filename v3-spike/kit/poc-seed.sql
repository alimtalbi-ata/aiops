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

-- E4 persistent fictional technical inventory; no external assets.
INSERT INTO aiops.twin_nodes(node_id,type,name,site) VALUES
('NODE-CI-ENT-NET-PAR','network','Paris access switch','PAR'),
('NODE-CI-ENT-NET-LYO','network','Lyon access switch','LYO'),
('NODE-CI-ENT-WAN','network','Inter-site WAN','PAR'),
('NODE-CI-ENT-LINUX-PAR','compute','Linux payments runtime','PAR'),
('NODE-CI-ENT-WIN-LYO','compute','Windows HR runtime','LYO'),
('NODE-CI-ENT-DB-PAY','database','Payments PostgreSQL','PAR'),
('NODE-CI-ENT-DB-CRM','database','CRM database','PAR'),
('NODE-CI-ENT-DB-HR','database','HR database','LYO'),
('NODE-CI-ENT-STORAGE-PAR','storage','Paris storage pool','PAR'),
('NODE-CI-ENT-STORAGE-LYO','storage','Lyon storage pool','LYO'),
('NODE-CI-ENT-IDENTITY','identity','Shared enterprise directory','PAR'),
('NODE-CI-ENT-PC-FIN-01','endpoint','Finance workstation 01','PAR'),
('NODE-CI-ENT-PC-HR-01','endpoint','HR workstation 01','LYO'),
('NODE-CI-ENT-PC-SALES-01','endpoint','Sales workstation 01','PAR')
ON CONFLICT (node_id) DO NOTHING;
INSERT INTO aiops.twin_edges(edge_id,source_id,target_id,relation_type,confidence) VALUES
('EDGE-CI-TECH-01','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-NET-PAR','contains',1),
('EDGE-CI-TECH-02','NODE-CI-ENT-INFRA-LYO','NODE-CI-ENT-NET-LYO','contains',1),
('EDGE-CI-TECH-03','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-WAN','contains',1),
('EDGE-CI-TECH-04','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-LINUX-PAR','contains',1),
('EDGE-CI-TECH-05','NODE-CI-ENT-INFRA-LYO','NODE-CI-ENT-WIN-LYO','contains',1),
('EDGE-CI-TECH-06','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-DB-PAY','contains',1),
('EDGE-CI-TECH-07','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-DB-CRM','contains',1),
('EDGE-CI-TECH-08','NODE-CI-ENT-INFRA-LYO','NODE-CI-ENT-DB-HR','contains',1),
('EDGE-CI-TECH-09','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-STORAGE-PAR','contains',1),
('EDGE-CI-TECH-10','NODE-CI-ENT-INFRA-LYO','NODE-CI-ENT-STORAGE-LYO','contains',1),
('EDGE-CI-TECH-11','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-IDENTITY','contains',1),
('EDGE-CI-TECH-12','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-PC-FIN-01','contains',1),
('EDGE-CI-TECH-13','NODE-CI-ENT-INFRA-LYO','NODE-CI-ENT-PC-HR-01','contains',1),
('EDGE-CI-TECH-14','NODE-CI-ENT-INFRA-PAR','NODE-CI-ENT-PC-SALES-01','contains',1),
('EDGE-CI-TECH-15','NODE-CI-ENT-ASSET-PAR','NODE-CI-ENT-LINUX-PAR','requires',1),
('EDGE-CI-TECH-16','NODE-CI-ENT-ASSET-LYO','NODE-CI-ENT-WIN-LYO','requires',1),
('EDGE-CI-TECH-17','NODE-CI-ENT-LINUX-PAR','NODE-CI-ENT-NET-PAR','requires',1),
('EDGE-CI-TECH-18','NODE-CI-ENT-WIN-LYO','NODE-CI-ENT-NET-LYO','requires',1),
('EDGE-CI-TECH-19','NODE-CI-ENT-NET-PAR','NODE-CI-ENT-WAN','requires',1),
('EDGE-CI-TECH-20','NODE-CI-ENT-NET-LYO','NODE-CI-ENT-WAN','requires',1),
('EDGE-CI-TECH-21','NODE-CI-ENT-APP-PAY','NODE-CI-ENT-DB-PAY','requires',1),
('EDGE-CI-TECH-22','NODE-CI-ENT-APP-CRM','NODE-CI-ENT-DB-CRM','requires',1),
('EDGE-CI-TECH-23','NODE-CI-ENT-APP-HR','NODE-CI-ENT-DB-HR','requires',1),
('EDGE-CI-TECH-24','NODE-CI-ENT-DB-PAY','NODE-CI-ENT-STORAGE-PAR','requires',1),
('EDGE-CI-TECH-25','NODE-CI-ENT-DB-CRM','NODE-CI-ENT-STORAGE-PAR','requires',1),
('EDGE-CI-TECH-26','NODE-CI-ENT-DB-HR','NODE-CI-ENT-STORAGE-LYO','requires',1),
('EDGE-CI-TECH-27','NODE-CI-ENT-APP-PAY','NODE-CI-ENT-IDENTITY','requires',1),
('EDGE-CI-TECH-28','NODE-CI-ENT-APP-CRM','NODE-CI-ENT-IDENTITY','requires',1),
('EDGE-CI-TECH-29','NODE-CI-ENT-APP-HR','NODE-CI-ENT-IDENTITY','requires',1),
('EDGE-CI-TECH-30','NODE-CI-ENT-USER-FIN-01','NODE-CI-ENT-PC-FIN-01','uses_device',1),
('EDGE-CI-TECH-31','NODE-CI-ENT-USER-HR-01','NODE-CI-ENT-PC-HR-01','uses_device',1),
('EDGE-CI-TECH-32','NODE-CI-ENT-USER-SALES-01','NODE-CI-ENT-PC-SALES-01','uses_device',1)
ON CONFLICT (edge_id) DO NOTHING;
COMMIT;
