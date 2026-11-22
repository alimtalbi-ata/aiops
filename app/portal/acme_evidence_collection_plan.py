"""Non-executable evidence collection plan for the synthetic ACME incident.

A source/checkpoint mapping is a request for proof, never a receipt or a
grant to query external services. The portal performs no outbound calls.
"""
from __future__ import annotations

from portal.acme_itil_readiness import assess_synthetic_itil_readiness
from portal.acme_lifecycle_read_model import STAGES, build_synthetic_incident_lifecycle

# Independent proof must be reviewed before promoting any checkpoint.
EVIDENCE_REQUIREMENTS = {
    "detect": ("ALERT_STATE", "observed_at", "source_id", "content_sha256"),
    "correlate": ("CORRELATION_EVENT", "observed_at", "source_id", "content_sha256"),
    "enrich": ("SERVICE_DEPENDENCY_OBSERVATION", "observed_at", "source_id", "content_sha256"),
    "analyze": ("ANALYST_CRITIC_REVIEW", "observed_at", "source_id", "content_sha256"),
    "ticket": ("GLPI_AUTHENTICATED_TICKET_READBACK", "observed_at", "source_id", "content_sha256"),
    "approve": ("POLICY_AND_HITL_DECISION", "observed_at", "source_id", "content_sha256"),
    "simulate": ("ISOLATED_SIMULATOR_RECEIPT", "observed_at", "source_id", "content_sha256"),
    "verify": ("INDEPENDENT_POSTCHECK", "observed_at", "source_id", "content_sha256"),
    "close": ("GLPI_AUTHENTICATED_CLOSURE_AND_PIR_READBACK", "observed_at", "source_id", "content_sha256"),
}


def plan_synthetic_evidence_collection(lifecycle: dict) -> dict:
    readiness = assess_synthetic_itil_readiness(lifecycle)
    requests = []
    for cue, phase, source in STAGES:
        kind, *fields = EVIDENCE_REQUIREMENTS[cue]
        requests.append({
            "checkpoint": cue,
            "phase": phase,
            "expected_source": source,
            "required_evidence_type": kind,
            "required_metadata": fields,
            "collection_mode": "MANUAL_READ_ONLY_INDEPENDENT_REVIEW",
            "evidence_state": "MISSING",
            "submitted_evidence": None,
            "attested": False,
            "qualifies_runtime": False,
        })
    return {
        "schema": "aiops.synthetic-evidence-collection-plan.v1",
        "mode": "DEMO",
        "source_sha256": readiness["source_sha256"],
        "incident_id": readiness["source_incident_id"],
        "business_impact_incident_id": readiness["business_impact_incident_id"],
        "requests": requests,
        "requested_count": len(requests),
        "verified_count": 0,
        "evidence_acceptance_enabled": False,
        "outbound_collection_enabled": False,
        "glpi_write_enabled": False,
        "temporal_execution_enabled": False,
        "live_remediation_authorized": False,
    }


def build_synthetic_evidence_collection_plan() -> dict:
    return plan_synthetic_evidence_collection(build_synthetic_incident_lifecycle())
