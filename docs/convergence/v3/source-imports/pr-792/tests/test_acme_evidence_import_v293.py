import importlib.util
import unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"tools/import_acme_telemetry_v293.py"
spec=importlib.util.spec_from_file_location("acme_import",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ROW={"timestamp":"2026-10-21T10:00:00+00:00","scope":"ACME","synthetic":True,
     "kind":"metric","ci_id":"ACME-STO-PURE01","correlation_id":"ACME-DEMO-20261021",
     "scenario":"SAN_FABRIC_A_DEGRADATION","metric":"storage_latency_ms","value":20}
class ImportTests(unittest.TestCase):
    def test_bounded_synthetic_envelope(self):
        a=m.prepare([ROW])[0]
        self.assertEqual(a["provenance"]["scope"],"ACME")
        self.assertTrue(a["provenance"]["synthetic"])
        self.assertEqual(a["provenance"]["record_type"],"synthetic_telemetry")
        self.assertTrue(a["external_id"].startswith("SIM-"))
    def test_stable_identity(self):
        self.assertEqual(m.prepare([ROW]),m.prepare([dict(ROW)]))
    def test_cross_tenant_refused(self):
        for row in [dict(ROW,scope="OTHER"),dict(ROW,synthetic=False),
                    dict(ROW,ci_id="OTHER-STO-1")]:
            with self.assertRaises(ValueError):m.prepare([row])
    def test_duplicate_in_file_refused(self):
        with self.assertRaises(ValueError):m.prepare([ROW,ROW])
if __name__=="__main__":unittest.main()
