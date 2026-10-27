import copy
import json
import unittest
from pathlib import Path
from demo.noc_synthetic_snapshot import build_noc_snapshot
SOURCE=Path(__file__).resolve().parents[1]/"demo/rag_ops_fixture_catalog.json"
class NocSnapshotTests(unittest.TestCase):
    def catalog(self):return json.loads(SOURCE.read_text(encoding="utf-8"))
    def test_deterministic_state_and_business_impact(self):
        first=build_noc_snapshot(self.catalog())
        self.assertEqual(first,build_noc_snapshot(self.catalog()))
        self.assertEqual(first["totals"],{"hosts":6,"services":1,"alerts":6})
        self.assertEqual(first["business_services"]["ACME Payments"]["state"],"CRIT")
        self.assertFalse(first["runtime_authenticated"])
        self.assertFalse(first["checkmk_live"])
        self.assertFalse(first["thruk_live"])
    def test_unknown_event_fails_closed(self):
        c=self.catalog();c["scenarios"][0]["event_key"]="DEMO_UNREVIEWED"
        with self.assertRaises(ValueError):build_noc_snapshot(c)
    def test_vendor_authority_forgery_fails(self):
        c=self.catalog();c["scenarios"][0]["source_type"]="VENDOR_OFFICIAL"
        with self.assertRaises(ValueError):build_noc_snapshot(c)
    def test_untrusted_run_id_fails(self):
        with self.assertRaises(ValueError):build_noc_snapshot(self.catalog(),"../escape")
if __name__=="__main__":unittest.main()
