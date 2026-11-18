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

    async def test_elapsed_timeout_cancels_cooperative_exercise(self):
        entered = asyncio.Event()
        cancelled = asyncio.Event()
        calls = []
        async def exercise():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        async def cleanup():
            self.assertTrue(cancelled.is_set())
            calls.append("cleanup")
        async def absence():
            return True
        result = await rehearse(PLAN,exercise=exercise,cleanup=cleanup,
                                verify_absence=absence,timeout=1)
        self.assertTrue(entered.is_set())
        self.assertEqual(result["outcome"],"TIMEOUT")
        self.assertEqual(calls,["cleanup"])

    async def test_external_cancellation_runs_cleanup_and_propagates(self):
        entered = asyncio.Event()
        calls = []
        async def exercise():
            entered.set()
            await asyncio.Event().wait()
        async def cleanup():
            calls.append("cleanup")
        async def absence():
            calls.append("absence")
            return True
        task = asyncio.create_task(rehearse(PLAN,exercise=exercise,
                                   cleanup=cleanup,verify_absence=absence,timeout=1))
        try:
            await asyncio.wait_for(entered.wait(),1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task,3)
            self.assertEqual(calls,["cleanup","absence"])
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
