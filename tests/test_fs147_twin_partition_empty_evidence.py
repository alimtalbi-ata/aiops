"""FS147/SAN partition gate: missing evidence must never yield PASS."""
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/fs/fs147_twin_partition_gate.py"
spec = importlib.util.spec_from_file_location("fs147_partition_gate_empty", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def capture():
    graph = {"nodes": [
        {"node_id": "FS-147", "namespace": "lab/fs147"},
        {"node_id": "SAN-1", "namespace": "lab/san"}], "edges": []}
    fs = {"run_id": "RUN-FS", "synthetic": True, "facts": [
        {"fact_id": "FACT-FS", "node_id": "FS-147",
         "value": {"run_id": "RUN-FS", "synthetic": True,
                   "target_node_id": "FS-147"}}]}
    san = {"run_id": "RUN-SAN", "synthetic": True, "facts": [
        {"fact_id": "FACT-SAN", "node_id": "SAN-1",
         "value": {"run_id": "RUN-SAN", "synthetic": True,
                   "target_node_id": "SAN-1"}}]}
    return graph, fs, san


class MissingEvidenceTests(unittest.TestCase):
    def qualify(self, graph, fs, san):
        return gate.qualify(graph, fs, san, "lab/fs147", "lab/san")

    def test_baseline_isolated(self):
        self.assertEqual(self.qualify(*capture())["status"], "PASS")

    def test_empty_topology_is_hold(self):
        graph, fs, san = capture()
        graph["nodes"] = []
        with self.assertRaises(gate.IsolationError):
            self.qualify(graph, fs, san)

    def test_missing_partition_is_hold(self):
        for missing in ("lab/fs147", "lab/san"):
            with self.subTest(missing=missing):
                graph, fs, san = capture()
                graph["nodes"] = [n for n in graph["nodes"]
                                  if n["namespace"] != missing]
                with self.assertRaises(gate.IsolationError):
                    self.qualify(graph, fs, san)

    def test_empty_run_facts_are_hold(self):
        for run in ("fs", "san"):
            with self.subTest(run=run):
                graph, fs, san = capture()
                (fs if run == "fs" else san)["facts"] = []
                with self.assertRaises(gate.IsolationError):
                    self.qualify(graph, fs, san)


if __name__ == "__main__":
    unittest.main()
