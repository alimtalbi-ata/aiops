"""Unified read-only DEMO incident cockpit with cross-projection consistency checks.

All views derive from the same validated fixture snapshot, never separate reads.
No runtime proof, authenticated user action or execution capability is implied.
"""
from __future__ import annotations

from portal.acme_lifecycle_read_model import project_synthetic_incident_lifecycle
from portal.acme_itil_readiness import assess_synthetic_itil_readiness
from portal.acme_evidence_collection_plan import plan_synthetic_evidence_collection
from portal.acme_analyst_critic_review import review_synthetic_analyst_critic


def project_synthetic_incident_cockpit(impact: dict) -> dict:
    lifecycle = project_synthetic_incident_lifecycle(impact)
    readiness = assess_synthetic_itil_readiness(lifecycle)
    evidence = plan_synthetic_evidence_collection(lifecycle)
    review = review_synthetic_analyst_critic(impact)
    views = (lifecycle, readiness, evidence, review)
    if (any(view.get("source_sha256") != lifecycle["source_sha256"] for view in views)
            or any(view.get("mode") != "DEMO" for view in views)
            or readiness.get("source_incident_id") != evidence.get("incident_id")
            or evidence.get("incident_id") != review.get("incident_id")
            or lifecycle.get("source_incident_id") != evidence.get("incident_id")
            or evidence.get("business_impact_incident_id") != readiness.get("business_impact_incident_id")
            or readiness.get("authorized_transition_count") != 0
            or evidence.get("verified_count") != 0
            or review.get("runtime_citations_verified") != 0
            or review.get("policy_disposition") != "DENY_LIVE_ACTION"
            or evidence.get("outbound_collection_enabled") is not False
            or evidence.get("temporal_execution_enabled") is not False):
        raise ValueError("synthetic_cockpit_projection_mismatch")
    return {
        "schema": "aiops.synthetic-incident-cockpit.v1",
        "twin_consumer": lifecycle["twin_consumer"],
        "mode": "DEMO",
        "provenance": "LOCAL_SYNTHETIC_FIXTURE",
        "source_sha256": lifecycle["source_sha256"],
        "incident_id": lifecycle["source_incident_id"],
        "business_impact_incident_id": lifecycle["business_impact_incident_id"],
        "business_impact_path": lifecycle["business_impact_path"],
        "lifecycle": lifecycle,
        "itil_readiness": readiness,
        "evidence_plan": evidence,
        "analyst_critic_review": review,
        "runtime_attested": False,
        "live_remediation_authorized": False,
        "overall_qualification": "UNKNOWN",
    }
