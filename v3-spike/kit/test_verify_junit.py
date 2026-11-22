"""Synthetic JUnit mutations; no host or Docker access."""
import tempfile
import unittest
from pathlib import Path
from verify_junit import verify


class JUnitIntegrityTests(unittest.TestCase):
    def check(self, xml, expected=1):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "receipt.xml").write_text(xml, encoding="utf-8")
            return verify(Path(tmp), expected)

    def test_valid(self):
        self.assertEqual(self.check('<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="ok"/></testsuite>'), 1)

    def test_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                verify(Path(tmp), 1)

    def test_empty(self):
        with self.assertRaises(ValueError):
            self.check("")

    def test_malformed(self):
        with self.assertRaises(ValueError):
            self.check("<testsuite")

    def test_counter_lie(self):
        with self.assertRaises(ValueError):
            self.check('<testsuite tests="2" failures="0" errors="0" skipped="0"><testcase name="ok"/></testsuite>')

    def test_failure(self):
        with self.assertRaises(ValueError):
            self.check('<testsuite tests="1" failures="1" errors="0" skipped="0"><testcase name="bad"><failure/></testcase></testsuite>')

    def test_skipped(self):
        with self.assertRaises(ValueError):
            self.check('<testsuite tests="1" failures="0" errors="0" skipped="1"><testcase name="skip"><skipped/></testcase></testsuite>')

    def test_missing_counter(self):
        with self.assertRaises(ValueError):
            self.check('<testsuite tests="1" failures="0" errors="0"><testcase name="ok"/></testsuite>')


if __name__ == "__main__":
    unittest.main()
