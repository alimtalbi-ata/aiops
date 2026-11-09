#!/usr/bin/env python3
"""Regression: reject null/blank Prometheus points instead of plotting false zeroes.

Runs the exact helper embedded in the FS1097 patch using Node.js; no live calls.
"""
import pathlib
import re
import subprocess
import unittest

PATCH = pathlib.Path(__file__).with_name("fs1097_patch.py")

class HistoryPointValidation(unittest.TestCase):
    def test_history_points(self):
        source = PATCH.read_text(encoding="utf-8")
        match = re.search(r'function historyValidPoint\(p\)\{[^\n]+\}', source)
        self.assertIsNotNone(match, "chart point validator missing")
        self.assertIn("series.flatMap(s=>s.points).filter(historyValidPoint)", source)
        self.assertIn("s.points.filter(historyValidPoint)", source)
        js = match.group(0) + """
const cases = [
 [[1700000000,"0.75"],true],
 [[1700000000,0],true],
 [[1700000000,null],false],
 [[null,"1"],false],
 [[1700000000,""],false],
 [[1700000000,"   "],false],
 [[1700000000,"NaN"],false],
 [[1700000000,"Infinity"],false],
 [[1700000000,"2","3"],false]
];
for (const [point,expected] of cases) {
 if (historyValidPoint(point)!==expected) process.exit(1);
}
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == "__main__":
    unittest.main()
