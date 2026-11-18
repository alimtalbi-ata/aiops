"""Synthetic incident-to-ITIL lifecycle projection; no operational side effects.

Every stage is an explicit contract, not a runtime observation. This model
never promotes missing evidence to success or simulation to LIVE authority.
"""
from __future__ import annotations

from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_twin_consumer import project_twin_consumer

STAGES = (
    ("detect", "OBSERVABILITY", "grafana"),
    ("correlate", "INCIDENT_CORRELATION", "n8n"),
    ("enrich", "BUSINESS_IMPACT", "n8n"),
    ("analyze", "ANALYST_CRITIC", "n8n"),
    ("ticket", "ITIL_INCIDENT", "glpi"),
    ("approve", "POLICY_HITL", "glpi"),
    ("simulate", "ORCHESTRATION", "n8n"),
    ("verify", "INDEPENDENT_VERIFICATION", "grafana"),
    ("close", "ITIL_PROBLEM_PIR", "glpi"),
)


def project_synthetic_incident_lifecycle(impact: dict) -> dict:
    if (not isinstance(impact, dict)
            or impact.get("schema") != "aiops.synthetic-impact-read-model.v1"
            or impact.get("provenance") != "SIMULATED_TARGET"
            or impact.get("runtime_evidence_present") is not False
            or impact.get("runtime_attested") is not False
            or impact.get("production_qualified") is not False
            or impact.get("live_remediation_authorized") is not False
            or impact.get("ticket_id") is not None
            or impact.get("event_timestamp_utc") is not None
            or not isinstance(impact.get("source_sha256"), str)
            or len(impact["source_sha256"]) != 64):
        raise ValueError("unqualified_synthetic_impact")
    checkpoints = impact.get("checkpoint_evidence")
    if (not isinstance(checkpoints, list) or len(checkpoints) != len(STAGES)):
        raise ValueError("invalid_lifecycle_checkpoints")
    result = []
    for checkpoint, (cue, phase, service) in zip(checkpoints, STAGES):
        if (not isinstance(checkpoint, dict)
                or checkpoint.get("cue") != cue
                or checkpoint.get("service") != service
                or checkpoint.get("status") != "MISSING"
                or checkpoint.get("runtime_authenticated") is not False
                or checkpoint.get("screenshot_sha256") is not None
                or checkpoint.get("event_timestamp_utc") is not None):
            raise ValueError("unqualified_lifecycle_checkpoint")
        result.append({
            "phase": phase,
            "cue": cue,
            "expected_source": service,
            "evidence_state": "UNKNOWN",
            "runtime_attested": False,
            "operational_transition_authorized": False,
            "reason": "INDEPENDENT_RUNTIME_EVIDENCE_MISSING",
        })
    twin = project_twin_consumer(impact)
    if impact.get("twin_consumer") != twin:
        raise ValueError("twin_consumer_mismatch")
    return {
        "schema": "aiops.synthetic-incident-itil-lifecycle.v1",
        "twin_consumer": twin,
        "mode": "DEMO",
        "provenance": "LOCAL_SYNTHETIC_FIXTURE",
        "source_sha256": impact["source_sha256"],
        "source_incident_id": impact["incident_id"],
        "business_impact_incident_id": impact["impact_incident_id"],
        "business_impact_path": list(impact["impact_path"]),
        "stages": result,
        "overall_qualification": "UNKNOWN",
        "itil_ticket_state": "UNKNOWN_NO_AUTHENTICATED_GLPI_READBACK",
        "analyst_critic_state": "HYPOTHESIS_NOT_RUNTIME_VERIFIED",
        "policy_disposition": "DENY_LIVE_ACTION",
        "hitl_approval_state": "NOT_VERIFIED",
        "orchestration_effect_state": "NO_EFFECT_RECEIPT",
        "postcheck_state": "UNKNOWN",
        "pir_problem_state": "NOT_VERIFIED",
        "runtime_attested": False,
        "live_remediation_authorized": False,
    }


def build_synthetic_incident_lifecycle() -> dict:
    return project_synthetic_incident_lifecycle(build_acme_impact_read_model())
