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


class GateEvidenceShapeTests(unittest.TestCase):
    def deny(self, payload, status):
        connection = Connection()
        with self.assertRaises(HTTPException) as caught:
            load_gate(connection)('RUN-1', payload, 'token')
        self.assertEqual(caught.exception.status_code, status)
        self.assertFalse(connection.writes)

    def test_pass_requires_nonempty_evidence_and_categories(self):
        for payload in ({'stage': 'OBSERVE', 'state': 'PASS'},
                        {'stage': 'OBSERVE', 'state': 'PASS', 'required_evidence': ['observation']},
                        {'stage': 'OBSERVE', 'state': 'PASS', 'evidence_ids': ['EV-1']}):
            with self.subTest(payload=payload):
                self.deny(payload, 409)

    def test_malformed_evidence_is_rejected_without_write(self):
        for field in ('evidence_ids', 'required_evidence'):
            for value in (None, 'EV-1', {}, [True], [''], ['  '], [['nested']], ['x', 'x']):
                payload = dict(stage='OBSERVE', state='UNKNOWN', evidence_ids=['EV-1'],
                               required_evidence=['observation'])
                payload[field] = value
                with self.subTest(field=field, value=value):
                    self.deny(payload, 422)

    def test_worker_category_contract_is_preserved(self):
        connection = Connection()
        result = load_gate(connection)('RUN-1', dict(
            stage='POLICY', state='PASS', decision='SIMULATE',
            evidence_ids=['EV-1'],
            required_evidence=['analyst', 'critic', 'twin', 'observation']), 'token')
        self.assertEqual(result['state'], 'PASS')
        self.assertEqual(len(connection.writes), 1)

    def test_unknown_persisted_evidence_is_rejected(self):
        self.deny(dict(stage='OBSERVE', state='PASS', evidence_ids=['EV-missing'],
                       required_evidence=['observation']), 422)

    def test_synthetic_policy_guard_is_preserved(self):
        self.deny(dict(stage='POLICY', state='PASS', decision='EXECUTE',
                       evidence_ids=['EV-1'], required_evidence=['observation']), 422)

    def test_unknown_gate_can_record_missing_evidence(self):
        connection = Connection()
        result = load_gate(connection)('RUN-1', dict(stage='OBSERVE', state='UNKNOWN'), 'token')
        self.assertEqual(result['state'], 'UNKNOWN')
        self.assertEqual(len(connection.writes), 1)


class GateEvidenceRunBindingTests(unittest.TestCase):
    def test_explicit_foreign_or_unknown_run_is_refused(self):
        for owner in ('RUN-OTHER', None, '', 42):
            connection = Connection()
            original = connection.execute
            def execute(query, params):
                result = original(query, params)
                if 'count(*)' in query and len(params) > 1:
                    connection.row = (int(owner == params[1]),)
                return result
            connection.execute = execute
            with self.subTest(owner=owner):
                with self.assertRaises(HTTPException) as caught:
                    load_gate(connection)('RUN-1', dict(stage='OBSERVE', state='PASS',
                        evidence_ids=['EV-1'], required_evidence=['observation']), 'token')
                self.assertEqual(caught.exception.status_code, 422)
                self.assertFalse(connection.writes)


if __name__ == '__main__':
    unittest.main()


class GateProvenanceObjectTests(unittest.TestCase):
    def test_nonobject_provenance_is_not_legacy_ownership(self):
        # SQL double models the PostgreSQL '?' absent-key behavior on scalars.
        # Actual JSON operators are exercised by the Actions-only PG fixture.
        for provenance in (None, [], ["other"], "legacy", 42, False):
            connection = Connection()
            original = connection.execute
            def execute(query, params):
                result = original(query, params)
                if 'count(*)' in query:
                    connection.row = (int("jsonb_typeof(provenance)='object'" not in query),)
                return result
            connection.execute = execute
            with self.subTest(provenance=provenance):
                with self.assertRaises(HTTPException) as caught:
                    load_gate(connection)('RUN-1', dict(stage='OBSERVE', state='PASS',
                        evidence_ids=['EV-1'], required_evidence=['observation']), 'token')
                self.assertEqual(caught.exception.status_code, 422)
                self.assertFalse(connection.writes)
