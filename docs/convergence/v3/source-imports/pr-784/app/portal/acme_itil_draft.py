"""Generate an inert ITIL incident handoff draft from one qualified DEMO snapshot.

The draft is a review artifact, not a GLPI REST payload or a write capability.
"""
from __future__ import annotations

import hashlib
import json

from portal.acme_incident_cockpit import project_synthetic_incident_cockpit


def build_synthetic_itil_handoff_draft(impact: dict) -> dict:
    cockpit = project_synthetic_incident_cockpit(impact)
    if (cockpit["evidence_plan"]["verified_count"] != 0
            or cockpit["itil_readiness"]["authorized_transition_count"] != 0
            or cockpit["analyst_critic_review"]["policy_disposition"] != "DENY_LIVE_ACTION"):
        raise ValueError("itil_draft_requires_unqualified_demo")
    incident = cockpit["incident_id"]
    affected = cockpit["business_impact_incident_id"]
    path = cockpit["business_impact_path"]
    if (not isinstance(path, list) or not 2 <= len(path) <= 32
            or not all(isinstance(node, str) and 1 <= len(node) <= 128 for node in path)):
        raise ValueError("invalid_impact_path")
    content = {
        "title": "DEMO ONLY — SAN P1 / Payments P2 — revue humaine requise",
        "source_incident": incident,
        "affected_business_incident": affected,
        "business_impact_path": list(path),
        "priority_proposal": "P1_SOURCE_WITH_P2_BUSINESS_IMPACT",
        "analysis_status": "HYPOTHESIS_ONLY",
        "critic_status": "HOLD_FOR_HUMAN_REVIEW",
        "policy_status": "DENY_LIVE_ACTION",
        "required_evidence": [r["checkpoint"] for r in cockpit["evidence_plan"]["requests"]],
        "operator_next_step": "COLLECT_INDEPENDENT_RUNTIME_EVIDENCE_READ_ONLY",
        "resolution_status": "NOT_RESOLVED",
        "pir_status": "NOT_OPENED",
    }
    digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "schema": "aiops.synthetic-itil-handoff-draft.v1",
        "mode": "DEMO",
        "provenance": "LOCAL_SYNTHETIC_FIXTURE",
        "source_sha256": cockpit["source_sha256"],
        "draft_sha256": digest,
        "content": content,
        "glpi_ticket_id": None,
        "glpi_payload": None,
        "glpi_write_performed": False,
        "human_approved": False,
        "independent_evidence_verified": False,
        "itil_transition_authorized": False,
        "live_remediation_authorized": False,
    }
