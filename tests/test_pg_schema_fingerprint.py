import unittest

from tools.compare_pg_schema_fingerprints import compare, keyed


def fingerprint(database, relations):
    return {"format_version": 1, "database": database, "relations": relations}


def relation(name, columns=None, constraints=None, indexes=None):
    return {
        "schema": "aiops",
        "name": name,
        "kind": "r",
        "columns": columns or [],
        "constraints": constraints or [],
        "indexes": indexes or [],
    }


class SchemaFingerprintTests(unittest.TestCase):
    def test_detects_identical_different_and_one_sided_relations(self):
        left = fingerprint("v1", [
            relation("same", columns=[{"name": "id", "type": "bigint"}]),
            relation("changed", columns=[{"name": "id", "type": "integer"}]),
            relation("legacy_only"),
        ])
        right = fingerprint("v2", [
            relation("same", columns=[{"name": "id", "type": "bigint"}]),
            relation("changed", columns=[{"name": "id", "type": "bigint"}]),
            relation("new_only"),
        ])
        report = compare(left, right)
        rows = {row["relation"]: row for row in report["relations"]}
        self.assertEqual(rows["aiops.same"]["status"], "identical")
        self.assertEqual(rows["aiops.changed"]["differences"], ["columns"])
        self.assertEqual(rows["aiops.legacy_only"]["status"], "left-only")
        self.assertEqual(rows["aiops.new_only"]["status"], "right-only")
        self.assertEqual(report["counts"]["identical"], 1)
        self.assertIn("does not establish", report["warning"])

    def test_rejects_duplicate_relation_keys(self):
        with self.assertRaises(ValueError):
            keyed([relation("duplicate"), relation("duplicate")])


if __name__ == "__main__":
    unittest.main()
