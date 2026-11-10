"""FS147 stage side-effect claims must stop read-only pipeline progression."""
import unittest
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request, execute

class PolicyExecutionMetadataTests(unittest.TestCase):

    def setUp(self):
        self.req = FS147Request('tenant', 'actor', 'incident', 'run')
        self.calls = []
        self.scope = dict(tenant_id='tenant', actor_id='actor', incident_id='incident', run_id='run', ticket_id=147, evidence_id='ev-1')
        self.clock = lambda: datetime(2026, 11, 10, 1, 0, tzinfo=timezone.utc)

    def observe(self, _):
        self.calls.append('observe')
        return dict(self.scope, source='fs-lab-bridge-readonly', commands=['df', 'du', 'ls'], filesystem='/fs-lab', read_only=True, collected_at='2026-11-10T01:00:00+00:00', used_percent=50)

    def analyst(self, _, observation):
        self.calls.append('analyst')
        return dict(self.scope, findings=['fs-lab diagnostic'])

    def critic(self, *_):
        self.calls.append('critic')
        return dict(self.scope, state='PASS', validated=True, missing_information=[])

    def policy(self, *_):
        self.calls.append('policy')
        return dict(self.scope, state='PASS', decision='SIMULATE', dispatch_allowed=False, effect='NO_EFFECT')

    def test_policy_execution_metadata_must_match_simulation(self):
        for field, value in (('dry_run', False), ('dry_run', None), ('dry_run', 1), ('dry_run', 'true'), ('execution_mode', 'LIVE'), ('execution_mode', None), ('execution_mode', 'DEMO')):
            with self.subTest(field=field, value=value):
                self.calls = []

                def policy(*args):
                    return dict(self.policy(*args), **{field: value})
                result = execute(self.req, stop_auto=False, observe=self.observe, analyst=self.analyst, critic=self.critic, policy=policy, claim_once=lambda _: True, now=self.clock)
                self.assertEqual((result['status'], result.get('reason'), result['effect']), ('BLOCKED', 'POLICY_REFUSED', 'NO_EFFECT'))
                self.assertEqual(self.calls, ['observe', 'analyst', 'critic', 'policy'])

    def test_policy_explicit_simulation_metadata_is_readonly(self):

        def policy(*args):
            return dict(self.policy(*args), dry_run=True, execution_mode='SIMULATE')
        result = execute(self.req, stop_auto=False, observe=self.observe, analyst=self.analyst, critic=self.critic, policy=policy, claim_once=lambda _: True, now=self.clock)
        self.assertEqual(result['status'], 'NO_EFFECT')
        self.assertEqual(result['effect'], 'NO_EFFECT')
if __name__ == '__main__':
    unittest.main()
