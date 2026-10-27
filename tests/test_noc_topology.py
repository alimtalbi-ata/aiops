import json
import unittest
from pathlib import Path
from demo.noc_synthetic_snapshot import build_noc_snapshot
from demo.noc_topology import build_noc_topology
from demo.noc_wallboard import render_noc_wallboard

class NocTopologyTests(unittest.TestCase):
    def state(self):
        source=Path(__file__).resolve().parents[1]/"demo/rag_ops_fixture_catalog.json"
        return build_noc_snapshot(json.loads(source.read_text(encoding="utf8")))
    def test_san_to_business_path(self):
        graph=build_noc_topology(self.state())
        self.assertEqual(len(graph["nodes"]),7)
        self.assertEqual(len(graph["edges"]),6)
        self.assertFalse(graph["cmdb_verified"])
        self.assertFalse(graph["live_discovery"])
        self.assertIn({"from":"pay-api-01","to":"ACME Payments"},graph["edges"])
    def test_wallboard_includes_dependency_links(self):
        page=render_noc_wallboard(self.state())
        self.assertIn("Topologie d’impact SAN",page)
        self.assertIn("CMDB SYNTHÉTIQUES",page)
        self.assertIn("pay-api-01 → ACME Payments",page)
    def test_forbid_forged_live_discovery(self):
        state=self.state();state["checkmk_live"]=True
        with self.assertRaises(ValueError):build_noc_topology(state)
    def test_unknown_core_asset_fails(self):
        state=self.state();del state["hosts"]["brocade-fc01"]
        with self.assertRaises(ValueError):build_noc_topology(state)

if __name__=="__main__": unittest.main()
