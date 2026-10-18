insert into aiops.twin_nodes(node_id,type,name,site,state,criticality,health,confidence) values
('NODE-ACME-SVC-PAY','SERVICE','ACME Payment Service','PARIS','HEALTHY',5,0.99,0.98),
('NODE-ACME-APP-ORACLE','APPLICATION','Oracle Payments','PARIS','HEALTHY',5,0.99,0.98),
('NODE-ACME-VM-01','VM','PAY-VM-01','PARIS','HEALTHY',5,0.99,0.98),
('NODE-ACME-STORE-01','STORAGE','PURE-01','PARIS','HEALTHY',5,0.99,0.98),
('NODE-ACME-SAN-A','SAN','FABRIC-A','PARIS','HEALTHY',5,0.99,0.98),
('NODE-ACME-SAN-B','SAN','FABRIC-B','PARIS','HEALTHY',5,0.99,0.98),
('NODE-ACME-SRV-01','SERVER','RHEL-PAY-01','PARIS','HEALTHY',5,0.99,0.98)
on conflict(node_id) do nothing;
insert into aiops.twin_edges(edge_id,source_id,target_id,relation_type,redundancy,confidence) values
('EDGE-001','NODE-ACME-SVC-PAY','NODE-ACME-APP-ORACLE','DEPENDS_ON',1,.98),
('EDGE-002','NODE-ACME-APP-ORACLE','NODE-ACME-VM-01','RUNS_ON',1,.98),
('EDGE-003','NODE-ACME-VM-01','NODE-ACME-STORE-01','USES',2,.97),
('EDGE-004','NODE-ACME-STORE-01','NODE-ACME-SAN-A','PATH',2,.97),
('EDGE-005','NODE-ACME-STORE-01','NODE-ACME-SAN-B','PATH',2,.97),
('EDGE-006','NODE-ACME-VM-01','NODE-ACME-SRV-01','HOSTED_ON',1,.98)
on conflict(source_id,target_id,relation_type) do nothing;
