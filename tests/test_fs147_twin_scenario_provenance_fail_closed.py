"""Scenario fact readback must reject cross-RUN rows even if DB filtering drifts."""
import ast
import unittest
from pathlib import Path


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class DB:
    def __init__(self, value):
        self.value = value
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
        return [('FACT-1', 'FS-LAB147', 'observation',
                 self.value, None, None, None, 1.0)]


def route(db):
    path = Path(__file__).resolve().parents[1] / 'app/twin/main.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == 'scenario_facts')
    fn.decorator_list = []
    namespace = {'HTTPException': HTTPException, 'SIM_TOKEN': 'token',
                 'Header': lambda default=None: default, 'db': db}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'),
         namespace)
    return namespace['scenario_facts']


class ScenarioProvenanceTest(unittest.TestCase):
    def test_rejects_other_run_and_unmarked_rows(self):
        cases = [
            {'run_id': 'RUN-SAN', 'synthetic': True},
            {'run_id': 'RUN-FS147', 'synthetic': False},
            {'run_id': 'RUN-FS147'},
            {'run_id': 'RUN-FS147', 'synthetic': 1},
            'not-json',
        ]
        for value in cases:
            with self.subTest(value=value):
                db = DB(value)
                with self.assertRaises(HTTPException) as ctx:
                    route(db)('RUN-FS147', authorization='Bearer token')
                self.assertEqual(ctx.exception.status_code, 409)
                self.assertEqual(len(db.calls), 1)

    def test_accepts_exact_run_with_boolean_or_string_marker(self):
        for marker in (True, 'true'):
            with self.subTest(marker=marker):
                db = DB({'run_id': 'RUN-FS147', 'synthetic': marker})
                result = route(db)('RUN-FS147', authorization='Bearer token')
                self.assertEqual(len(result['facts']), 1)
                self.assertEqual(result['run_id'], 'RUN-FS147')


if __name__ == '__main__':
    unittest.main()
