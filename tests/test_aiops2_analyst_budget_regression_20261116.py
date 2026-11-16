"""Offline bounded-input regression for synthetic Analyst/Critic; no external effects."""
import hashlib
import unittest
from scripts.aiops2_analyst_critic import analyze_and_critique
from scripts.aiops2_event_correlation import InvalidEvent


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def fixture():
    incident = {
        "tenant_id": "acme", "incident_id": "SAN-P1", "service_id": "Payments",
        "runtime_attested": False, "live_remediation_authorized": False,
        "events": [{"tenant_id": "acme", "service_id": "Payments",
                    "ci_id": "SAN", "evidence_sha256": digest("san-event")}],
    }
    impact = {
        "tenant_id": "acme", "incident_id": "SAN-P1", "service_id": "Payments",
        "runtime_attested": False, "live_remediation_authorized": False,
        "resource_budget_exhausted": False,
        "impact_state": "SOURCED_SYNTHETIC_PATH",
        "paths": [{"nodes": ["SAN", "Payments"],
                   "evidence_sha256": [digest("san-payments")]}],
    }
    return incident, impact


class AnalystBudgetRegression(unittest.TestCase):
    def test_baseline_remains_synthetic_and_denied(self):
        incident, impact = fixture()
        result = analyze_and_critique(incident, impact)
        self.assertEqual(result["critic"]["disposition"], "SUPPORTED_SYNTHETIC_HYPOTHESIS")
        self.assertFalse(result["critic"]["root_cause_confirmed"])
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["live_remediation_authorized"])
        self.assertEqual(result["policy_disposition"], "DENY_LIVE")

    def test_over_budget_paths_fail_closed(self):
        incident, impact = fixture()
        impact["paths"] = [
            {"nodes": ["SAN", f"CI{i}", "Payments"],
             "evidence_sha256": [digest(f"edge{i}a"), digest(f"edge{i}b")]}
            for i in range(101)
        ]
        with self.assertRaises(InvalidEvent):
            analyze_and_critique(incident, impact)

    def test_over_budget_origins_fail_closed(self):
        incident, impact = fixture()
        incident["events"] = [
            dict(incident["events"][0], ci_id=f"SAN{i}") for i in range(101)
        ]
        with self.assertRaises(InvalidEvent):
            analyze_and_critique(incident, impact)

    def test_over_budget_path_nodes_fail_closed(self):
        incident, impact = fixture()
        impact["paths"] = [{
            "nodes": ["SAN"] + [f"CI{i}" for i in range(99)] + ["Payments"],
            "evidence_sha256": [digest(str(i)) for i in range(100)],
        }]
        with self.assertRaises(InvalidEvent):
            analyze_and_critique(incident, impact)

    def test_exhausted_budget_cannot_claim_sourced_path(self):
        incident, impact = fixture()
        impact["resource_budget_exhausted"] = True
        with self.assertRaises(InvalidEvent):
            analyze_and_critique(incident, impact)

    def test_exhausted_budget_unknown_is_not_supported(self):
        incident, impact = fixture()
        impact.update(resource_budget_exhausted=True, impact_state="UNKNOWN", paths=[])
        result = analyze_and_critique(incident, impact)
        self.assertEqual(result["critic"]["disposition"], "NEEDS_MORE_EVIDENCE")
        self.assertIn("SOURCED_DEPENDENCY_PATH", result["analyst"]["missing_evidence"])
        self.assertEqual(result["policy_disposition"], "DENY_LIVE")


if __name__ == "__main__":
    unittest.main()
