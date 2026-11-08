import unittest
from datetime import datetime, timezone
from worker.fs147_observation_gate import admit_observation

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc)
        self.env = dict(tenant_id='demo', ticket_id=147, run_id='RUN-147', source='fs-lab',
                        access_mode='read-only', provenance_verified=True, source_event_id='evt-1',
                        observed_at='2026-11-08T19:59:00Z', received_at='2026-11-08T19:59:30Z',
                        evidence={'filesystem_usage_percent': 92})
        self.kw = dict(now=self.now, expected_run_id='RUN-147', expected_tenant_id='demo', expected_ticket_id=147)
    def check(self, **changes):
        return admit_observation(self.env | changes, **self.kw)
    def test_accept_and_deterministic_fingerprint(self):
        a = self.check(); b = self.check()
        self.assertEqual(a, b)
        self.assertEqual(a['status'], 'ACCEPTED')
    def test_identity_rejection(self):
        for change in ({'run_id':'other'}, {'ticket_id':True}, {'tenant_id':'other'}):
            with self.subTest(change=change): self.assertEqual(self.check(**change)['status'], 'UNKNOWN')
    def test_provenance_and_read_only(self):
        for change in ({'provenance_verified':1}, {'access_mode':'read-write'}, {'source':'SAN'}):
            with self.subTest(change=change): self.assertEqual(self.check(**change)['status'], 'UNKNOWN')
    def test_stale_and_future(self):
        self.assertEqual(self.check(observed_at='2026-11-08T19:50:00Z')['reason'], 'STALE_OBSERVATION')
        self.assertEqual(self.check(received_at='2026-11-08T20:01:00Z')['reason'], 'INVALID_TIMESTAMPS')
    def test_missing_or_malformed(self):
        for change in ({'evidence':{}}, {'evidence':{'x':float('nan')}}, {'observed_at':'invalid'}, {'source_event_id':''}):
            with self.subTest(change=change): self.assertEqual(self.check(**change)['status'], 'UNKNOWN')
    def test_insufficient_nested_evidence_fails_closed(self):
        for evidence in ({'value': None}, {'value': '   '}, {'nested': {}},
                         {'nested': {'metric': None}}, {'samples': []},
                         {'samples': [1, None]}, {'value': float('inf')},
                         {'value': object()}):
            with self.subTest(evidence=repr(evidence)):
                result = self.check(evidence=evidence)
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertEqual(result['reason'], 'INSUFFICIENT_EVIDENCE')
                self.assertIsNone(result['fingerprint'])
    def test_nonempty_nested_evidence_admitted(self):
        self.assertEqual(self.check(evidence={'samples': [{'metric': 92}]} )['status'], 'ACCEPTED')
    def test_replay_fingerprint_changes_with_event(self):
        self.assertNotEqual(self.check()['fingerprint'], self.check(source_event_id='evt-2')['fingerprint'])
    def test_bad_policy_fails_closed(self):
        self.assertEqual(admit_observation(self.env, **(self.kw | {'max_age_seconds':True}))['status'], 'UNKNOWN')
if __name__ == '__main__': unittest.main()
