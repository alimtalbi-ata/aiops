"""Regression tests for the read-only FS147/SAN partition gate."""
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/fs/fs147_twin_partition_gate.py"
spec = importlib.util.spec_from_file_location("fs147_partition_gate", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    def node(identifier, namespace):
        return {"node_id": identifier, "namespace": namespace}
    def facts(run, node_id, fact_id):
        return {"run_id": run, "synthetic": True, "facts": [
            {"fact_id": fact_id, "node_id": node_id,
             "value": {"run_id": run, "synthetic": True,
                       "target_node_id": node_id}}]}
    return ({"nodes": [node("FS-147", "lab/fs147"), node("SAN-1", "lab/san")],
             "edges": []},
            facts("RUN-FS", "FS-147", "FACT-FS"),
            facts("RUN-SAN", "SAN-1", "FACT-SAN"))


class PartitionGateTests(unittest.TestCase):
    def check(self, graph, fs, san):
        return module.qualify(graph, fs, san, "lab/fs147", "lab/san")

    def test_core_run_binding_rejects_swapped_capture(self):
        graph, fs, san = fixture()
        self.assertEqual(module.qualify(graph, fs, san, "lab/fs147", "lab/san",
                                        "RUN-FS", "RUN-SAN")["status"], "PASS")
        with self.assertRaisesRegex(module.IsolationError, "filesystem RUN"):
            module.qualify(graph, fs, san, "lab/fs147", "lab/san",
                           "RUN-OTHER", "RUN-SAN")
        with self.assertRaisesRegex(module.IsolationError, "SAN RUN"):
            module.qualify(graph, fs, san, "lab/fs147", "lab/san",
                           "RUN-FS", "RUN-OTHER")

    def test_valid_isolated_capture(self):
        self.assertEqual(self.check(*fixture())["status"], "PASS")

    def test_anonymous_dependency_and_fact_ids_fail_closed(self):
        for field, value in (("edge_id", ""), ("edge_id", None),
                             ("relation_type", ""), ("relation_type", None)):
            with self.subTest(field=field, value=value):
                graph, fs, san = fixture()
                graph["edges"].append({"edge_id": "EDGE-FS", "source_id": "FS-147",
                                       "target_id": "FS-147", "relation_type": "DEPENDS_ON"})
                graph["edges"][0][field] = value
                with self.assertRaisesRegex(module.IsolationError, "dependency identity"):
                    self.check(graph, fs, san)
        for value in ("", None):
            with self.subTest(fact_id=value):
                graph, fs, san = fixture()
                fs["facts"][0]["fact_id"] = value
                with self.assertRaisesRegex(module.IsolationError, "missing fact identity"):
                    self.check(graph, fs, san)

    def test_named_same_namespace_dependency_is_accepted(self):
        graph, fs, san = fixture()
        graph["edges"].append({"edge_id": "EDGE-FS", "source_id": "FS-147",
                               "target_id": "FS-147", "relation_type": "DEPENDS_ON"})
        self.assertEqual(self.check(graph, fs, san)["edges"], 1)

    def test_cross_namespace_dependency(self):
        graph, fs, san = fixture()
        graph["edges"].append({"edge_id": "EDGE-X", "source_id": "FS-147",
                               "target_id": "SAN-1"})
        with self.assertRaises(module.IsolationError):
            self.check(graph, fs, san)

    def test_san_fact_substituted_into_fs_run(self):
        graph, fs, san = fixture()
        fs["facts"][0]["node_id"] = "SAN-1"
        with self.assertRaises(module.IsolationError):
            self.check(graph, fs, san)

    def test_cross_run_and_missing_target(self):
        for field, value in (("run_id", "RUN-SAN"), ("target_node_id", None)):
            with self.subTest(field=field):
                graph, fs, san = fixture()
                fs["facts"][0]["value"][field] = value
                with self.assertRaises(module.IsolationError):
                    self.check(graph, fs, san)

    def test_duplicate_ids_and_missing_namespace(self):
        for kind in ("duplicate_node", "duplicate_fact", "unscoped"):
            with self.subTest(kind=kind):
                graph, fs, san = fixture()
                if kind == "duplicate_node":
                    graph["nodes"][1]["node_id"] = "FS-147"
                elif kind == "duplicate_fact":
                    san["facts"][0]["fact_id"] = "FACT-FS"
                else:
                    graph["nodes"][1].pop("namespace")
                with self.assertRaises(module.IsolationError):
                    self.check(graph, fs, san)


if __name__ == "__main__":
    unittest.main()
