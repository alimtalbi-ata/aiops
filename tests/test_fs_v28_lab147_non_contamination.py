"""FS147 source-only contract: Twin SAN is excluded, legacy V28 receipt cannot authorize lab147.

No Debian/GLPI/Temporal calls, no mutations. A new run-bound detection contract
must replace the V28-specific receipt before the lab147 path can be enabled.
"""
import ast
from pathlib import Path
import unittest

WORKER = Path(__file__).resolve().parents[1] / "app/worker/main.py"
OLD_RUN = "RUN-4FABD1786F107E51"
OLD_EVIDENCE = "EVD-D2069BA816126499"
SAN_NODE = "ACME-SAN-FABRIC-A"


class FS147IsolationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(WORKER.read_text(encoding="utf-8"))
        cls.fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                      and n.name == "_execute_stage_blocking")
        cls.fs = next(n for n in ast.walk(cls.fn) if isinstance(n, ast.If)
                      and "scenario == FS_V28_SCENARIO" in ast.unparse(n.test))
        validator = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                         and n.name == "validate_fs_v28_observation")
        scope = {"FS_V28_EVIDENCE_ID": OLD_EVIDENCE}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[validator], type_ignores=[])),
                     str(WORKER), "exec"), scope)
        cls.validate = staticmethod(scope["validate_fs_v28_observation"])

    def test_filesystem_observe_has_no_san_write(self):
        calls = [n for stmt in self.fs.body for n in ast.walk(stmt)
                 if isinstance(n, ast.Call)]
        names = [n.func.id for n in calls if isinstance(n.func, ast.Name)]
        self.assertEqual(names.count("get_json"), 1)
        self.assertEqual(names.count("validate_fs_v28_observation"), 1)
        self.assertFalse({"post_json", "put_json", "delete_json"} & set(names))
        self.assertNotIn(SAN_NODE, " ".join(ast.unparse(n) for n in self.fs.body))
        self.assertEqual(len(self.fs.orelse), 1)
        self.assertIsInstance(self.fs.orelse[0], ast.If)

    def test_old_v28_receipt_does_not_authorize_new_lab147_run(self):
        old_receipt = {
            "evidence_id": OLD_EVIDENCE, "source": "filesystem-detector",
            "claim": "Filesystem usage high", "payload_hash": "sha256-test",
            "provenance": {"run_id": OLD_RUN},
            "payload": {"filesystem": "/fs-lab", "used_percent": 92},
        }
        with self.assertRaisesRegex(RuntimeError, "fs_v28_evidence_run_mismatch"):
            self.validate(old_receipt, "RUN-LAB147-NEW")

    def test_san_receipt_cannot_be_reused_for_filesystem(self):
        receipt = {
            "evidence_id": OLD_EVIDENCE, "source": "twin-simulator",
            "claim": "SAN", "payload_hash": "sha256-test",
            "provenance": {"run_id": OLD_RUN},
            "payload": {"node_id": SAN_NODE},
        }
        with self.assertRaisesRegex(RuntimeError, "fs_v28_evidence_not_independent"):
            self.validate(receipt, OLD_RUN)


if __name__ == "__main__":
    unittest.main()
