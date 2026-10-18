insert into aiops.twin_nodes(node_id,type,name,site,state,criticality,health,confidence) values
('ACME-BIZ-PAYMENTS','BUSINESS','ACME Payments','PARIS','HEALTHY',5,.99,.98),
('ACME-SVC-PAYMENTS','SERVICE','Payment Processing','PARIS','HEALTHY',5,.99,.98),
('ACME-SVC-IDENTITY','SERVICE','Identity & Access','PARIS','HEALTHY',5,.995,.99),
('ACME-APP-ORACLEPAY','APPLICATION','Oracle Payments','PARIS','HEALTHY',5,.99,.98),
('ACME-APP-PORTAL','APPLICATION','Customer Payment Portal','PARIS','HEALTHY',5,.99,.98),
('ACME-VM-PAY01','VM','PAY-VM-01','PARIS','HEALTHY',5,.99,.98),
('ACME-VM-PAY02','VM','PAY-VM-02','PARIS','HEALTHY',5,.99,.98),
('ACME-SRV-RHEL01','SERVER','RHEL-PAY-01','PARIS','HEALTHY',5,.99,.98),
('ACME-SRV-RHEL02','SERVER','RHEL-PAY-02','PARIS','HEALTHY',5,.99,.98),
('ACME-STO-PURE01','STORAGE','PURE-PAY-01','PARIS','HEALTHY',5,.99,.98),
('ACME-STO-POWERMAX01','STORAGE','POWERMAX-PAY-01','PARIS','HEALTHY',5,.99,.97),
('ACME-SAN-FABRIC-A','SAN','FABRIC-A','PARIS','HEALTHY',5,.99,.98),
('ACME-SAN-FABRIC-B','SAN','FABRIC-B','PARIS','HEALTHY',5,.99,.98),
('ACME-NET-CORE-A','NETWORK','CORE-SW-A','PARIS','HEALTHY',4,.99,.98),
('ACME-NET-CORE-B','NETWORK','CORE-SW-B','PARIS','HEALTHY',4,.99,.98),
('ACME-NAS-01','NAS','NAS-PROD-01','PARIS','HEALTHY',4,.99,.97),
('ACME-APP-ERP','APPLICATION','Oracle ERP','PARIS','HEALTHY',5,.995,.98),
('ACME-SVC-ERP','SERVICE','ERP Business Service','PARIS','HEALTHY',5,.995,.98)
on conflict(node_id) do update set state=excluded.state,health=excluded.health,confidence=excluded.confidence;
insert into aiops.twin_edges(edge_id,source_id,target_id,relation_type,redundancy,confidence) values
('ACME-E01','ACME-BIZ-PAYMENTS','ACME-SVC-PAYMENTS','USES',1,.98),
('ACME-E02','ACME-SVC-PAYMENTS','ACME-APP-ORACLEPAY','DEPENDS_ON',1,.98),
('ACME-E03','ACME-SVC-PAYMENTS','ACME-APP-PORTAL','DEPENDS_ON',1,.97),
('ACME-E04','ACME-APP-ORACLEPAY','ACME-VM-PAY01','RUNS_ON',1,.98),
('ACME-E05','ACME-APP-ORACLEPAY','ACME-VM-PAY02','RUNS_ON',1,.98),
('ACME-E06','ACME-VM-PAY01','ACME-STO-PURE01','USES',2,.97),
('ACME-E07','ACME-VM-PAY02','ACME-STO-PURE01','USES',2,.97),
('ACME-E08','ACME-STO-PURE01','ACME-SAN-FABRIC-A','PATH',1,.98),
('ACME-E09','ACME-STO-PURE01','ACME-SAN-FABRIC-B','PATH',1,.98),
('ACME-E10','ACME-VM-PAY01','ACME-SRV-RHEL01','HOSTED_ON',1,.98),
('ACME-E11','ACME-VM-PAY02','ACME-SRV-RHEL02','HOSTED_ON',1,.98),
('ACME-E12','ACME-APP-PORTAL','ACME-NET-CORE-A','USES',2,.97),
('ACME-E13','ACME-APP-PORTAL','ACME-NET-CORE-B','USES',2,.97),
('ACME-E14','ACME-SVC-ERP','ACME-APP-ERP','DEPENDS_ON',1,.98),
('ACME-E15','ACME-APP-ERP','ACME-STO-POWERMAX01','USES',2,.96),
('ACME-E16','ACME-STO-POWERMAX01','ACME-SAN-FABRIC-A','PATH',1,.97),
('ACME-E17','ACME-STO-POWERMAX01','ACME-SAN-FABRIC-B','PATH',1,.97)
on conflict(source_id,target_id,relation_type) do nothing;
insert into aiops.scenarios(scenario_id,name,seed,synthetic,description) values
('SCN-GOLDEN-PAYMENT-P1','Golden Payment SAN degradation',20261018,true,'P1 with one SAN fabric degraded, redundancy preserves service but creates risk.'),
('SCN-STORAGE-CAPACITY-P2','Storage capacity pressure',20261019,true,'P2 capacity threshold with forecasted exhaustion and change correlation.'),
('SCN-ORACLE-LATENCY-P1','Oracle payment latency',20261020,true,'P1 application latency with storage and host evidence.'),
('SCN-ESX-FC-P1','ESX FC port failure',20261021,true,'P1 FC failure with alternate path analysis.');
insert into aiops.scenario_steps(scenario_id,step_no,at_seconds,action,target_node_id,payload) values
('SCN-GOLDEN-PAYMENT-P1',1,0,'INCIDENT_OPEN','ACME-SVC-PAYMENTS','{"severity":"P1","title":"Payment latency following FC fabric degradation"}'),
('SCN-GOLDEN-PAYMENT-P1',2,15,'SET_STATE','ACME-SAN-FABRIC-A','{"state":"DEGRADED","health":0.42}'),
('SCN-GOLDEN-PAYMENT-P1',3,30,'OBSERVE','ACME-SAN-FABRIC-A','{"metric":"fc_errors","value":184,"unit":"errors/min","status":"CRITICAL"}'),
('SCN-GOLDEN-PAYMENT-P1',4,45,'CHANGE_LOOKUP','ACME-SAN-FABRIC-A','{"window_minutes":60}'),
('SCN-GOLDEN-PAYMENT-P1',5,60,'POLICY_CHECK','ACME-SVC-PAYMENTS','{"requested_action":"HUMAN_APPROVAL"}'),
('SCN-GOLDEN-PAYMENT-P1',6,90,'VERIFY','ACME-SVC-PAYMENTS','{"latency_ms":92,"status":"OK"}'),
('SCN-GOLDEN-PAYMENT-P1',7,110,'RECONCILE','ACME-SAN-FABRIC-A','{"state":"DEGRADED","residual_risk":0.31}') on conflict(scenario_id,step_no) do update set at_seconds=excluded.at_seconds,action=excluded.action,target_node_id=excluded.target_node_id,payload=excluded.payload;
