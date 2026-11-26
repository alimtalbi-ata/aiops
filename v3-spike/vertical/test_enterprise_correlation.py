import unittest
from enterprise_context import P,ROOT,LYON
from enterprise_correlation import preview
from test_enterprise_context import graph

def row(ident,root,at,app=None,user=None,group=None):
    e={"asset_id":P+"ASSET-PAR" if root==ROOT else root,"occurred_at":at}
    for k,v in (("application_id",app),("user_id",user),("group_id",group)):
        if v:e[k]=P+v
    return {"id":ident,"kind":"metric","source":"lab-monitor","resource":root,"tenant":"synthetic-demo","severity":"critical","synthetic":True,"enterprise":e}

T="2026-01-01T09:00:00Z"
class TemporalCorrelationTest(unittest.TestCase):
    def setUp(self):self.graph=graph()
    def test_separated_recurrence_and_boundary(self):
        a=row("wan1",P+"WAN",T)
        b=row("wan2",P+"WAN","2026-01-01T09:02:00Z")
        c=row("wan3",P+"WAN","2026-01-01T09:02:01Z")
        d=row("wan4",P+"WAN","2026-01-15T09:00:00Z")
        result=preview([d,b,a,c,a],self.graph)
        self.assertEqual([g["event_count"] for g in result["groups"]],[2,1,1])
        self.assertEqual(result["unique"],4)
        self.assertEqual(result["groups"],preview([a,b,c,d],self.graph)["groups"])
        self.assertEqual(len(preview([a,d],self.graph)["groups"]),2)
        self.assertNotEqual(result["groups"][0]["candidate_group_id"],result["groups"][-1]["candidate_group_id"])
        self.assertEqual(len(preview([a,b],self.graph,119)["groups"]),2)
        self.assertFalse(result["incidents_created"])
    def test_explicit_topology_and_no_automatic_merge(self):
        a=row("wan",P+"WAN",T)
        b=row("lyon",P+"NET-LYO","2026-01-01T09:00:01Z")
        result=preview([b,a],self.graph)
        self.assertEqual(len(result["groups"]),2)
        self.assertEqual(result["candidate_count"],1)
        link=result["candidates"][0]
        self.assertEqual((link["dependent_resource"],link["dependency_resource"]),(P+"NET-LYO",P+"WAN"))
        self.assertEqual(link["gap_seconds"],1)
        self.assertEqual(link["path"],[{"source_id":P+"NET-LYO","target_id":P+"WAN","relation_type":"requires"}])
        self.assertFalse(result["causality_established"])
        self.assertEqual(result["operational_decision"],"DENY")
        self.assertEqual(preview([a,dict(b,enterprise=dict(b["enterprise"],occurred_at="2026-01-01T09:02:01Z"))],self.graph)["candidate_count"],0)
        self.assertEqual(preview([row("pay",P+"DB-PAY",T),row("hr",P+"DB-HR",T)],self.graph)["candidate_count"],0)
    def test_scope_and_undated(self):
        a=row("fin1",ROOT,T,"APP-PAY","USER-FIN-01","GROUP-FIN")
        b=row("fin2",ROOT,T,"APP-PAY","USER-FIN-02","GROUP-FIN")
        result=preview([a,b],self.graph)
        self.assertEqual(len(result["groups"]),2)
        old={k:v for k,v in a.items() if k!="enterprise"}
        result=preview([old],self.graph)
        self.assertEqual(result["groups"],[])
        self.assertEqual(result["undated"][0]["state"],"TIMESTAMP_UNAVAILABLE")
        for bad in (dict(a,tenant="foreign"),dict(a,enterprise=dict(a["enterprise"],user_id=P+"USER-HR-01")),dict(a,enterprise=dict(a["enterprise"],occurred_at="unknown"))):
            with self.assertRaises(ValueError):preview([bad],self.graph)
        with self.assertRaises(ValueError):preview([a,dict(a,severity="warning")],self.graph)
        for window in (True,0,3601):
            with self.assertRaises(ValueError):preview([a],self.graph,window)
if __name__=="__main__":unittest.main()
