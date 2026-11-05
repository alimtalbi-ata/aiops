"""Synthetic readback race matrix: no durable replay/PG16 claims.

No LIVE action, GLPI writes, or human approval are performed.
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


class SecondReadRaceMatrix(unittest.TestCase):
    def test_rotated_authority_on_second_round_fails_closed(self):
        mutations = (
            ("core", "incident_status", "RESOLVED"),
            ("core", "run_status", "REOPENED"),
            ("core", "request_sha256", "b" * 64),
            ("twin", "approval_nonce", "ROTATED-NONCE"),
            ("twin", "approval_id", "ROTATED-APPROVAL"),
            ("policy", "decision", "ALLOW"),
            ("policy", "human_approved", True),
            ("policy", "effect_allowed", True),
        )
        for target, field, replacement in mutations:
            with self.subTest(target=target, field=field):
                docs = fixtures()
                reads = []
                async def get(component, path):
                    reads.append(component)
                    result = deepcopy(docs[component])
                    if len(reads) > 3 and component == target:
                        result[field] = replacement
                    return result
                with self.assertRaises(SandboxDenied):
                    asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
                self.assertEqual(reads[:3], ["core", "twin", "policy"])
                self.assertIn(target, reads[3:])


if __name__ == "__main__":
    unittest.main()
