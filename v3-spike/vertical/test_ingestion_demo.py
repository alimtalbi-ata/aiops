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
