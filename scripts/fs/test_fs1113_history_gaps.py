#!/usr/bin/env python3
"""Regression: missing Prometheus samples must not be drawn as continuous observations."""
import ast
import pathlib
import subprocess
import unittest

PATCH = pathlib.Path(__file__).with_name("fs1097_patch.py")


class HistoryGapsTest(unittest.TestCase):
    def test_invalid_samples_break_svg_path(self):
        tree = ast.parse(PATCH.read_text(encoding="utf-8"))
        js = next(ast.literal_eval(node.value) for node in tree.body
                  if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "js_add"
                          for target in node.targets))
        start = js.index("function historyValidPoint(")
        end = js.index("async function loadHistory()", start)
        functions = js[start:end]
        test = """
const assert=require('node:assert/strict');
const x=v=>Number(v),y=v=>Number(v);
assert.equal(historySegmentedPath([[1,1],[2,2],null,[4,4],[5,5]],x,y),
             'M1.00 1.00 L2.00 2.00 M4.00 4.00 L5.00 5.00');
assert.equal(historySegmentedPath([[1,0],[2,''],[3,0]],x,y),
             'M1.00 0.00 M3.00 0.00');
assert.equal(historySegmentedPath([[1,null],[2,'NaN']],x,y),'');
assert.equal(historySegmentedPath([[1,1],[2,2]],x,y),
             'M1.00 1.00 L2.00 2.00');
"""
        result = subprocess.run(["node", "-e", functions + test],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
