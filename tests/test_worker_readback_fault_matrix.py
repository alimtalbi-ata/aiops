"""Synthetic transport fault injection at each independent read boundary.

No durable replay, restart or PG16/Temporal assertion is made here.
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


class WorkerReadbackFaultMatrix(unittest.TestCase):
    def test_each_of_six_read_failures_is_fail_closed_and_sanitized(self):
        for failure_index in range(1, 7):
            with self.subTest(read=failure_index):
                docs = fixtures()
                calls = []
                async def get(component, path):
                    calls.append(component)
                    if len(calls) == failure_index:
                        raise ConnectionError("bearer SECRET-NEVER-LEAK")
                    return deepcopy(docs[component])
                with self.assertRaisesRegex(
                    SandboxDenied, "^sandbox_independent_readback_unavailable$"
                ):
                    asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
                self.assertEqual(len(calls), failure_index)
                self.assertEqual(
                    calls, (["core", "twin", "policy"] * 2)[:failure_index]
                )

    def test_second_read_missing_authority_is_not_a_receipt(self):
        for component in ("core", "twin", "policy"):
            with self.subTest(component=component):
                docs = fixtures()
                calls = []
                async def get(which, path):
                    calls.append(which)
                    if len(calls) > 3 and which == component:
                        return None
                    return deepcopy(docs[which])
                with self.assertRaises(SandboxDenied):
                    asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
                self.assertEqual(calls, ["core", "twin", "policy"] * 2)


if __name__ == "__main__":
    unittest.main()
