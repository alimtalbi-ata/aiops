"""Offline vertical slice: synthetic events -> correlation -> Twin -> Analyst/Critic.

Produces a JSON-serializable NOC decision projection, never a LIVE attestation.
"""
from __future__ import annotations

from aiops2_event_correlation import correlate_events
from aiops2_digital_twin_impact import resolve_impact
from aiops2_analyst_critic import analyze_and_critique


def build_noc_decision(events: list, edges: list, *, as_of: str) -> dict:
    """Build tenant-isolated, evidence-bound synthetic decision projections."""
    correlated = correlate_events(events, as_of=as_of)
    decisions = []
    for incident in correlated["incidents"]:
        impact = resolve_impact(incident, edges, as_of=as_of)
        intelligence = analyze_and_critique(incident, impact)
        decisions.append({
            "incident_id": incident["incident_id"],
            "tenant_id": incident["tenant_id"],
            "service_id": incident["service_id"],
            "priority": incident["priority"],
            "event_count": incident["event_count"],
            "incident_ci_ids": sorted({event["ci_id"] for event in incident["events"]}),
            "resource_budget_exhausted": impact["resource_budget_exhausted"],
            "impact_state": impact["impact_state"],
            "impact_paths": impact["paths"],
            "rejected_edges": impact["rejected_edges"],
            "analyst": intelligence["analyst"],
            "critic": intelligence["critic"],
            "policy_disposition": "DENY_LIVE",
            "next_noc_action": (
                "REVIEW_SYNTHETIC_EVIDENCE"
                if intelligence["critic"]["disposition"] == "SUPPORTED_SYNTHETIC_HYPOTHESIS"
                else "RETRY_WITH_BOUNDED_SYNTHETIC_GRAPH" if impact["resource_budget_exhausted"]
                else "COLLECT_MISSING_DEPENDENCY_EVIDENCE"
            ),
            "runtime_attested": False,
            "live_remediation_authorized": False,
        })
    return {
        "schema": "aiops2.synthetic-noc-decision.v1",
        "mode": "SIMULATION",
        "scope": "OFFLINE_NO_EXTERNAL_IO",
        "decisions": decisions,
        "rejected_events": correlated["rejected"],
        "runtime_attested": False,
        "live_remediation_authorized": False,
    }
