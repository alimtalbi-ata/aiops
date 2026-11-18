"""Adapt #79 binding tamper / expiry / replay tests to existing Worker contract.
No durable one-use claim: #79 SQLite tests remain archived.
"""
import asyncio
from copy import deepcopy
from datetime import timedelta
import unittest
from test_worker_acme_simulated_hitl import (
    INTENT, NOW, fixtures, simulate_no_effect, SandboxDenied, verify_no_effect_receipt,
)

class HistoricalBindingTests(unittest.TestCase):
    def test_binding_tamper_without_receipt(self):
        # #79 test_binding_tamper_rejected_without_consumption
        for field in ("incident_id", "run_id", "proposal_id", "approval_id", "ticket_id", "tenant_id", "attempt_id"):
            with self.subTest(field=field):
                docs = fixtures()
                calls = []
                async def get(component, path):
                    calls.append(component)
                    return deepcopy(docs[component])
                intent = dict(INTENT, **{field: "foreign"})
                with self.assertRaises(SandboxDenied):
                    asyncio.run(simulate_no_effect(intent, get=get, now=NOW))
                self.assertLessEqual(len(calls), 6)
                receipt = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
                identity = {k: INTENT[k] for k in ("attempt_id", "tenant_id", "incident_id", "run_id", "proposal_id", "ticket_id", "approval_id")}
                self.assertTrue(verify_no_effect_receipt(receipt, identity))
                self.assertEqual(receipt["effect_receipts"], 0)

    def test_consumption_expiry(self):
        # #79 test_consumption_expiry; independent Twin expiry, not SQLite consumption.
        docs = fixtures()
        async def get(component, path):
            return deepcopy(docs[component])
        with self.assertRaises(SandboxDenied):
            asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW + timedelta(seconds=301)))

    def test_retry_same_snapshot_is_same_receipt_not_one_use(self):
        # #79 single-use invariant requires durable authority; only deterministic no-effect here.
        docs = fixtures()
        async def get(component, path):
            return deepcopy(docs[component])
        first = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        second = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertEqual(first, second)
        self.assertEqual(second["effect_receipts"], 0)
        self.assertFalse(second["execution_allowed"])
