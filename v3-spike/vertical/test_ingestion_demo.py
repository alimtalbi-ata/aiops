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
