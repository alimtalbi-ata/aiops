"""Negative contract: untrusted Core xref-shaped data cannot authorize Policy.

Candidate has no Core xref endpoint or 009-012 chain. This is a synthetic,
offline, fail-closed boundary test, NOT a Core xref runtime integration.
"""
import unittest

from app.policy.main import Decision, check, evaluate


BASE = {
    "mode": "DEMO", "command": "REMEDIATE", "severity": "P2",
    "confidence": 0.99, "evidence_count": 2, "critic_validated": True,
    "redundancy_ok": True, "evidence_fresh": True,
    "preconditions_verified": True, "fencing_verified": True,
    "human_approved": True,
}


class PolicyCoreXrefBoundaryTests(unittest.TestCase):
    def test_untrusted_xref_cannot_upgrade_synthetic_decision(self):
        # Xref-shaped objects are caller-controlled; they are NOT Core receipts.
        for xref in (
            None,
            {},
            {"schema": "aiops.core-itsm-xref-read.v1", "status": "UNKNOWN"},
            {"schema": "aiops.core-itsm-xref-read.v1", "status": "VERIFIED",
             "tenant_id": "OTHER-TENANT", "ticket_id": "FAKE-1",
             "execution_allowed": True, "effect_allowed": True},
        ):
            for mode in ("DEMO", "REPLAY", "STORY"):
                with self.subTest(xref=xref, mode=mode):
                    baseline = Decision(**{**BASE, "mode": mode})
                    # Policy does not accept xref as an authorization input.
                    supplied = Decision.model_validate({
                        **BASE, "mode": mode, "core_xref": xref,
                        "tenant_id": "UNATTESTED-TENANT",
                    })
                    result = evaluate(supplied)
                    self.assertEqual(result, evaluate(baseline))
                    self.assertEqual(result["decision"], "SIMULATE")
                    self.assertIs(result["execution_allowed"], False)
                    self.assertIs(result["effect_allowed"], False)
                    self.assertEqual(set(check(supplied)), {"state", "decision", "reason"})

    def test_xref_shaped_live_claim_cannot_create_approval(self):
        for command in ("OBSERVE", "EXECUTE", "REMEDIATE", "CANCEL"):
            with self.subTest(command=command):
                decision = Decision.model_validate({
                    **BASE, "mode": "LIVE", "command": command,
                    "core_xref": {"status": "VERIFIED", "human_approved": True},
                })
                result = evaluate(decision)
                self.assertIs(result["execution_allowed"], False)
                self.assertIs(result["effect_allowed"], False)
                self.assertNotIn(result["decision"], ("EXECUTE", "REMEDIATE"))
                self.assertEqual(set(check(decision)), {"state", "decision", "reason"})


if __name__ == "__main__":
    unittest.main()
