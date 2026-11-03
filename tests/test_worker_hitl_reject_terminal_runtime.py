import asyncio
import ast
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'app'))
from worker.hitl_reject_terminal_runtime import (
    CORE_SCHEMA, RECEIPT_SCHEMA, UnqualifiedTerminal, recover_terminal_once,
)

ARGS = dict(tenant_id='TENANT-01', event_id='EVENT-01', run_id='RUN-01',
            incident_id='INC-01', proposal_id='PROPOSAL-01',
            proposal_hash='a'*64, proposal_revision=1, decision='REJECT',
            execution_allowed=False, effect_allowed=False)
OWNER = 'svc-terminal-01'


def receipt(**changes):
    r = dict(schema=CORE_SCHEMA, receipt_schema=RECEIPT_SCHEMA, status='DEAD',
             execution_allowed=False, effect_allowed=False, attempts=8,
             idempotent=False, actor_id=OWNER, tenant_id=ARGS['tenant_id'],
             event_id=ARGS['event_id'], run_id=ARGS['run_id'],
             incident_id=ARGS['incident_id'], proposal_id=ARGS['proposal_id'], proposal_hash=ARGS['proposal_hash'],
             proposal_revision=1, receipt_sha256='b'*64,
             dead_at='2026-11-02T10:00:00+00:00')
    r.update(changes)
    return r


class TerminalRuntimeTests(unittest.TestCase):
    def run_async(self, post, args=None):
        return asyncio.run(recover_terminal_once(args or dict(ARGS), owner=OWNER, post=post))

    def test_01_core_dead_and_readback_only(self):
        calls = []
        async def post(path, body):
            calls.append((path, body))
            return receipt(idempotent=len(calls)==2)
        result = self.run_async(post)
        self.assertEqual([p.split('/')[-1] for p, _ in calls],
                         ['terminal-recover', 'terminal-receipt'])
        self.assertEqual(result['status'], 'DEAD')
        self.assertFalse(result['temporal_signal_sent'])
        self.assertFalse(result['ack_sent'])
        self.assertEqual(result['human_glpi_authorization'], 'UNKNOWN')
        for path, body in calls:
            self.assertNotIn('lease_token', repr((path, body)))
            self.assertEqual(body['owner'], OWNER)
            self.assertIs(body['effect_allowed'], False)

    def test_02_replay_idempotent(self):
        async def post(path, body): return receipt(idempotent=True)
        self.assertTrue(self.run_async(post)['idempotent'])

    def test_03_unknown_blocks_readback(self):
        calls=[]
        async def post(path, body):
            calls.append(path)
            return {'schema': CORE_SCHEMA, 'status': 'UNKNOWN',
                    'execution_allowed': False, 'effect_allowed': False}
        with self.assertRaises(UnqualifiedTerminal): self.run_async(post)
        self.assertEqual(len(calls), 1)

    def test_04_401_403_fail_closed(self):
        for status in (401, 403, 503):
            async def post(path, body): raise RuntimeError('HTTP '+str(status))
            with self.subTest(status=status), self.assertRaises(UnqualifiedTerminal):
                self.run_async(post)

    def test_05_approval_and_token_injection_blocked(self):
        for key, value in [('decision','APPROVE'), ('execution_allowed',True),
                           ('effect_allowed',True), ('lease_token','secret')]:
            args=dict(ARGS); args[key]=value
            async def post(path, body): self.fail('must not call Core')
            with self.subTest(key=key), self.assertRaises(UnqualifiedTerminal):
                self.run_async(post,args)

    def test_06_readback_mismatch(self):
        n=0
        async def post(path, body):
            nonlocal n
            n+=1
            return receipt(receipt_sha256=('c' if n==2 else 'b')*64)
        with self.assertRaises(UnqualifiedTerminal): self.run_async(post)

    def test_07_bad_binding_or_token_leak(self):
        for changes in ({'run_id':'OTHER'}, {'lease_token':'raw'},
                        {'attempts':7}, {'actor_id':'other'},
                        {'dead_at':'2026-11-02T10:00:00'}):
            async def post(path, body): return receipt(**changes)
            with self.subTest(changes=changes), self.assertRaises(UnqualifiedTerminal):
                self.run_async(post)

    def test_09_missing_canonical_incident_fails_before_readback(self):
        calls = []
        async def post(path, body):
            calls.append(path)
            response = receipt()
            del response['incident_id']
            return response
        with self.assertRaises(UnqualifiedTerminal):
            self.run_async(post)
        self.assertEqual(len(calls), 1)

    def test_10_foreign_canonical_incident_on_readback_fails(self):
        calls = []
        async def post(path, body):
            calls.append(path)
            return receipt(incident_id='INC-FOREIGN') if len(calls) == 2 else receipt()
        with self.assertRaises(UnqualifiedTerminal):
            self.run_async(post)
        self.assertEqual(len(calls), 2)

    def test_08_production_registration_and_workflow(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / 'app/worker/main.py').read_text()
        tree=ast.parse(source)
        worker=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='worker_main')
        self.assertIn('reject_terminal_recover', ast.unparse(worker))
        self.assertIn('TerminalRejectWorkflow', ast.unparse(worker))
        isolated = (pathlib.Path(__file__).resolve().parents[1] /
                    'app/worker/temporal_workflows.py').read_text()
        workflow_tree = ast.parse(isolated)
        terminal = next(n for n in ast.walk(workflow_tree)
                        if isinstance(n, ast.ClassDef) and n.name == 'TerminalRejectWorkflow')
        self.assertIn('execute_activity(', ast.unparse(terminal))
        self.assertIn('reject_terminal_recover', ast.unparse(terminal))
        self.assertNotIn('signal_workflow', source + isolated)
        self.assertNotIn('shared.http', isolated)
        self.assertNotIn('worker.main', isolated)

if __name__ == '__main__': unittest.main()
