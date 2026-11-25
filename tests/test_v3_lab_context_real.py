import os
import sys
import unittest
from pathlib import Path
import psycopg
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"v3-spike"/"vertical"))
from lab_context import context

class LabContextReal(unittest.TestCase):
    def test_real_context(self):
        with psycopg.connect(os.environ["DATABASE_URL"]) as c:
            c.execute("insert into aiops.twin_nodes(node_id,type,name) values ('NODE-CI-ROOT','service','CI root'),('NODE-CI-CHILD','service','CI child')")
            c.execute("insert into aiops.twin_edges(edge_id,source_id,target_id,relation_type,confidence) values ('EDGE-CI-01','NODE-CI-ROOT','NODE-CI-CHILD','depends',1)")
        try:
            response=requests.post("http://127.0.0.1:1815/api/evidence",json={"source":"ci-lab","claim":"synthetic observation","confidence":0.5,"provenance":{"run_id":"RUN-CI-CONTEXT","synthetic":True},"payload":{"metric":"latency","value":42}},timeout=5)
            response.raise_for_status()
            result=context(1814,1815,"RUN-CI-CONTEXT","NODE-CI-ROOT")
            self.assertEqual({x["node_id"] for x in result["affected"]},{"NODE-CI-ROOT","NODE-CI-CHILD"})
            self.assertEqual(result["evidence"][0]["evidence_id"],response.json()["evidence_id"])
            self.assertEqual(result["rca"],"UNKNOWN")
            self.assertEqual(result["policy"],"DENY")
        finally:
            with psycopg.connect(os.environ["DATABASE_URL"]) as c:
                c.execute("delete from aiops.evidence where provenance->>'run_id'='RUN-CI-CONTEXT'")
                c.execute("delete from aiops.twin_edges where edge_id='EDGE-CI-01'")
                c.execute("delete from aiops.twin_nodes where node_id in ('NODE-CI-ROOT','NODE-CI-CHILD')")
