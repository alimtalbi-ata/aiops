import asyncio
import unittest
from int10c_lab_lifecycle import rehearse

PLAN = {"status":"PLAN_ONLY","launch_authorized":False,
        "runtime_attested":False,"ownership":"UNKNOWN"}

class LifecycleRehearsal(unittest.IsolatedAsyncioTestCase):
    async def test_order_on_success_and_interruption(self):
        for interrupted in (False,True):
            calls=[]
            async def exercise():
                calls.append("exercise")
                if interrupted:
                    raise ConnectionError("synthetic fault")
            async def cleanup():
                calls.append("cleanup")
            async def absence():
                calls.append("absence")
                return True
            result=await rehearse(PLAN,exercise=exercise,cleanup=cleanup,
                                 verify_absence=absence,timeout=1)
            self.assertEqual(calls,["exercise","cleanup","absence"])
            self.assertEqual(result["outcome"],"INTERRUPTED" if interrupted else "COMPLETED")
            self.assertIs(result["cleanup_observed"],True)
            self.assertIs(result["runtime_attested"],False)

    async def test_cleanup_failure_and_missing_absence(self):
        async def exercise():
            pass
        async def absence():
            return False
        async def broken():
            raise RuntimeError("synthetic cleanup failure")
        for cleanup in (exercise,broken):
            result=await rehearse(PLAN,exercise=exercise,cleanup=cleanup,
                                  verify_absence=absence,timeout=1)
            self.assertIs(result["cleanup_observed"],False)
            self.assertIs(result["launch_authorized"],False)

    async def test_timeout_still_cleans(self):
        calls=[]
        async def exercise():
            raise TimeoutError("injected timeout, not elapsed wall time")
        async def cleanup():
            calls.append("cleanup")
        async def absence():
            return True
        result=await rehearse(PLAN,exercise=exercise,cleanup=cleanup,
                              verify_absence=absence,timeout=1)
        self.assertEqual(result["outcome"],"TIMEOUT")
        self.assertEqual(calls,["cleanup"])

    async def test_invalid_plan_never_calls(self):
        async def forbidden():
            self.fail("invalid plan reached callback")
        with self.assertRaises(ValueError):
            await rehearse(dict(PLAN,launch_authorized=True),exercise=forbidden,
                           cleanup=forbidden,verify_absence=forbidden,timeout=1)
