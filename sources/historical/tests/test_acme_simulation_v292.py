import importlib.util
import unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"tools/generate_acme_telemetry_v291.py"
spec=importlib.util.spec_from_file_location("acme_sim",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class ACMESimulationTests(unittest.TestCase):
    def test_temporal_correlation_and_scope(self):
        rows=m.generate(20261021,12)
        self.assertEqual(len(rows),75)
        self.assertTrue(all(x["scope"]=="ACME" and x["synthetic"] is True for x in rows))
        self.assertEqual(len({x["correlation_id"] for x in rows}),1)
        self.assertEqual({x["kind"] for x in rows},{"metric","trace","log"})
    def test_fabric_independence_and_multipath(self):
        rows=m.generate(20261021,12)
        a=[x["value"] for x in rows if x.get("ci_id")=="ACME-SAN-FABRIC-A" and x["kind"]=="metric"]
        b=[x["value"] for x in rows if x.get("ci_id")=="ACME-SAN-FABRIC-B" and x["kind"]=="metric"]
        paths=[x["value"] for x in rows if x.get("metric")=="multipath_active_paths"]
        self.assertTrue(all(v<=2 for v in a[:5]))
        self.assertTrue(all(v>=25 for v in a[5:]))
        self.assertTrue(all(v<=1 for v in b))
        self.assertEqual(paths,[4]*5+[3]*7)
    def test_reproducibility(self):
        self.assertEqual(m.generate(20261021,12),m.generate(20261021,12))
if __name__=="__main__":unittest.main()
