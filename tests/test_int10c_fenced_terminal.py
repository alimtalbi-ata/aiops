import unittest
from worker.int10c_fenced_terminal import recover_fenced_terminal, UnqualifiedTerminal
from worker.hitl_reject_core_wire import CORE_SCHEMA
from worker.hitl_reject_terminal_runtime import RECEIPT_SCHEMA

BODY = dict(owner="worker-1", run_id="RUN-1", proposal_id="PROP-1",
            proposal_hash="a"*64, proposal_revision=1, lease_token="x"*43,
            execution_allowed=False, effect_allowed=False)
def receipt(**changes):
    value = dict(schema=CORE_SCHEMA, receipt_schema=RECEIPT_SCHEMA, status="DEAD",
                 tenant_id="TEN-1", event_id="EV-1", actor_id=BODY["owner"],
                 run_id=BODY["run_id"], proposal_id=BODY["proposal_id"],
                 proposal_hash=BODY["proposal_hash"], proposal_revision=1,
                 attempts=8, dead_at="2026-11-18T10:00:00+00:00",
                 receipt_sha256="b"*64, idempotent=False,
                 execution_allowed=False, effect_allowed=False)
    value.update(changes)
    return value

class FencedTerminalTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_body_and_replay(self):
        calls = []
        async def core(tenant,event,body):
            calls.append((tenant,event,body))
            return 200, receipt(idempotent=len(calls)>1)
        first = await recover_fenced_terminal("TEN-1","EV-1",BODY,terminal=core)
        second = await recover_fenced_terminal("TEN-1","EV-1",BODY,terminal=core)
        self.assertEqual(calls,[("TEN-1","EV-1",BODY)]*2)
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["receipt_sha256"],second["receipt_sha256"])
        self.assertNotIn("lease_token",second)
    async def test_invalid_input_never_calls(self):
        async def forbidden(*args):
            self.fail("invalid body reached Core")
        for change in (dict(incident_id="INC-1"),dict(proposal_revision=True),
                       dict(lease_token="short"),dict(effect_allowed=True)):
            with self.subTest(change=change), self.assertRaises(UnqualifiedTerminal):
                await recover_fenced_terminal("TEN-1","EV-1",dict(BODY,**change),terminal=forbidden)
    async def test_core_denial_rotated_token_expiry_or_permission(self):
        # Scripted Core outcomes only; no claim of transactional authority.
        for status in (200,403,503):
            async def denied(*args):
                return status, dict(schema=CORE_SCHEMA,status="UNKNOWN",
                                    execution_allowed=False,effect_allowed=False)
            with self.subTest(status=status), self.assertRaises(UnqualifiedTerminal):
                await recover_fenced_terminal("TEN-1","EV-1",BODY,terminal=denied)
    async def test_receipt_drift_and_leak_denied(self):
        for change in (dict(tenant_id="TEN-2"),dict(actor_id="other"),dict(proposal_revision=2),
                       dict(attempts=7),dict(receipt_sha256="invalid"),dict(lease_token="secret"),
                       dict(dead_at="2026-11-18T10:00:00"),dict(idempotent=1)):
            async def core(*args):
                return 200,receipt(**change)
            with self.subTest(change=change), self.assertRaises(UnqualifiedTerminal):
                await recover_fenced_terminal("TEN-1","EV-1",BODY,terminal=core)
    async def test_lost_reply_same_fence_retry(self):
        calls=[]
        async def core(tenant,event,body):
            calls.append(body)
            if len(calls)==1:
                raise ConnectionError("injected lost terminal reply")
            return 200,receipt(idempotent=True)
        with self.assertRaises(UnqualifiedTerminal):
            await recover_fenced_terminal("TEN-1","EV-1",BODY,terminal=core)
        self.assertTrue((await recover_fenced_terminal("TEN-1","EV-1",BODY,terminal=core))["idempotent"])
        self.assertEqual(calls,[BODY,BODY])
