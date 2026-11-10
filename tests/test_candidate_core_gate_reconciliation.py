"""Gate evidence contract regressions; extracted route, no PostgreSQL runtime."""
import ast
import json
from pathlib import Path
import unittest


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Connection:
    def __init__(self, known=('EV-1',), mode='DEMO'):
        self.known, self.mode = set(known), mode
        self.writes = []
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        if query.startswith('select mode'):
            self.row = (self.mode,)
        elif 'count(*)' in query:
            self.row = (len(self.known.intersection(params[0])),)
        else:
            self.writes.append((query, params))
        return self

    def fetchone(self):
        return self.row


def load_gate(connection):
    source = Path(__file__).resolve().parents[1] / 'app/core/main.py'
    node = next(n for n in ast.parse(source.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'gate')
    node.decorator_list = []
    namespace = dict(db=lambda: connection, json=json, HTTPException=HTTPException,
                     auth=lambda value: None, bearer=lambda value: value,
                     Header=lambda default=None: default, new=lambda prefix: prefix)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['gate']


class GateReconciliationTests(unittest.TestCase):
    def test_repeated_stage_replaces_categories_with_current_contract(self):
        connection = Connection()
        gate = load_gate(connection)
        gate('RUN-1', dict(stage='POLICY', state='PASS', decision='SIMULATE',
                          required_evidence=['observation'], evidence_ids=['EV-1']), 'token')
        gate('RUN-1', dict(stage='POLICY', state='UNKNOWN',
                          required_evidence=[], evidence_ids=[]), 'token')
        self.assertEqual(len(connection.writes), 2)
        for sql, params in connection.writes:
            self.assertIn('required_evidence=excluded.required_evidence', sql)
        self.assertEqual(json.loads(connection.writes[0][1][4]), ['observation'])
        self.assertEqual(json.loads(connection.writes[1][1][4]), [])
        self.assertEqual(connection.writes[1][1][3], 'UNKNOWN')

if __name__ == '__main__':
    unittest.main()
