"""Truthful adapter from the existing ACME fixture cockpit to the Team C journey contract.

This projects one deterministic STORY_OFFLINE Run/attempt identity. It does not
create a Core Run, invoke Temporal/HITL, issue a receipt, or mark any stage PASS.
"""
from __future__ import annotations

STAGES = (
    "capability_simulator", "capability_core", "capability_twin",
    "capability_policy", "capability_worker", "simulator_start",
    "pre_resolution_core", "pre_resolution_twin", "pre_resolution_policy",
    "pre_resolution_worker", "worker_no_effect", "core_finalization",
    "post_resolution_core", "post_resolution_twin", "post_resolution_policy",
    "post_resolution_worker", "resolved",
)


def project_team_c_run_journey(impact: dict, cockpit: dict) -> dict:
    if not isinstance(impact, dict) or not isinstance(cockpit, dict):
        raise ValueError("run_journey_projection_requires_existing_views")
    twin = impact.get("twin_evidence")
    consumer = cockpit.get("twin_consumer")
    if (not isinstance(twin, dict) or not isinstance(consumer, dict)
            or twin.get("scope") != "STORY_OFFLINE"
            or twin.get("binding_status") != "UNBOUND"
            or twin.get("tenant_id") is not None
            or twin.get("attempt_id") is not None
            or twin.get("core_run_id") is not None
            or twin.get("runtime_attested") is not False
            or twin.get("live_remediation_authorized") is not False):
        raise ValueError("run_journey_source_not_unbound_story_fixture")
    source_sha256 = impact.get("source_sha256")
    if (not isinstance(source_sha256, str) or len(source_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in source_sha256)
            or source_sha256 != twin.get("source_sha256")
            or source_sha256 != cockpit.get("source_sha256")):
        raise ValueError("run_journey_source_digest_mismatch")
    run_id = twin.get("run_id")
    expected_run_id = "SIM-ACME-" + source_sha256[:16].upper()
    if run_id != expected_run_id or consumer.get("story_identity", {}).get("run_id") != run_id:
        raise ValueError("run_journey_run_identity_mismatch")
    attempt_id = "ACME-SIM-" + source_sha256[:16].upper()
    incident_id = cockpit.get("incident_id")
    if not isinstance(incident_id, str) or not incident_id:
        raise ValueError("run_journey_incident_missing")
    preview = impact.get("decision_preview")
    if not isinstance(preview, dict):
        raise ValueError("run_journey_decision_preview_missing")
    analyst = preview.get("analyst", {})
    critic = preview.get("critic", {})
    policy = preview.get("policy", {})
    if (preview.get("provider") != "DETERMINISTIC_RULES_NOT_LLM"
            or analyst.get("status") != "HYPOTHESIS_ONLY"
            or critic.get("decision") != "HOLD_FOR_HUMAN_REVIEW"
            or policy.get("decision") != "DENY_LIVE_ACTION"
            or preview.get("live_execution") is not False
            or preview.get("backend_writes") is not False):
        raise ValueError("run_journey_intelligence_or_policy_unqualified")
    citations = consumer.get("hypothesis_citations", [])
    evidence_refs = sorted({
        item.get("source_ref") for item in citations
        if isinstance(item, dict) and isinstance(item.get("source_ref"), str)
    })
    if not evidence_refs:
        raise ValueError("run_journey_evidence_refs_missing")
    return {
        "schema": "aiops.team-c.san-payments-run-journey.v2",
        "scope": "STORY_OFFLINE",
        "mode": "DEMO",
        "run": {
            "run_id": run_id,
            "attempt_id": attempt_id,
            "incident_id": incident_id,
            "tenant_id": None,
            "scenario_id": "ACME-SAN-PAYMENTS",
            "executed_sha": None,
            "idempotency_key": attempt_id,
        },
        "intelligence": {
            "provider": "DETERMINISTIC_RULES_NOT_LLM",
            "analyst_status": "HYPOTHESIS_ONLY",
            "hypotheses": [{
                "claim": analyst["summary"],
                "confidence": None,
                "evidence_refs": evidence_refs,
            }],
            "critic_disposition": "HOLD_FOR_HUMAN_REVIEW",
            "objections": [critic.get("reason", "Independent runtime evidence is missing.")],
            "critic_independently_verified": False,
            "evidence_refs": evidence_refs,
        },
        "policy": {
            "decision": "DENY_LIVE_ACTION",
            "reason_codes": ["RUNTIME_EVIDENCE_MISSING", "LIVE_ACTION_DISABLED"],
            "execution_allowed": False,
            "effect_allowed": False,
        },
        "hitl": {
            "kind": "SIMULATED_NOT_REQUESTED",
            "approval_id": None,
            "issuer": "TWIN_ACME_SIMULATED",
            "human_approval_claimed": False,
            "simulated_only": True,
        },
        "worker": {
            "executor": "NOT_INVOKED",
            "workflow_id": None,
            "task_queue": None,
            "isolated": True,
            "no_effect": True,
            "runtime_attested": False,
        },
        "receipt": None,
        "stage_plan": [{
            "stage": stage,
            "status": "NOT_RUN",
            "evidence_state": "MISSING",
            "run_id": run_id,
            "attempt_id": attempt_id,
            "sha256": None,
            "observed_at": None,
        } for stage in STAGES],
        "provenance": {
            "source_kind": "LOCAL_SYNTHETIC_FIXTURE",
            "source_sha256": source_sha256,
            "source_git_sha": None,
            "expected_sha": None,
            "collected_at": None,
        },
    }
