#!/usr/bin/env python3
"""Regression: 24h history extents must handle large responses without JS spread."""
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATCH = ROOT / "scripts/fs/fs1097_patch.py"

class HistoryExtentsTest(unittest.TestCase):
    def test_large_history_extents(self):
        source = PATCH.read_text(encoding="utf-8")
        match = re.search(r"(let minT=Infinity,maxT=-Infinity,minV=Infinity,maxV=-Infinity;.*?)(?=\n  if\(minT===maxT\))", source, re.S)
        self.assertIsNotNone(match, "missing streaming history bounds")
        self.assertNotIn("...points", match.group(1))
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable; JavaScript execution not verified")
        script = """
const points = Array.from({length: 150000}, (_, i) => [i, i % 7 === 0 ? 0 : i / 10]);
""" + match.group(1) + """
if (minT !== 0 || maxT !== 149999 || minV !== 0 || maxV !== 14999.9)
  throw new Error('Incorrect bounds: ' + [minT,maxT,minV,maxV].join(','));
console.log('FS1113_LARGE_HISTORY_EXTENTS=PASS');
"""
        completed = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("FS1113_LARGE_HISTORY_EXTENTS=PASS", completed.stdout)

if __name__ == "__main__":
    unittest.main()
