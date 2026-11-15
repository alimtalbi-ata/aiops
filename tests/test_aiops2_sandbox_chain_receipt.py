import unittest
from scripts.aiops2_sandbox_chain_receipt import receipt

BASE = {"mode": "SIMULATION_ONLY", "tenant": "acme-demo", "actor_tenant": "acme-demo",
        "path": ["SAN", "Payments"], "as_of": "2026-11-15T12:00:00Z",
        "evidence": [{"id": "san-1", "tenant": "acme-demo", "observed_at": "2026-11-15T11:59:00Z"}],
        "analysis": {"hypotheses": ["SAN path degraded"], "citations": ["san-1"],
                     "contradictions": [], "missing_evidence": ["independent critic proof"]},
        "hitl": "DENY"}

class ChainTests(unittest.TestCase):
    def test_safe_baseline(self):
        r = receipt(BASE)
        self.assertEqual(r["failures"], ["CRITIC_INDEPENDENCE_UNATTESTED"])
        self.assertFalse(r["effects_allowed"])
        self.assertEqual(r["hitl"], "DENY")
        self.assertEqual(r["glpi"], "NOT_EXECUTED")

    def test_adversarial_cases(self):
        cases = [
            ({"mode": "LIVE"}, "MODE_NOT_SIMULATION"),
            ({"actor_tenant": "other"}, "TENANT_ACL_UNATTESTED"),
            ({"path": ["SAN", "Other"]}, "DEPENDENCY_UNATTESTED"),
            ({"evidence": []}, "EVIDENCE_MISSING"),
            ({"evidence": [{"id": "san-1", "tenant": "other", "observed_at": "2026-11-15T11:59:00Z"}]}, "CROSS_TENANT_EVIDENCE"),
            ({"evidence": [{"id": "san-1", "tenant": "acme-demo", "observed_at": "2026-11-15T11:00:00Z"}]}, "STALE_OR_FUTURE_EVIDENCE"),
            ({"analysis": {"hypotheses": ["x"], "citations": ["invented"], "contradictions": [], "missing_evidence": []}}, "UNSUPPORTED_CITATION"),
            ({"hitl": "APPROVE"}, "HITL_NOT_DENY"),
        ]
        for change, expected in cases:
            with self.subTest(expected=expected):
                r = receipt({**BASE, **change})
                self.assertIn(expected, r["failures"])
                self.assertEqual(r["policy"], "DENY_LIVE")
                self.assertFalse(r["effects_allowed"])

    def test_malformed(self):
        for obj in (None, [], {}, {"mode": "LIVE"}):
            with self.subTest(obj=obj):
                self.assertFalse(receipt(obj)["effects_allowed"])

if __name__ == "__main__":
    unittest.main()
