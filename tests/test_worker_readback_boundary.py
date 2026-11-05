"""Synthetic-only fail-closed expiry/restart-boundary regressions.

These tests do not assert durable replay prevention or a PG16/Temporal restart.
"""
import asyncio
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import runpy
import unittest

base = runpy.run_path(str(Path(__file__).with_name("test_worker_acme_simulated_hitl.py")))
INTENT, NOW = base["INTENT"], base["NOW"]
fixtures, simulate_no_effect = base["fixtures"], base["simulate_no_effect"]
SandboxDenied = base["SandboxDenied"]


class WorkerReadbackBoundaryTests(unittest.TestCase):
    def test_expiry_between_two_independent_reads_denies_receipt(self):
        docs = fixtures()
        reads = []
        async def get(component, path):
            reads.append(component)
            result = deepcopy(docs[component])
            if len(reads) > 3 and component == "twin":
                result["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
            return result
        with self.assertRaises(SandboxDenied):
            asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(reads, ["core", "twin", "policy", "core", "twin", "policy"])

    def test_second_read_transport_failure_denies_receipt(self):
        docs = fixtures()
        reads = []
        async def get(component, path):
            reads.append(component)
            if len(reads) == 5:
                raise ConnectionError("synthetic restart boundary")
            return deepcopy(docs[component])
        with self.assertRaisesRegex(
            SandboxDenied, "^sandbox_independent_readback_unavailable$"
        ):
            asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(reads, ["core", "twin", "policy", "core", "twin"])


if __name__ == "__main__":
    unittest.main()
