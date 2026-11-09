"""Offline unit fixtures are not evidence of real runtime integration."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ops.coordination.integration_evidence_gate import evaluate


VALID = {
    "source_provenance": "REAL",
    "correlation_id": "run-123",
    "core_status": "SUCCESS",
    "worker_status": "SUCCESS",
    "policy_status": "APPROVED",
    "evidence_status": "VERIFIED",
    "glpi_core_link": "LINKED",
    "itsm_readback": "VERIFIED",
}
SCRIPT = (Path(__file__).resolve().parents[1]
          / "ops/coordination/integration_evidence_gate.py")


class EvaluateTests(unittest.TestCase):
    def test_full_pass_without_mutation(self):
        receipt = copy.deepcopy(VALID)
        self.assertEqual(evaluate(receipt), {"status": "PASS", "reasons": []})
        self.assertEqual(receipt, VALID)

    def test_every_missing_gate(self):
        for field in VALID:
            with self.subTest(field=field):
                receipt = dict(VALID)
                del receipt[field]
                self.assertEqual(evaluate(receipt), {
                    "status": "HOLD", "reasons": ["MISSING_" + field.upper()]})

    def test_every_failed_or_malformed_gate(self):
        for field, valid in VALID.items():
            for value in (None, True, False, 0, 1, [], {}, "", " \t\n"):
                with self.subTest(field=field, value=value):
                    receipt = dict(VALID, **{field: value})
                    self.assertEqual(evaluate(receipt), {
                        "status": "HOLD", "reasons": ["INVALID_" + field.upper()]})
            if field != "correlation_id":
                for value in ("FAILED", "UNKNOWN", valid.lower(), valid + " "):
                    with self.subTest(field=field, value=value):
                        self.assertEqual(evaluate(dict(VALID, **{field: value})), {
                            "status": "HOLD", "reasons": ["INVALID_" + field.upper()]})

    def test_synthetic_provenance(self):
        self.assertEqual(evaluate(dict(VALID, source_provenance="SYNTHETIC")), {
            "status": "HOLD", "reasons": ["INVALID_SOURCE_PROVENANCE"]})

    def test_missing_glpi_readback_even_with_link(self):
        receipt = dict(VALID)
        del receipt["itsm_readback"]
        self.assertEqual(evaluate(receipt), {
            "status": "HOLD", "reasons": ["MISSING_ITSM_READBACK"]})

    def test_non_object_receipts(self):
        for value in (None, [], "REAL", 42, True):
            with self.subTest(value=value):
                self.assertEqual(evaluate(value), {
                    "status": "HOLD", "reasons": ["INVALID_RECEIPT"]})

    def test_all_missing_gates_reported_deterministically(self):
        result = evaluate({})
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(set(result["reasons"]), {
            "MISSING_" + field.upper() for field in VALID})
        self.assertEqual(len(result["reasons"]), len(VALID))
        self.assertEqual(result, evaluate({}))


class CliTests(unittest.TestCase):
    def run_cli(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            if content is not None:
                path.write_bytes(content)
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), str(path)],
                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout)

    def test_pass_exit_zero(self):
        self.assertEqual(self.run_cli(json.dumps(VALID).encode()),
                         (0, {"status": "PASS", "reasons": []}))

    def test_every_missing_gate_exit_two(self):
        for field in VALID:
            with self.subTest(field=field):
                receipt = dict(VALID)
                del receipt[field]
                code, result = self.run_cli(json.dumps(receipt).encode())
                self.assertEqual(code, 2)
                self.assertEqual(result, evaluate(receipt))

    def test_invalid_files_exit_two(self):
        duplicate = json.dumps(VALID)[:-1] + ', "source_provenance": "REAL"}'
        for content in (None, b"", b"{", b"\xff", b"NaN", b"Infinity",
                        duplicate.encode(), b"{" + b'"x":[' + b"[" * 1500):
            with self.subTest(content=repr(content)[:80]):
                self.assertEqual(self.run_cli(content), (2, {
                    "status": "HOLD", "reasons": ["INVALID_RECEIPT_FILE"]}))

    def test_non_objects_exit_two(self):
        for content in (b"null", b"[]", b"true", b'"REAL"', b"42"):
            with self.subTest(content=content):
                self.assertEqual(self.run_cli(content), (2, {
                    "status": "HOLD", "reasons": ["INVALID_RECEIPT"]}))

    def test_synthetic_exit_two(self):
        receipt = dict(VALID, source_provenance="SYNTHETIC")
        self.assertEqual(self.run_cli(json.dumps(receipt).encode()),
                         (2, evaluate(receipt)))


if __name__ == "__main__":
    unittest.main()
