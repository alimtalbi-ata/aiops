"""Offline safety regressions: python -m unittest discover -s tests -p 'test_fs_real_lineage.py'."""
import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "app/portal/fs_real_lineage.py"
spec = importlib.util.spec_from_file_location("fs_real_lineage", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class LineageSafetyTests(unittest.TestCase):
    def test_empty_receipt_never_passes(self):
        result = mod.project_lineage({})
        self.assertTrue(result["read_only"])
        self.assertEqual(result["approval"], "UNVERIFIED")
        self.assertEqual(result["resolution"], "UNVERIFIED")
        self.assertTrue(all(v["status"] == "UNKNOWN" for v in result["stages"].values()))

    def test_fs1250_visual_ticket_is_not_verified_xref(self):
        result = mod.project_lineage({"scenario": "FS1250", "run_id": "RUN-8CA56A39E58944F1",
            "stages": {"itsm": {"status": "PASS", "evidence_ref": "glpi-ui-201"}},
            "external_refs": [{"system": "GLPI", "id": 201, "verification": "UNKNOWN"}]})
        self.assertEqual(result["stages"]["itsm"]["status"], "UNKNOWN")
        self.assertEqual(result["verified_external_refs"], [])

    def test_fs147_historical_approval_does_not_transfer(self):
        result = mod.project_lineage({"scenario": "FS147",
            "stages": {"policy": {"status": "BLOCKED", "evidence_ref": "policy-receipt"}},
            "external_refs": [{"system": "GLPI", "id": 147, "verification": "VERIFIED",
                               "evidence_ref": "readback"}],
            "approval": "ACCEPTED", "resolution": "RESOLVED"})
        self.assertEqual(result["stages"]["policy"]["status"], "BLOCKED")
        self.assertEqual(result["approval"], "UNVERIFIED")
        self.assertEqual(result["resolution"], "UNVERIFIED")

    def test_pass_requires_evidence(self):
        result = mod.project_lineage({"stages": {"core": {"status": "PASS"},
                                                 "source": {"status": "PASS", "evidence_ref": "prom-1"}}})
        self.assertEqual(result["stages"]["core"]["status"], "UNKNOWN")
        self.assertEqual(result["stages"]["source"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
