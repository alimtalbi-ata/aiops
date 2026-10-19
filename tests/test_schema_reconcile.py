import tempfile
import unittest
from pathlib import Path

from tools.schema_reconcile import compare, read_inventory, read_legacy


class SchemaReconcileTests(unittest.TestCase):
    def test_name_overlap_is_classified_without_claiming_compatibility(self):
        report = compare(
            {"incidents", "cmdb_objects", "legacy_only"},
            {"aiops.incidents", "aiops.cmdb_objects", "n8n.workflow", "aiops.shared"},
            {"aiops.events", "aiops.incidents", "aiops.shared"},
        )
        by_name = {row["table"]: row for row in report["rows"]}
        self.assertEqual(by_name["incidents"]["classification"], "name-match-all-three")
        self.assertEqual(by_name["cmdb_objects"]["classification"], "legacy-and-v1-name-match")
        self.assertEqual(by_name["events"]["classification"], "v2-only-name")
        self.assertEqual(by_name["legacy_only"]["classification"], "legacy-only-name")
        self.assertEqual(by_name["shared"]["classification"], "v1-and-v2-name-match")
        self.assertEqual(report["method"], "table-name-only")
        self.assertIn("not proof", report["warning"])

    def test_inventory_parser_requires_schema_and_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.txt"
            path.write_text("aiops|incidents\n", encoding="utf-8")
            self.assertEqual(read_inventory(path), {"aiops.incidents"})
            path.write_text("bad-line\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_inventory(path)

    def test_legacy_parser_ignores_comments_and_blanks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.txt"
            path.write_text("# comment\nincidents\n\nincidents\n", encoding="utf-8")
            self.assertEqual(read_legacy(path), {"incidents"})


if __name__ == "__main__":
    unittest.main()
