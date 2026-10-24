import copy
import json
import unittest
from pathlib import Path
from demo.validate_rag_ops_fixtures import validate_catalog

ROOT = Path(__file__).resolve().parents[1]
class TestSyntheticRAGCatalog(unittest.TestCase):
    def data(self):
        return json.loads((ROOT / "demo/rag_ops_fixture_catalog.json").read_text(encoding="utf-8"))
    def test_six_labeled_multivendor_cases(self):
        self.assertEqual(validate_catalog(self.data()), 6)
    def test_forged_official_source_is_rejected(self):
        data=self.data()
        data["scenarios"][0]["source_type"]="VENDOR_OFFICIAL"
        with self.assertRaises(ValueError):
            validate_catalog(data)
    def test_unmarked_log_is_rejected(self):
        data=self.data()
        data["scenarios"][0]["sample"]="switch error"
        with self.assertRaises(ValueError):
            validate_catalog(data)
    def test_duplicate_case_is_rejected(self):
        data=self.data()
        data["scenarios"].append(copy.deepcopy(data["scenarios"][0]))
        with self.assertRaises(ValueError):
            validate_catalog(data)

if __name__=="__main__":unittest.main()
