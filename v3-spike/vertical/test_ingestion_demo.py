import unittest
from ingestion_demo import ingest

class IngestionTest(unittest.TestCase):
    def test_correlation(self):
        a=dict(id="m1",kind="metric",source="monitor",resource="demo-node",severity="critical",tenant="synthetic-demo",synthetic=True)
        b=dict(a,id="l1",kind="log",source="application")
        result=ingest([a,b,a])
        self.assertEqual(result["ingestion"]["unique"],2)
        self.assertEqual(len(result["incidents"]),1)
        self.assertEqual(result["incidents"][0]["alert_count"],2)
        self.assertEqual(result["incidents"][0]["rca"]["status"],"UNKNOWN")
        with self.assertRaises(ValueError):
            ingest([dict(a,synthetic=False)])
        with self.assertRaises(ValueError):
            ingest([a,dict(a,severity="warning")])

    def test_observation_integrity(self):
        a=dict(id="m1",kind="metric",source="monitor",resource="NODE-CI-ROOT",severity="critical",tenant="synthetic-demo",synthetic=True,
               observation={"metric":"latency_ms","phase":"baseline","value":40})
        b=dict(a,id="m2",observation=dict(a["observation"],phase="incident",value=160))
        evidence=ingest([a,b,a])["incidents"][0]["evidence"]
        self.assertEqual([x["observation"]["value"] for x in evidence],[40,160])
        changed=dict(a,observation=dict(a["observation"],value=41))
        self.assertNotEqual(evidence[0]["sha256"],ingest([changed])["incidents"][0]["evidence"][0]["sha256"])
        with self.assertRaises(ValueError):
            ingest([a,changed])
        for value in (True,0,-1,float("nan"),float("inf"),1e10,"40"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ingest([dict(a,observation=dict(a["observation"],value=value))])
        with self.assertRaises(ValueError):
            ingest([dict(a,kind="log")])
        with self.assertRaises(ValueError):
            ingest([dict(a,observation=dict(a["observation"],metric="unknown"))])

    def test_http(self):
        import json
        import threading
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        from http_demo import server
        a=dict(id="m1",kind="metric",source="monitor",resource="demo-node",severity="critical",tenant="synthetic-demo",synthetic=True)
        with server() as http:
            thread=threading.Thread(target=http.serve_forever,daemon=True)
            thread.start()
            origin="http://127.0.0.1:%d"%http.server_port
            def send(rows):
                return urlopen(Request(origin+"/api/v1/ingest",data=json.dumps(rows).encode(),headers={"Origin":origin,"Content-Type":"application/json"}),timeout=5)
            try:
                with send([a,dict(a,id="l1",kind="log")]) as response:
                    result=json.load(response)
                    self.assertEqual(result["incidents"][0]["alert_count"],2)
                with self.assertRaises(HTTPError) as err:
                    send([dict(a,synthetic=False)])
                self.assertEqual(err.exception.code,503)
            finally:
                http.shutdown()
                thread.join(5)
