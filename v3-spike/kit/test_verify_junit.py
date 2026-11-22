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


    def identity(self, names, classname="ExampleTests"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "test_example.py"
            source.write_text("import unittest\nclass ExampleTests(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n")
            cases = "".join(f'<testcase classname="{classname}" name="{name}"/>' for name in names)
            (root / "receipt.xml").write_text(f'<testsuite tests="2" failures="0" errors="0" skipped="0">{cases}</testsuite>')
            return verify(root, 2, source=source)

    def test_identity_valid(self):
        self.assertEqual(self.identity(["test_a", "test_b"]), 2)

    def test_identity_duplicate(self):
        with self.assertRaises(ValueError):
            self.identity(["test_a", "test_a"])

    def test_identity_substitution(self):
        with self.assertRaises(ValueError):
            self.identity(["test_a", "test_x"])

    def test_identity_wrong_class(self):
        with self.assertRaises(ValueError):
            self.identity(["test_a", "test_b"], "WrongTests")

    def test_manifest_sha_and_xml_digest(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "test_x.py"
            source.write_text("class T:\n def test_a(self): pass\n")
            reports = root / "reports"
            reports.mkdir()
            (reports / "x.xml").write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="T" name="test_a"/></testsuite>')
            manifest = root / "manifest.json"
            self.assertEqual(verify(reports, 1, source, "a"*40, "product-bom-static", manifest), 1)
            data = json.loads(manifest.read_text())
            self.assertEqual(data["sha"], "a"*40)
            self.assertEqual(data["job"], "product-bom-static")
            self.assertIn("x.xml", data["xml_sha256"])

    def test_manifest_rejects_invalid_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "test_x.py"
            source.write_text("class T:\n def test_a(self): pass\n")
            (root / "x.xml").write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="T" name="test_a"/></testsuite>')
            with self.assertRaises(ValueError):
                verify(root, 1, source, "bad", "job", root / "manifest.json")

if __name__ == "__main__":
    unittest.main()
