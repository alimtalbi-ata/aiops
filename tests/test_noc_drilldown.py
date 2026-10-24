import json
import unittest
from pathlib import Path
from demo.noc_synthetic_snapshot import build_noc_snapshot
from demo.noc_drilldown import build_noc_drilldown
CAT=Path(__file__).resolve().parents[1]/"demo/rag_ops_fixture_catalog.json"
class NocDrilldownTests(unittest.TestCase):
    def data(self):return json.loads(CAT.read_text(encoding="utf-8"))
    def test_drilldown_contains_rag_and_dependencies(self):
        data=self.data();result=build_noc_drilldown(build_noc_snapshot(data),data)
        b=result["assets"]["brocade-fc01"]
        self.assertEqual(b["downstream"],["flasharray-01"])
        self.assertEqual(b["diagnostics"][0]["doc_id"],"SYN-FOS-FC-CRC-001")
        self.assertFalse(result["cmdb_verified"])
        self.assertFalse(result["live_remediation_authorized"])
    def test_missing_rag_evidence_is_rejected(self):
        data=self.data();snapshot=build_noc_snapshot(data)
        snapshot["alerts"].pop()
        with self.assertRaises(ValueError):build_noc_drilldown(snapshot,data)
    def test_cross_asset_event_is_rejected(self):
        data=self.data();snapshot=build_noc_snapshot(data)
        snapshot["alerts"][0]["asset_id"]="mds-fc02"
        with self.assertRaises(ValueError):build_noc_drilldown(snapshot,data)
    def test_orphan_alert_asset_is_rejected_not_silently_dropped(self):
        data=self.data();snapshot=build_noc_snapshot(data)
        snapshot["alerts"][0]["asset_id"]="unknown-asset-999"
        with self.assertRaisesRegex(ValueError,"absent from synthetic dependency topology"):
            build_noc_drilldown(snapshot,data)
if __name__=="__main__":unittest.main()
