"""FS147: scenario readback must bind a fact's claimed node to its SQL node."""
import ast
import unittest
from pathlib import Path


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class DB:
    def __init__(self, value, node="FS-LAB147"):
        self.value, self.node = value, node
        self.calls = []

    def __call__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return [("FACT-1", self.node, "observation", self.value,
                 None, None, None, 1.0)]


def route(db):
    path = Path(__file__).resolve().parents[1] / "app/twin/main.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "scenario_facts")
    fn.decorator_list = []
    ns = {"HTTPException": HTTPException, "SIM_TOKEN": "token",
          "Header": lambda default=None: default, "db": db}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), ns)
    return ns["scenario_facts"]


class NodeBindingTest(unittest.TestCase):
    def test_rejects_san_node_claim_in_filesystem_row(self):
        db = DB({"run_id": "RUN-FS147", "synthetic": True,
                 "target_node_id": "SAN-VOLUME"})
        with self.assertRaises(HTTPException) as ctx:
            route(db)("RUN-FS147", authorization="Bearer token")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(len(db.calls), 1)
        self.assertIn("run_id", db.calls[0][0])

    def test_accepts_matching_node_and_legacy_fact_without_claim(self):
        for payload in (
            {"run_id": "RUN-FS147", "synthetic": True,
             "target_node_id": "FS-LAB147"},
            {"run_id": "RUN-FS147", "synthetic": "true"},
        ):
            with self.subTest(payload=payload):
                result = route(DB(payload))("RUN-FS147",
                                            authorization="Bearer token")
                self.assertEqual(result["facts"][0]["node_id"], "FS-LAB147")

    def test_rejects_cross_run_even_when_node_matches(self):
        db = DB({"run_id": "RUN-SAN", "synthetic": True,
                 "target_node_id": "FS-LAB147"})
        with self.assertRaises(HTTPException) as ctx:
            route(db)("RUN-FS147", authorization="Bearer token")
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
