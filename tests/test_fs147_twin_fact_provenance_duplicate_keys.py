"""Regression: ambiguous stored fact provenance must never pass SAN/FS isolation."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "fs"))
from fs147_twin_partition_gate import IsolationError, qualify


def capture():
    graph = {"nodes": [
        {"node_id": "fs-147", "namespace": "lab-fs"},
        {"node_id": "san-1", "namespace": "lab-san"},
    ], "edges": []}
    fs = {"run_id": "core-fs-run", "synthetic": True, "facts": [
        {"fact_id": "fs-fact", "node_id": "fs-147",
         "value": json.dumps({"run_id": "core-fs-run", "synthetic": True,
                              "target_node_id": "fs-147"})}
    ]}
    san = {"run_id": "core-san-run", "synthetic": True, "facts": [
        {"fact_id": "san-fact", "node_id": "san-1",
         "value": json.dumps({"run_id": "core-san-run", "synthetic": True,
                              "target_node_id": "san-1"})}
    ]}
    return graph, fs, san


def check(graph, fs, san):
    return qualify(graph, fs, san, "lab-fs", "lab-san",
                   "core-fs-run", "core-san-run")


class FactProvenanceDuplicateKeyTests(unittest.TestCase):
    def test_unambiguous_fact_is_accepted(self):
        self.assertEqual(check(*capture())["status"], "PASS")

    def test_duplicate_run_id_is_rejected(self):
        graph, fs, san = capture()
        fs["facts"][0]["value"] = (
            '{"run_id":"core-san-run","run_id":"core-fs-run",'
            '"synthetic":true,"target_node_id":"fs-147"}'
        )
        with self.assertRaises(IsolationError):
            check(graph, fs, san)

    def test_duplicate_nested_provenance_key_is_rejected(self):
        graph, fs, san = capture()
        fs["facts"][0]["value"] = (
            '{"run_id":"core-fs-run","synthetic":true,'
            '"target_node_id":"fs-147","metadata":{"source":"SAN","source":"FS"}}'
        )
        with self.assertRaises(IsolationError):
            check(graph, fs, san)


if __name__ == "__main__":
    unittest.main()
