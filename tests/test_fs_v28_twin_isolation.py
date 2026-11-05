"""Filesystem V28 regression: run-bound Evidence without SAN Twin contamination."""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "app/worker/main.py"


class FsV28Isolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        names = {"validate_fs_v28_observation", "_execute_stage_blocking"}
        cls.functions = {n.name: n for n in tree.body
                         if isinstance(n, ast.FunctionDef) and n.name in names}
        scope = {"FS_V28_EVIDENCE_ID": "EVD-D2069BA816126499"}
        code = ast.fix_missing_locations(ast.Module(
            body=[cls.functions["validate_fs_v28_observation"]], type_ignores=[]))
        exec(compile(code, str(SOURCE), "exec"), scope)
        cls.validate = staticmethod(scope["validate_fs_v28_observation"])

    def fixture(self, run="RUN-4FABD1786F107E51"):
        return {"evidence_id": "EVD-D2069BA816126499",
                "source": "filesystem-detector",
                "claim": "Filesystem detection",
                "payload_hash": "sha256-example",
                "provenance": {"run_id": run, "synthetic": True},
                "payload": {"filesystem": "/var", "metric": "usage"}}

    def test_existing_fs_evidence_is_accepted_without_twin(self):
        self.assertTrue(self.validate(self.fixture(), "RUN-4FABD1786F107E51"))

    def test_cross_run_or_san_evidence_is_rejected(self):
        mutations = [
            lambda e: e["provenance"].update(run_id="RUN-OTHER"),
            lambda e: e.update(evidence_id="EVD-OTHER"),
            lambda e: e.update(source="twin-simulator"),
            lambda e: e.update(source=""),
            lambda e: e.update(source=None),
            lambda e: e.update(source=[]),
            lambda e: e["payload"].update(node_id="ACME-SAN-FABRIC-A"),
            lambda e: e.update(payload_hash=""),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                e = self.fixture()
                mutate(e)
                with self.assertRaises(RuntimeError):
                    self.validate(e, "RUN-4FABD1786F107E51")

    def test_fs_branch_precedes_legacy_san_branch(self):
        source = ast.get_source_segment(
            SOURCE.read_text(encoding="utf-8"),
            self.functions["_execute_stage_blocking"])
        fs = "if synthetic and stage=='OBSERVE' and scenario==FS_V28_SCENARIO:"
        san = "elif synthetic and stage=='OBSERVE':"
        self.assertIn(fs, source)
        self.assertIn(san, source)
        self.assertLess(source.index(fs), source.index(san))
        self.assertIn("validate_fs_v28_observation(fs_evidence,rid)", source)


if __name__ == "__main__":
    unittest.main()
