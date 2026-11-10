"""FS147 qualification graph contract: no implicit namespace or cross-scope edges."""
import ast
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


def load_endpoint():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "app/twin/main.py").read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "qualification_graph")
    fn.decorator_list = []
    # The endpoint's authorization annotation references typing aliases;
    # execute only this production function, with injected dependencies.
    env = {"Header": lambda default=None: default, "HTTPException": HTTPException,
           "SIM_TOKEN": "test-only-token", "os": os}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<twin-endpoint>", "exec"), env)
    return env


class QualificationGraphContract(unittest.TestCase):
    def setUp(self):
        self.env = load_endpoint()
        self.graph = {"nodes": [{"node_id": "FS-1"}, {"node_id": "SAN-1"}],
                      "edges": []}
        self.env["graph"] = lambda: self.graph

    def call(self, mapping, authorization="Bearer test-only-token"):
        with patch.dict(os.environ, {"AIOPS_TWIN_QUALIFICATION_NODE_NAMESPACES": mapping}):
            return self.env["qualification_graph"](authorization)

    def assert_hold(self, mapping, status=409):
        with self.assertRaises(HTTPException) as caught:
            self.call(mapping)
        self.assertEqual(caught.exception.status_code, status)

    def test_explicit_partition_passes_without_mutating_canonical_graph(self):
        original = json.dumps(self.graph, sort_keys=True)
        result = self.call('{"FS-1":"lab-fs147","SAN-1":"lab-san"}')
        self.assertEqual([n["namespace"] for n in result["nodes"]],
                         ["lab-fs147", "lab-san"])
        self.assertEqual(result["scope"], "qualification-only")
        self.assertEqual(json.dumps(self.graph, sort_keys=True), original)

    def test_missing_mapping_fails_closed(self):
        self.assert_hold('{"FS-1":"lab-fs147"}')
        self.assert_hold('', status=503)

    def test_cross_namespace_dependency_fails_closed(self):
        self.graph["edges"] = [{"edge_id": "E-1", "source_id": "FS-1",
                                "target_id": "SAN-1", "relation_type": "depends_on"}]
        self.assert_hold('{"FS-1":"lab-fs147","SAN-1":"lab-san"}')

    def test_authentication_required(self):
        with self.assertRaises(HTTPException) as caught:
            self.call('{"FS-1":"lab-fs147","SAN-1":"lab-san"}',
                      authorization=None)
        self.assertEqual(caught.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
