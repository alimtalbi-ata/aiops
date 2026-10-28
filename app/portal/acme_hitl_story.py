"""Read-only ACME HITL/Policy/Temporal storyboard projection.

This projects a *plan*, not an authenticated human decision, Policy HTTP
evaluation, Temporal workflow, sandbox receipt, postcheck or recovery proof.
No external I/O, no free-form commands and no effectful capability.
"""
from __future__ import annotations

import re
from typing import Any

from portal.acme_fixture_contract import SOURCE_INCIDENT_ID, TARGET_INCIDENT_ID
from shared.simulation_policy_contract import policy_command_for_mode

STATES = {
    "detect": "NOT_REACHED",
    "correlate": "NOT_REACHED",
    "enrich": "NOT_REACHED",
    "analyze": "NOT_REACHED",
    "ticket": "NOT_REACHED",
    "approve": "HUMAN_APPROVAL_REQUIRED",
    "simulate": "DRY_RUN_NOT_EXECUTED",
    "verify": "POSTCHECK_NOT_EXECUTED",
    "close": "RECOVERY_NOT_VERIFIED",
}


def project_hitl_story(model: dict[str, Any], cue: str) -> dict[str, Any]:
    """Refuse unqualified fixture metadata; preserve synthetic Run/Incident labels."""
    if type(model) is not dict or type(cue) is not str or cue not in STATES:
        raise ValueError("invalid HITL storyboard input")
    digest = model.get("source_sha256")
    if type(digest) is not str or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValueError("invalid synthetic fixture digest")
    if (model.get("provenance") != "SIMULATED_TARGET"
            or model.get("run_id") != "SIM-ACME-" + digest[:16].upper()
            or model.get("run_id_provenance") != "DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN"
            or model.get("incident_id") != SOURCE_INCIDENT_ID
            or model.get("impact_incident_id") != TARGET_INCIDENT_ID
            or model.get("ticket_id") is not None
            or model.get("event_timestamp_utc") is not None
            or model.get("runtime_evidence_present") is not False
            or model.get("runtime_attested") is not False
            or model.get("production_qualified") is not False
            or model.get("live_remediation_authorized") is not False):
        raise ValueError("unqualified HITL storyboard source")
    preview = model.get("decision_preview")
    if (type(preview) is not dict
            or preview.get("provider") != "DETERMINISTIC_RULES_NOT_LLM"
            or type(preview.get("policy")) is not dict
            or preview["policy"].get("decision") != "DENY_LIVE_ACTION"
            or preview.get("live_execution") is not False
            or preview.get("backend_writes") is not False):
        raise ValueError("unsafe policy preview")
    return {
        "schema": "aiops.acme-hitl-story.v1",
        "provenance": "SIMULATED_TARGET",
        "mode": "DEMO",
        "run_id": model["run_id"],
        "incident_id": SOURCE_INCIDENT_ID,
        "impact_incident_id": TARGET_INCIDENT_ID,
        "cue": cue,
        "story_state": STATES[cue],
        "policy_command": policy_command_for_mode("DEMO"),
        "policy_live_effect": "DENY_LIVE_ACTION",
        "policy_source": "DETERMINISTIC_PREVIEW_NOT_POLICY_HTTP",
        "policy_runtime_checked": False,
        "binding_status": "MISSING",
        "recipe_id": None,
        "target_id": None,
        "params_hash": None,
        "approval_id": None,
        "human_decision": "NOT_AUTHENTICATED",
        "temporal_workflow": "NOT_EXECUTED",
        "dry_run_receipt": None,
        "postchecks": "NOT_EXECUTED",
        "rollback": "DOCUMENTED_ONLY_NOT_EXECUTED",
        "recovery": "NOT_VERIFIED",
        "live_effect_authorized": False,
    }
