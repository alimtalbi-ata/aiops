#!/usr/bin/env python3
"""Regression: the history series guard must be executable JS, not comment text."""
from pathlib import Path
import re
import unittest

PATCH = Path(__file__).with_name("fs1097_patch.py")


class HistoryFilterCommentTest(unittest.TestCase):
    def test_invalid_series_guard_is_not_swallowed_by_comment(self):
        source = PATCH.read_text(encoding="utf-8")
        start = source.index("const series=data.series.filter(s=>{")
        end = source.index("}).slice(0,30);", start)
        block = source[start:end]
        guard = "if(!s||!Array.isArray(s.points)||!s.points.some(historyValidPoint))return false;"
        self.assertIn(guard, block)
        # The guard must be on its own line, not inside a // comment containing
        # the two literal characters backslash and n.
        lines = block.splitlines()
        matches = [line for line in lines if guard in line]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].strip().startswith("if("), matches[0])
        self.assertFalse(any("\\n" in line for line in lines if "//" in line))
        self.assertIn("if(!s.job&&!s.instance)return true;", block)


if __name__ == "__main__":
    unittest.main()
