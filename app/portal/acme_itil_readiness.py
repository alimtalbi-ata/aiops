"""Read-only ITIL progression readiness for the synthetic ACME incident.

A checkpoint contract is not a receipt. No stage is promoted to verified,
no ITIL ticket is closed, and no executor capability is emitted.
"""
from __future__ import annotations

from portal.acme_lifecycle_read_model import STAGES, build_synthetic_incident_lifecycle

REQUIRED = {
    "ACKNOWLEDGE_P1": ("detect", "correlate"),
    "DECLARE_BUSINESS_IMPACT": ("detect", "correlate", "enrich"),
    "PROPOSE_REMEDIATION": ("analyze", "ticket"),
    "REQUEST_HITL_APPROVAL": ("analyze", "ticket", "approve"),
    "SIMULATE_REMEDIATION": ("approve", "simulate"),
    "VERIFY_RECOVERY": ("simulate", "verify"),
    "RESOLVE_INCIDENT": ("ticket", "verify"),
    "CLOSE_ITIL_AND_OPEN_PIR": ("ticket", "verify", "close"),
}


def assess_synthetic_itil_readiness(lifecycle: dict) -> dict:
    if (not isinstance(lifecycle, dict)
            or lifecycle.get("schema") != "aiops.synthetic-incident-itil-lifecycle.v1"
            or lifecycle.get("mode") != "DEMO"
            or lifecycle.get("provenance") != "LOCAL_SYNTHETIC_FIXTURE"
            or lifecycle.get("overall_qualification") != "UNKNOWN"
            or lifecycle.get("runtime_attested") is not False
            or lifecycle.get("live_remediation_authorized") is not False
            or lifecycle.get("policy_disposition") != "DENY_LIVE_ACTION"
            or lifecycle.get("orchestration_effect_state") != "NO_EFFECT_RECEIPT"
            or lifecycle.get("postcheck_state") != "UNKNOWN"):
        raise ValueError("unqualified_itil_lifecycle")
    stages = lifecycle.get("stages")
    if (not isinstance(stages, list) or len(stages) != len(STAGES)):
        raise ValueError("unqualified_itil_stages")
    by_cue = {}
    for stage, (cue, phase, source) in zip(stages, STAGES):
        if (not isinstance(stage, dict)
                or stage.get("cue") != cue
                or stage.get("phase") != phase
                or stage.get("expected_source") != source
                or stage.get("evidence_state") != "UNKNOWN"
                or stage.get("runtime_attested") is not False
                or stage.get("operational_transition_authorized") is not False
                or stage.get("reason") != "INDEPENDENT_RUNTIME_EVIDENCE_MISSING"):
            raise ValueError("unqualified_itil_stage")
        by_cue[cue] = stage
    transitions = [
        {
            "transition": transition,
            "required_checkpoints": list(required),
            "missing_evidence": list(required),
            "readiness": "UNKNOWN",
            "authorized": False,
            "reason": "INDEPENDENT_RUNTIME_EVIDENCE_MISSING",
        }
        for transition, required in REQUIRED.items()
    ]
    return {
        "schema": "aiops.synthetic-itil-transition-readiness.v1",
        "mode": "DEMO",
        "source_sha256": lifecycle["source_sha256"],
        "source_incident_id": lifecycle["source_incident_id"],
        "business_impact_incident_id": lifecycle["business_impact_incident_id"],
        "transitions": transitions,
        "authorized_transition_count": 0,
        "missing_unique_checkpoints": [cue for cue, _, _ in STAGES],
        "missing_unique_checkpoint_count": len(STAGES),
        "next_operator_step": "COLLECT_INDEPENDENT_RUNTIME_EVIDENCE_READ_ONLY",
        "actual_glpi_ticket_updated": False,
        "temporal_execution_performed": False,
        "production_remediation_verified": False,
        "live_remediation_authorized": False,
    }


def build_synthetic_itil_readiness() -> dict:
    return assess_synthetic_itil_readiness(build_synthetic_incident_lifecycle())
