"""Offline Analyst/Critic contracts; no LLM, network, or effects."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_event_correlation import InvalidEvent, correlate_events
from aiops2_digital_twin_impact import resolve_impact
from aiops2_analyst_critic import analyze_and_critique

NOW = "2026-11-15T12:00:00Z"


def inputs():
    events = [{"tenant_id": "acme", "source": "checkmk", "source_event_id": "san-1",
               "ci_id": "san-01", "service_id": "payments", "severity": "P1",
               "evidence_sha256": "a" * 64, "observed_at": "2026-11-15T11:59:00Z",
               "known_at": "2026-11-15T11:59:05Z"}]
    incident = correlate_events(events, as_of=NOW)["incidents"][0]
    edges = [{"tenant_id": "acme", "from_id": "san-01", "to_id": "payments",
              "source_id": "synthetic-cmdb", "evidence_sha256": "b" * 64,
              "observed_at": "2026-11-15T11:59:00Z"}]
    return incident, resolve_impact(incident, edges, as_of=NOW)


def test_sourced_hypothesis_is_not_confirmed_root_cause():
    incident, impact = inputs()
    result = analyze_and_critique(incident, impact)
    assert result["critic"]["disposition"] == "SUPPORTED_SYNTHETIC_HYPOTHESIS"
    assert result["analyst"]["evidence_sha256"] == ["a" * 64, "b" * 64]
    assert result["critic"]["root_cause_confirmed"] is False
    assert result["policy_disposition"] == "DENY_LIVE"
    assert result["live_remediation_authorized"] is False


def test_missing_path_fails_closed():
    incident, impact = inputs()
    impact["impact_state"] = "UNKNOWN"
    impact["paths"] = []
    result = analyze_and_critique(incident, impact)
    assert result["critic"]["disposition"] == "NEEDS_MORE_EVIDENCE"
    assert result["analyst"]["missing_evidence"] == ["SOURCED_DEPENDENCY_PATH"]


def test_cross_tenant_or_incident_mismatch_fails_closed():
    incident, impact = inputs()
    for field, value in (("tenant_id", "other"), ("incident_id", "other"), ("service_id", "other")):
        forged = copy.deepcopy(impact)
        forged[field] = value
        with pytest.raises(InvalidEvent):
            analyze_and_critique(incident, forged)


def test_forged_citation_and_unknown_with_path_rejected():
    incident, impact = inputs()
    forged = copy.deepcopy(impact)
    forged["paths"][0]["evidence_sha256"] = ["not-a-digest"]
    with pytest.raises(InvalidEvent):
        analyze_and_critique(incident, forged)
    forged = copy.deepcopy(impact)
    forged["impact_state"] = "UNKNOWN"
    with pytest.raises(InvalidEvent):
        analyze_and_critique(incident, forged)


def test_replay_is_deterministic_and_does_not_mutate_inputs():
    incident, impact = inputs()
    a, b = copy.deepcopy(incident), copy.deepcopy(impact)
    assert analyze_and_critique(incident, impact) == analyze_and_critique(a, b)
    assert incident == a and impact == b



def test_forged_path_start_not_in_incident_is_rejected():
    incident, impact = inputs()
    forged = copy.deepcopy(impact)
    forged["paths"][0]["nodes"][0] = "unrelated-ci"
    with pytest.raises(InvalidEvent, match="invalid impact path provenance"):
        analyze_and_critique(incident, forged)


def test_cyclic_forged_path_is_rejected():
    incident, impact = inputs()
    forged = copy.deepcopy(impact)
    forged["paths"][0]["nodes"] = ["san-01", "san-01", "payments"]
    forged["paths"][0]["evidence_sha256"] = ["b" * 64, "b" * 64]
    with pytest.raises(InvalidEvent, match="invalid impact path provenance"):
        analyze_and_critique(incident, forged)



@pytest.mark.parametrize("which,field,value", [
    ("incident", "runtime_attested", True),
    ("impact", "runtime_attested", True),
    ("incident", "live_remediation_authorized", True),
    ("impact", "live_remediation_authorized", True),
    ("incident", "runtime_attested", None),
    ("impact", "live_remediation_authorized", None),
])
def test_upstream_live_claims_and_missing_guards_fail_closed(which, field, value):
    incident, impact = inputs()
    forged_incident, forged_impact = copy.deepcopy(incident), copy.deepcopy(impact)
    (forged_incident if which == "incident" else forged_impact)[field] = value
    with pytest.raises(InvalidEvent, match="unqualified upstream"):
        analyze_and_critique(forged_incident, forged_impact)



@pytest.mark.parametrize("budget_value", [True, None, "false", 0])
def test_twin_budget_cannot_support_sourced_path_or_be_ambiguous(budget_value):
    incident, impact = inputs()
    forged = copy.deepcopy(impact)
    forged["resource_budget_exhausted"] = budget_value
    with pytest.raises(InvalidEvent, match="resource budget|exhausted impact budget"):
        analyze_and_critique(incident, forged)


def test_exhausted_twin_budget_keeps_unknown_and_requests_evidence():
    incident, impact = inputs()
    impact["resource_budget_exhausted"] = True
    impact["impact_state"] = "UNKNOWN"
    impact["paths"] = []
    result = analyze_and_critique(incident, impact)
    assert result["critic"]["disposition"] == "NEEDS_MORE_EVIDENCE"
    assert result["critic"]["root_cause_confirmed"] is False
    assert result["policy_disposition"] == "DENY_LIVE"
