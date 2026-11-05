"""Synthetic Worker rollback/retry fence: no durable PG16/Temporal claim.

An aborted independent readback must never produce a receipt. A subsequent
fresh attempt may only produce PRE_RESOLUTION SIMULATED_NO_EFFECT.
"""
import asyncio
from copy import deepcopy
from pathlib import Path
import runpy
import unittest

base = runpy.run_path(str(Path(__file__).with_name("test_worker_acme_simulated_hitl.py")))
INTENT, NOW = base["INTENT"], base["NOW"]
fixtures, simulate_no_effect = base["fixtures"], base["simulate_no_effect"]
SandboxDenied = base["SandboxDenied"]
receipt_digest_valid = base["receipt_digest_valid"]


class WorkerSyntheticRollbackRetry(unittest.TestCase):
    def test_abort_at_each_readback_step_then_fresh_retry(self):
        for fail_at in range(1, 7):
            with self.subTest(fail_at=fail_at):
                docs = fixtures()
                calls = []
                emitted = []
                async def broken_get(component, path):
                    calls.append(component)
                    if len(calls) == fail_at:
                        raise ConnectionError("synthetic transient rollback")
                    return deepcopy(docs[component])
                with self.assertRaises(SandboxDenied):
                    emitted.append(asyncio.run(
                        simulate_no_effect(INTENT, get=broken_get, now=NOW)
                    ))
                self.assertEqual(emitted, [])
                self.assertEqual(len(calls), fail_at)

                retry_calls = []
                async def clean_get(component, path):
                    retry_calls.append(component)
                    return deepcopy(docs[component])
                receipt = asyncio.run(
                    simulate_no_effect(INTENT, get=clean_get, now=NOW)
                )
                self.assertEqual(retry_calls, ["core", "twin", "policy"] * 2)
                self.assertTrue(receipt_digest_valid(receipt))
                self.assertEqual(receipt["receipt_status"], "SIMULATED_NO_EFFECT")
                self.assertEqual(receipt["receipt_phase"], "PRE_RESOLUTION")
                self.assertFalse(receipt["human_approved"])
                self.assertFalse(receipt["glpi_write"])
                self.assertFalse(receipt["resolution_verified"])
                self.assertEqual(receipt["effect_receipts"], 0)


if __name__ == "__main__":
    unittest.main()
