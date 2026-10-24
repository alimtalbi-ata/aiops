"""Regression contract: Chromium evidence must be admitted before derived files.

The raw PNG gate accepts exactly three PNGs plus manifest.json. Once the
index/trace is written into the artifact directory it intentionally rejects
extra files. CI must validate the raw set first, not the augmented bundle.
"""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/star-offline-chromium-real-render.yml"


class ChromiumEvidenceWorkflowContract(unittest.TestCase):
    def test_raw_admission_precedes_derived_bundle(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        commands = [line.strip() for line in source.splitlines()
                    if line.strip().startswith("python -c ")]
        def find(needle):
            matches = [i for i, line in enumerate(commands) if needle in line]
            self.assertEqual(len(matches), 1, f"expected one CI command for {needle}")
            return matches[0]
        gate = find("from demo.noc_browser_evidence_gate import verify_noc_offline_browser_evidence")
        index = find("from demo.noc_evidence_index import build_noc_evidence_index")
        map_step = find("from demo.noc_star_cue_map import bind_noc_evidence_to_star")
        center = find("from demo.noc_evidence_center import render_noc_evidence_center")
        self.assertLess(gate, index)
        self.assertLess(index, map_step)
        self.assertLess(map_step, center)
        self.assertIn("python -m demo.noc_star_trace_bundle", source)
        self.assertLess(source.index("build_noc_evidence_index(p)"),
                        source.index("python -m demo.noc_star_trace_bundle"))
        self.assertLess(source.index("test_noc_unified_chromium.py"),
                        source.index("verify_noc_offline_browser_evidence"))

    def test_ci_has_no_runtime_target_or_live_promotion(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("10.79.94.202", source)
        self.assertNotIn("AIOPS_STAR_ALLOW_OPERATOR_READ", source)
        self.assertIn("noc-offline-browser-evidence", source)
        self.assertIn("retention-days: 7", source)


if __name__ == "__main__":
    unittest.main()
