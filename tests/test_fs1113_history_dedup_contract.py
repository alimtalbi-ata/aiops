"""Verify the FS1113 browser payload deduplication contract without Docker.

Run: python -m unittest discover -s tests -p test_fs1113_history_dedup_contract.py -v
"""
import pathlib
import re
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "scripts/fs/fs1097_patch.py"


class HistoryDedupContract(unittest.TestCase):
    def test_stale_response_guard_before_render(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("if(requestId!==historyRequestId)return;", source)
        self.assertIn("signal:controller.signal", source)
        self.assertIn("legend.replaceChildren()", source)

    def test_series_deduplicated_before_chart_and_legend(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("const seenTargets=new Set()", source)
        self.assertIn("JSON.stringify([s.job??null,s.instance??null])", source)
        self.assertIn("if(seenTargets.has(key))return false", source)
        self.assertLess(source.index("const series=data.series.filter"), source.index("series.forEach((s,index)=>"))


if __name__ == "__main__":
    unittest.main()
