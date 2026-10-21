import importlib.util
import pathlib
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("acme_offline",ROOT/"tools"/"build_acme_offline_demo.py")
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class AcmeOfflineDemoTests(unittest.TestCase):
    def test_offline_html_is_synthetic_and_self_contained(self):
        page=MODULE.build()
        self.assertIn("DEMO OFFLINE SYNTHETIC",page)
        self.assertIn("DONNÉES 100 % SYNTHÉTIQUES",page)
        self.assertIn("ACME-SAN-FABRIC-A",page)
        self.assertIn("Paiement ACME",page)
        self.assertIn('"production_qualified": false',page)
        self.assertNotIn("http://aiops2-",page)
        self.assertNotIn("api/demo",page)

    def test_fixture_consistent_and_impact_is_explicit(self):
        nodes={n["node_id"] for n in MODULE.NODES}
        self.assertEqual(len(nodes),len(MODULE.NODES))
        self.assertTrue(all(e["source_id"] in nodes and e["target_id"] in nodes for e in MODULE.EDGES))
        self.assertTrue(all(e["node_id"] in nodes for e in MODULE.IMPACT["affected"]))

if __name__=="__main__":
    unittest.main()
