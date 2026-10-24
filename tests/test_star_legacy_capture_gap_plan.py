import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
from demo.star_legacy_capture_gap_plan import build_gap_plan, main

class LegacyCaptureGapPlanTests(unittest.TestCase):
    def test_all_nine_cues_require_runtime_proof(self):
        report = {"schema":"aiops-legacy-playwright-audit-v1","entries":[
            {"application":"grafana","integrity_verified":True},
            {"application":"n8n","integrity_verified":True},
            {"application":"glpi","integrity_verified":False}]}
        plan = build_gap_plan(report, "RUN-TEST-123")
        self.assertEqual(len(plan["steps"]), 9)
        self.assertEqual(plan["missing_runtime_captures"], 9)
        self.assertEqual([x["cue"] for x in plan["steps"]], ["detect","correlate","enrich","analyze","ticket","approve","simulate","verify","close"])
        self.assertTrue(all(x["runtime_evidence_status"]=="MISSING" for x in plan["steps"]))
        self.assertFalse(plan["live_remediation_authorized"])
        self.assertEqual(plan["steps"][0]["legacy_png_byte_matches_for_application"],1)
    def test_rejects_forged_or_missing_metadata(self):
        with self.assertRaises(ValueError): build_gap_plan({"schema":"wrong","entries":[]},"RUN-123")
        with self.assertRaises(ValueError): build_gap_plan({"schema":"aiops-legacy-playwright-audit-v1","entries":[]},"../bad")
    def test_rejects_forged_business_or_runtime_proof(self):
        for key in ("runtime_authenticated", "business_state_verified", "eligible_for_star_proof"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_gap_plan({"schema":"aiops-legacy-playwright-audit-v1",
                    "entries":[{"application":"grafana", key:True}]}, "RUN-TEST-123")
    def test_rejects_invalid_attestation_types_and_unknown_application(self):
        for bad in ({"application":"grafana","integrity_verified":"true"},
                    {"application":"Grafana","integrity_verified":True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build_gap_plan({"schema":"aiops-legacy-playwright-audit-v1",
                    "entries":[bad]}, "RUN-TEST-123")
    def test_cli_exclusive_safe_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); source=d/"audit.json"; out=d/"plan.json"
            source.write_text(json.dumps({"schema":"aiops-legacy-playwright-audit-v1","entries":[]}),encoding="utf8")
            cmd=["gap",str(source),"--run-id","RUN-123","--output",str(out)]
            with patch.object(sys,"argv",cmd): main()
            self.assertEqual(json.loads(out.read_text())["missing_runtime_captures"],9)
            with patch.object(sys,"argv",cmd),self.assertRaises(FileExistsError): main()

if __name__=="__main__": unittest.main()
