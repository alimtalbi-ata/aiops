"""Regression: ambiguous capture envelopes must fail closed before qualification."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/fs/fs147_twin_partition_gate.py"


def valid_capture():
    return {
        "graph": {"nodes": [
            {"node_id": "FS-1", "namespace": "lab-fs147"},
            {"node_id": "SAN-1", "namespace": "san"},
        ], "edges": []},
        "fs_facts": {"run_id": "RUN-FS", "synthetic": True, "facts": [
            {"fact_id": "F-FS", "node_id": "FS-1",
             "value": {"run_id": "RUN-FS", "synthetic": True, "target_node_id": "FS-1"}}
        ]},
        "san_facts": {"run_id": "RUN-SAN", "synthetic": True, "facts": [
            {"fact_id": "F-SAN", "node_id": "SAN-1",
             "value": {"run_id": "RUN-SAN", "synthetic": True, "target_node_id": "SAN-1"}}
        ]},
    }


class StrictCaptureTest(unittest.TestCase):
    def invoke(self, payload):
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "capture.json"
            capture.write_text(payload, encoding="utf-8")
            return subprocess.run([
                sys.executable, str(GATE), "--capture", str(capture),
                "--fs-namespace", "lab-fs147", "--san-namespace", "san",
                "--fs-run-id", "RUN-FS", "--san-run-id", "RUN-SAN",
            ], capture_output=True, text=True, check=False)

    def test_valid_capture_passes(self):
        result = self.invoke(json.dumps(valid_capture()))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS")

    def test_duplicate_topology_namespace_fails_closed(self):
        raw = json.dumps(valid_capture())
        raw = raw.replace('"namespace": "lab-fs147"', '"namespace": "lab-fs147", "namespace": "san"', 1)
        result = self.invoke(raw)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "HOLD")
        self.assertIn("duplicate", result.stdout)

    def test_duplicate_run_identity_fails_closed(self):
        raw = json.dumps(valid_capture())
        raw = raw.replace('"run_id": "RUN-FS"', '"run_id": "RUN-FS", "run_id": "RUN-SAN"', 1)
        result = self.invoke(raw)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("duplicate", result.stdout)

    def test_duplicate_nested_fact_provenance_fails_closed(self):
        raw = json.dumps(valid_capture())
        raw = raw.replace('"target_node_id": "FS-1"', '"target_node_id": "FS-1", "target_node_id": "SAN-1"', 1)
        result = self.invoke(raw)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("duplicate", result.stdout)


    def test_nested_san_namespace_in_fs_observation_fails_closed(self):
        capture = valid_capture()
        capture["fs_facts"]["facts"][0]["value"]["source"] = {
            "namespace": "san", "metadata": {"confidence": 0.9}}
        result = self.invoke(json.dumps(capture))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("nested cross-namespace", result.stdout)

    def test_nested_san_node_dependency_in_fs_observation_fails_closed(self):
        capture = valid_capture()
        capture["fs_facts"]["facts"][0]["value"]["dependencies"] = [
            {"target_node_id": "SAN-1", "relation_type": "depends_on"}]
        result = self.invoke(json.dumps(capture))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("nested cross-node", result.stdout)

    def test_nested_foreign_run_in_fs_observation_fails_closed(self):
        capture = valid_capture()
        capture["fs_facts"]["facts"][0]["value"]["source"] = {"run_id": "RUN-SAN"}
        result = self.invoke(json.dumps(capture))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("nested cross-RUN", result.stdout)

    def test_nested_local_provenance_passes(self):
        capture = valid_capture()
        capture["fs_facts"]["facts"][0]["value"]["dependencies"] = [
            {"namespace": "lab-fs147", "target_node_id": "FS-1",
             "run_id": "RUN-FS", "metric": {"value": 92}}]
        result = self.invoke(json.dumps(capture))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
