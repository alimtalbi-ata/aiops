"""FS V28 malformed Evidence must fail closed, without SAN writes."""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "app/worker/main.py"

class MalformedEvidenceTests(unittest.TestCase):
    def test_invalid_evidence_structures_rejected(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "validate_fs_v28_observation")
        scope = {"FS_V28_EVIDENCE_ID": "EVD-D2069BA816126499"}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(SOURCE), "exec"), scope)
        validate = scope["validate_fs_v28_observation"]
        for record in (None, [], "invalid", 42, {"evidence_id": "EVD-D2069BA816126499", "provenance": [], "payload": {}}, {"evidence_id": "EVD-D2069BA816126499", "provenance": {"run_id": "RUN-4FABD1786F107E51"}, "payload": []}):
            with self.subTest(record=record), self.assertRaises(RuntimeError):
                validate(record, "RUN-4FABD1786F107E51")

if __name__ == "__main__":
    unittest.main()
