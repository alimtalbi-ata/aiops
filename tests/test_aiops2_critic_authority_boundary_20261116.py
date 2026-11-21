"""Synthetic Analyst/Critic trust-boundary regressions for PR #713.

These tests intentionally do NOT attest source authenticity, ACL, a separate
Critic process, LLM evaluation, GLPI, Temporal or a real ITIL integration.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import correlate_events
from aiops2_digital_twin_impact import resolve_impact
from aiops2_analyst_critic import analyze_and_critique

NOW = "2026-11-15T12:00:00Z"


def _fixture():
    events = [{
        "tenant_id": "acme", "source": "checkmk", "source_event_id": "san-1",
        "ci_id": "san-01", "service_id": "payments", "severity": "P1",
        "evidence_sha256": "a" * 64, "observed_at": "2026-11-15T11:59:00Z",
        "known_at": "2026-11-15T11:59:05Z",
    }]
    incident = correlate_events(events, as_of=NOW)["incidents"][0]
    edges = [{
        "tenant_id": "acme", "from_id": "san-01", "to_id": "payments",
        "source_id": "synthetic-cmdb", "evidence_sha256": "b" * 64,
        "observed_at": "2026-11-15T11:59:00Z",
    }]
    return incident, resolve_impact(incident, edges, as_of=NOW)


def _assert_no_effect(result):
    assert result["policy_disposition"] == "DENY_LIVE"
    assert result["live_remediation_authorized"] is False
    assert result["runtime_attested"] is False
    assert result["critic"]["root_cause_confirmed"] is False


def test_synthetic_supported_is_not_authoritative_evidence_or_independent_critic():
    incident, impact = _fixture()
    result = analyze_and_critique(incident, impact)
    assert result["critic"]["disposition"] == "SUPPORTED_SYNTHETIC_HYPOTHESIS"
    assert result["critic"]["citations_valid"] is True
    assert result["analyst"]["kind"] == "HYPOTHESIS_NOT_ROOT_CAUSE"
    # Citation membership alone does not prove that the digest is genuine.
    # No external ACL, source signature or independent invocation is checked.
    _assert_no_effect(result)


def test_attacker_controlled_digest_shape_cannot_grant_live_permission():
    incident, impact = _fixture()
    tampered = copy.deepcopy(incident)
    tampered["events"][0]["evidence_sha256"] = "f" * 64
    result = analyze_and_critique(tampered, impact)
    assert "f" * 64 in result["analyst"]["evidence_sha256"]
    # Explicitly document the gap: membership validates despite substitution.
    assert result["critic"]["citations_valid"] is True
    _assert_no_effect(result)


def test_missing_dependency_cannot_be_promoted_by_synthetic_critic():
    incident, impact = _fixture()
    impact["impact_state"] = "UNKNOWN"
    impact["paths"] = []
    result = analyze_and_critique(incident, impact)
    assert result["critic"]["disposition"] == "NEEDS_MORE_EVIDENCE"
    assert result["analyst"]["missing_evidence"] == ["SOURCED_DEPENDENCY_PATH"]
    _assert_no_effect(result)
