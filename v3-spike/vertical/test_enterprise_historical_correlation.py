import unittest
from enterprise_context import P
from enterprise_historical_correlation import historical_preview,reconstruct
from ingestion_demo import ingest
from test_enterprise_context import graph
from test_enterprise_correlation import row,T

A="RUN-"+"A"*16
B="RUN-"+"B"*16
def fixture(rid,raw,eid):
    signal=ingest([raw])["incidents"][0]["evidence"][0]
    ref={"evidence_id":eid,"payload_hash":"a"*64}
    return ({"run":{"run_id":rid,"mode":"DEMO","incident_id":"INC-CI-INGEST-"+rid[-1].lower()*32}},
            {"run_id":rid,"root":raw["resource"],"classification":"SYNTHETIC_LAB_CONTEXT",
             "production_authorized":False,"evidence":[ref],"verified_signals":[{**ref,"signal":signal}]})

class HistoricalCorrelationTest(unittest.TestCase):
    def setUp(self):
        self.raw_a=row("wan",P+"WAN",T)
        self.raw_b=row("lyon",P+"NET-LYO","2026-01-01T09:00:01Z")
        self.runs={A:fixture(A,self.raw_a,"E1"),B:fixture(B,self.raw_b,"E2")}
    def result(self,ids=None):return historical_preview(ids or [A,B],120,graph(),self.runs.__getitem__)
    def test_exact_sources_and_order(self):
        d=self.result()
        self.assertEqual(d,self.result([B,A]))
        self.assertEqual(d["candidate_count"],1)
        self.assertEqual(d["verified_evidence_count"],2)
        refs=[r for g in d["groups"] for s in g["signals"] for r in s["evidence_refs"]]
        self.assertEqual({(r["run_id"],r["evidence_id"]) for r in refs},{(A,"E1"),(B,"E2")})
        self.assertFalse(d["incidents_created"])
    def test_hash_reproduction_and_bad_runs(self):
        sig=self.runs[A][1]["verified_signals"][0]["signal"]
        self.assertEqual(reconstruct(sig,self.raw_a["resource"]),self.raw_a)
        with self.assertRaises(ValueError):reconstruct(dict(sig,sha256="0"*64),self.raw_a["resource"])
        for ids in ([A,A],[A],["foreign",B]):
            with self.assertRaises(ValueError):self.result(ids)
        self.runs[B][0]["run"]["mode"]="LIVE"
        with self.assertRaises(ValueError):self.result()
    def test_duplicate_signal_keeps_provenance(self):
        self.runs[B]=fixture(B,self.raw_a,"E2")
        d=self.result()
        self.assertEqual(d["unique"],1)
        self.assertEqual(len(d["groups"][0]["signals"][0]["evidence_refs"]),2)
        self.assertFalse(d["groups"][0]["independent_sources_verified"])
if __name__=="__main__":unittest.main()
