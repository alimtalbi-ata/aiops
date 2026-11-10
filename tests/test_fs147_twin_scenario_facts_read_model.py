"""FS147 scenario read model contract: actual route, fake DB, no live effects."""
import ast
from pathlib import Path
import unittest


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class FakeDB:
    def __init__(self, rows=()):
        self.rows = rows
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
        return self.rows


def route(db):
    path = Path(__file__).resolve().parents[1] / 'app/twin/main.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == 'scenario_facts')
    fn.decorator_list = []
    ns = {'HTTPException': HTTPException, 'SIM_TOKEN': 'test-token',
          'Header': lambda default=None: default, 'db': db}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), ns)
    return ns['scenario_facts']


class ScenarioFactsContract(unittest.TestCase):
    def test_auth_and_invalid_run_fail_before_db(self):
        db = FakeDB()
        fn = route(db)
        for run_id, token, expected in [
            ('RUN-FS147', 'Bearer invalid', 401),
            ('', 'Bearer test-token', 422),
            (' RUN-FS147', 'Bearer test-token', 422),
            ('RUN-FS147\\nSAN', 'Bearer test-token', 422),
        ]:
            with self.subTest(run_id=repr(run_id)), self.assertRaises(HTTPException) as ctx:
                fn(run_id, authorization=token)
            self.assertEqual(ctx.exception.status_code, expected)
        self.assertEqual(db.calls, [])

    def test_run_fencing_and_synthetic_filter_are_both_in_sql(self):
        db = FakeDB([('FACT-FS', 'FS-LAB147', 'observation',
                      {'synthetic': True, 'run_id': 'RUN-FS147'}, None, None, None, 1.0)])
        result = route(db)('RUN-FS147', authorization='Bearer test-token')
        self.assertEqual(result['run_id'], 'RUN-FS147')
        self.assertEqual(result['facts'][0]['node_id'], 'FS-LAB147')
        self.assertEqual(result['record_type'], 'twin_fact')
        self.assertEqual(len(db.calls), 1)
        sql, params = db.calls[0]
        self.assertEqual(params, ('RUN-FS147',))
        self.assertIn("value::jsonb ->> 'run_id' = %s", sql)
        self.assertIn("value::jsonb ->> 'synthetic' = 'true'", sql)
        self.assertIn('from aiops.twin_facts', sql)
        for forbidden in ('aiops.observations', 'aiops.twin_nodes', 'aiops.twin_edges'):
            self.assertNotIn(forbidden, sql.lower())
        self.assertFalse(any(x in sql.lower() for x in ('insert ', 'update ', 'delete ')))

    def test_fs_and_san_are_distinct_queries(self):
        db = FakeDB()
        fn = route(db)
        fn('RUN-FS147', authorization='Bearer test-token')
        fn('RUN-SAN147', authorization='Bearer test-token')
        self.assertEqual([params for _, params in db.calls],
                         [('RUN-FS147',), ('RUN-SAN147',)])

    def test_overflow_fails_closed_without_claiming_complete_evidence(self):
        db = FakeDB([('FACT', 'FS', 'observation', {}, None, None, None, 1)] * 501)
        with self.assertRaises(HTTPException) as ctx:
            route(db)('RUN-FS147', authorization='Bearer test-token')
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == '__main__':
    unittest.main()
