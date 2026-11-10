"""Actual control-character admission cases; no PostgreSQL or service calls."""
import unittest
from test_candidate_core_gate_evidence_shape import Connection, HTTPException, load_gate


class GateIdentityTests(unittest.TestCase):
    def deny(self, payload):
        connection = Connection()
        calls = []
        execute = connection.execute
        def record(query, params):
            calls.append(query)
            return execute(query, params)
        connection.execute = record
        with self.assertRaises(HTTPException) as caught:
            load_gate(connection)('RUN-1', payload, 'token')
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(calls, [])

    def test_missing_or_noncanonical_stage(self):
        for stage in (None, '', ' ', [], 1, ' POLICY', 'POLICY ',
                      'POL\nICY', 'POL\tICY', 'POL\x00ICY', 'POL\x7fICY'):
            with self.subTest(stage=stage):
                self.deny(dict(stage=stage, state='UNKNOWN'))
        self.deny(dict(state='UNKNOWN'))

    def test_unknown_state_value(self):
        for state in (None, '', 'SUCCESS', 'pass', [], {}):
            with self.subTest(state=state):
                self.deny(dict(stage='POLICY', state=state))
        self.deny(dict(stage='POLICY'))

    def test_evidence_and_category_identity(self):
        for field in ('evidence_ids', 'required_evidence'):
            for value in (' EV-1', 'EV-1 ', 'EV\n-1', 'EV\t-1', 'EV\x00-1', 'EV\x7f-1'):
                with self.subTest(field=field, value=value):
                    self.deny(dict(stage='POLICY', state='UNKNOWN', **{field: [value]}))

    def test_canonical_states_remain_accepted(self):
        for state in ('FAIL', 'BLOCKED', 'UNKNOWN', 'NEEDS_HUMAN', 'PENDING', 'RUNNING'):
            connection = Connection()
            result = load_gate(connection)('RUN-1', dict(stage='POLICY', state=state), 'token')
            self.assertEqual(result['state'], state)
            self.assertEqual(len(connection.writes), 1)
