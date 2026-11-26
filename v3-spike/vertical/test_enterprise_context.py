import unittest
from enterprise_context import Graph, P, ROOT, CHILD, normalize
from ingestion_demo import ingest

def graph():
    kinds={"COMPANY":"enterprise","SITE-PAR":"site","SITE-LYO":"site","INFRA-PAR":"infrastructure","INFRA-LYO":"infrastructure","ASSET-PAR":"asset","ASSET-LYO":"asset","APP-PAY":"application","APP-CRM":"application","APP-HR":"application","GROUP-FIN":"user_group","GROUP-SALES":"user_group","GROUP-HR":"user_group","USER-FIN-01":"user","USER-FIN-02":"user","USER-SALES-01":"user","USER-HR-01":"user","USER-DIRECT-01":"user"}
    nodes=[{"node_id":P+k,"type":v,"name":k,"site":None} for k,v in kinds.items()]
    nodes += [{"node_id":i,"type":"service","name":i,"site":None} for i in (ROOT,CHILD)]
    def ident(x): return x if x in (ROOT,CHILD) else P+x
    edges=[(ROOT,CHILD,"depends"),("COMPANY","SITE-PAR","contains"),("COMPANY","SITE-LYO","contains"),("SITE-PAR","INFRA-PAR","contains"),("SITE-LYO","INFRA-LYO","contains"),("INFRA-PAR","ASSET-PAR","contains"),("INFRA-LYO","ASSET-LYO","contains"),("ASSET-PAR",ROOT,"hosts"),("APP-PAY",ROOT,"depends_on"),("APP-CRM",ROOT,"depends_on"),("APP-HR","ASSET-LYO","depends_on"),("GROUP-FIN","APP-PAY","uses"),("GROUP-SALES","APP-CRM","uses"),("GROUP-HR","APP-HR","uses"),("USER-FIN-01","GROUP-FIN","member_of"),("USER-FIN-02","GROUP-FIN","member_of"),("USER-SALES-01","GROUP-SALES","member_of"),("USER-HR-01","GROUP-HR","member_of"),("USER-DIRECT-01","APP-PAY","uses")]
    return Graph({"nodes":nodes,"edges":[{"source_id":ident(a),"target_id":ident(b),"relation_type":r} for a,b,r in edges]})

class EnterpriseTest(unittest.TestCase):
    def setUp(self):
        self.graph=graph()
        self.scope={"asset_id":P+"ASSET-PAR","application_id":P+"APP-PAY","group_id":P+"GROUP-FIN","user_id":P+"USER-FIN-01","occurred_at":"2026-01-01T09:00:11Z","message":"Synthetic slow payment"}
    def test_impact_and_individual(self):
        exposure=self.graph.scope(ROOT)
        self.assertEqual(exposure["applications"],{P+"APP-PAY",P+"APP-CRM"})
        self.assertEqual(exposure["users"],{P+"USER-FIN-01",P+"USER-FIN-02",P+"USER-SALES-01",P+"USER-DIRECT-01"})
        self.graph.validate_signal(ROOT,normalize(self.scope,"log"))
        direct=dict(self.scope,user_id=P+"USER-DIRECT-01")
        direct.pop("group_id")
        self.graph.validate_signal(ROOT,normalize(direct,"log"))
        for bad in (dict(self.scope,user_id=P+"USER-HR-01"),dict(self.scope,application_id=P+"APP-CRM"),dict(self.scope,asset_id=P+"ASSET-LYO"),dict(self.scope,group_id=P+"GROUP-HR"),dict(self.scope,user_id=P+"USER-DIRECT-01")):
            with self.assertRaises(ValueError):
                self.graph.validate_signal(ROOT,normalize(bad,"log"))
    def test_independent_lyon_and_raw_samples(self):
        from enterprise_context import LYON
        scope={"asset_id":P+"ASSET-LYO","application_id":P+"APP-HR","group_id":P+"GROUP-HR","user_id":P+"USER-HR-01","occurred_at":"2026-01-01T09:00:11Z","message":"Synthetic HR request"}
        self.graph.validate_signal(LYON,normalize(scope,"log"))
        self.assertEqual(self.graph.scope(LYON)["applications"],{P+"APP-HR"})
        self.assertEqual(self.graph.scope(LYON)["users"],{P+"USER-HR-01"})
        for root,bad in ((ROOT,scope),(LYON,self.scope),(LYON,dict(scope,user_id=P+"USER-FIN-01"))):
            with self.assertRaises(ValueError):
                self.graph.validate_signal(root,normalize(bad,"log"))
        metric={"id":"measure1","kind":"metric","source":"multiasset-observed-http","resource":LYON,"severity":"critical","tenant":"synthetic-demo","synthetic":True,
                "enterprise":{"asset_id":P+"ASSET-LYO","application_id":P+"APP-HR","occurred_at":"2026-01-01T09:00:11Z","measurement":{"classification":"MEASURED_SYNTHETIC_LAB","samples_ms":[11,12,10,13,9],"method":"HTTP_MONOTONIC_MEDIAN_5"}},
                "observation":{"metric":"latency_ms","phase":"baseline","value":11}}
        signal=ingest([metric])["incidents"][0]["evidence"][0]
        self.assertEqual(signal["enterprise"]["measurement"]["samples_ms"],[11,12,10,13,9])
        with self.assertRaises(ValueError):
            ingest([dict(metric,observation=dict(metric["observation"],value=12))])
        for samples in ([11], [11,12,10,13,True], [11,12,10,13,float("nan")]):
            with self.assertRaises(ValueError):
                ingest([dict(metric,enterprise=dict(metric["enterprise"],measurement=dict(metric["enterprise"]["measurement"],samples_ms=samples)))])
    def test_ingestion_and_projection(self):
        row={"id":"ent-l1","kind":"log","source":"app","resource":ROOT,"severity":"critical","tenant":"synthetic-demo","synthetic":True,"enterprise":self.scope}
        signal=ingest([row])["incidents"][0]["evidence"][0]
        self.assertEqual(signal["enterprise"],self.scope)
        changed=dict(row,enterprise=dict(self.scope,message="different"))
        self.assertNotEqual(signal["sha256"],ingest([changed])["incidents"][0]["evidence"][0]["sha256"])
        with self.assertRaises(ValueError): ingest([row,changed])
        with self.assertRaises(ValueError): ingest([dict(row,tenant="other")])
        with self.assertRaises(ValueError): normalize(dict(self.scope,occurred_at="not UTC"),"log")
        ev={"evidence_id":"E1","payload_hash":"a"*64}
        details={"root":ROOT,"run_id":"RUN-CI-E1","policy":"DENY","production_authorized":False,"evidence":[ev],"verified_signals":[{**ev,"signal":signal}]}
        run={"run_id":"RUN-CI-E1","incident_id":"INC-CI-E1"}
        result=self.graph.project(details,run)
        self.assertEqual(result["reported_user_ids"],[P+"USER-FIN-01"])
        self.assertFalse(result["observed_outage_established"])
        self.assertEqual(result["timeline"][0]["message"],self.scope["message"])
        self.assertEqual({x["id"] for x in result["document_references"]},{"ENT-DOC-001","ENT-DOC-003"})
        self.assertTrue(all(not x["observed_evidence"] for x in result["document_references"]))
        self.assertEqual(result["operational_decision"],"DENY")
        with self.assertRaises(ValueError): self.graph.project(dict(details,verified_signals=[{**ev,"payload_hash":"b"*64,"signal":signal}]),run)

if __name__=="__main__": unittest.main()
