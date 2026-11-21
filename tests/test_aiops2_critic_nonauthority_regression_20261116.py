"""Offline regression: synthetic Critic must never be mistaken for authority.

This intentionally demonstrates that syntactically valid forged digests pass
the *synthetic* Analyst/Critic; this is a limitation receipt, not a security PASS.
No model, ITSM, Temporal, network, or execution side effects.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_analyst_critic import analyze_and_critique


def _fixture(event_digest="a" * 64, edge_digest="b" * 64):
    incident = {
        "tenant_id": "acme", "incident_id": "demo-san-1", "service_id": "payments",
        "runtime_attested": False, "live_remediation_authorized": False,
        "events": [{"tenant_id": "acme", "service_id": "payments",
                    "ci_id": "san-01", "evidence_sha256": event_digest}],
    }
    impact = {
        "tenant_id": "acme", "incident_id": "demo-san-1", "service_id": "payments",
        "runtime_attested": False, "live_remediation_authorized": False,
        "resource_budget_exhausted": False,
        "impact_state": "SOURCED_SYNTHETIC_PATH",
        "paths": [{"nodes": ["san-01", "payments"],
                   "evidence_sha256": [edge_digest]}],
    }
    return incident, impact


def test_synthetic_critic_is_not_independent_source_verification():
    original = analyze_and_critique(*_fixture())
    forged = analyze_and_critique(*_fixture("c" * 64, "d" * 64))
    assert original["critic"]["citations_valid"] is True
    assert forged["critic"]["citations_valid"] is True
    assert original["critic"]["disposition"] == forged["critic"]["disposition"]
    assert original["analyst"]["evidence_sha256"] != forged["analyst"]["evidence_sha256"]
    # This deliberately records a gap: no authoritative digest verification.
    for receipt in (original, forged):
        assert receipt["critic"]["root_cause_confirmed"] is False
        assert receipt["critic"]["runtime_attested"] is False
        assert receipt["policy_disposition"] == "DENY_LIVE"
        assert receipt["live_remediation_authorized"] is False
        assert receipt["runtime_attested"] is False


def test_missing_dependency_cannot_be_promoted_to_supported():
    incident, impact = _fixture()
    impact["impact_state"] = "UNKNOWN"
    impact["paths"] = []
    result = analyze_and_critique(incident, impact)
    assert result["critic"]["disposition"] == "NEEDS_MORE_EVIDENCE"
    assert result["analyst"]["missing_evidence"] == ["SOURCED_DEPENDENCY_PATH"]
    assert result["policy_disposition"] == "DENY_LIVE"
