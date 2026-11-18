"""Cross-check deterministic Analyst/Critic preview against missing independent proof.

This is a synthetic decision trace, not a model invocation or remediation permit.
"""
from __future__ import annotations

from portal.acme_lifecycle_read_model import project_synthetic_incident_lifecycle
from portal.acme_evidence_collection_plan import plan_synthetic_evidence_collection


def review_synthetic_analyst_critic(impact: dict) -> dict:
    lifecycle = project_synthetic_incident_lifecycle(impact)
    plan = plan_synthetic_evidence_collection(lifecycle)
    decision = impact.get("decision_preview")
    if (not isinstance(decision, dict)
            or decision.get("provider") != "DETERMINISTIC_RULES_NOT_LLM"
            or decision.get("live_execution") is not False
            or decision.get("backend_writes") is not False
            or not isinstance(decision.get("analyst"), dict)
            or decision["analyst"].get("status") != "HYPOTHESIS_ONLY"
            or not isinstance(decision["analyst"].get("summary"), str)
            or not decision["analyst"]["summary"]
            or not isinstance(decision["analyst"].get("next_checks"), list)
            or not all(isinstance(x, str) and x for x in decision["analyst"]["next_checks"])
            or not isinstance(decision.get("critic"), dict)
            or decision["critic"].get("decision") != "HOLD_FOR_HUMAN_REVIEW"
            or not isinstance(decision.get("policy"), dict)
            or decision["policy"].get("decision") != "DENY_LIVE_ACTION"):
        raise ValueError("unqualified_analyst_critic_preview")
    missing = {r["checkpoint"] for r in plan["requests"]}
    if not {"analyze", "verify", "approve"} <= missing:
        raise ValueError("missing_independent_review_gates")
    return {
        "schema": "aiops.synthetic-analyst-critic-evidence-review.v1",
        "twin_consumer": lifecycle["twin_consumer"],
        "mode": "DEMO",
        "source_sha256": plan["source_sha256"],
        "incident_id": plan["incident_id"],
        "analysis_kind": "DETERMINISTIC_HYPOTHESIS_NOT_LLM",
        "analyst_status": "HYPOTHESIS_ONLY",
        "critic_disposition": "HOLD_FOR_HUMAN_REVIEW",
        "critic_independently_verified": False,
        "citation_provenance": "LOCAL_SYNTHETIC_FIXTURE_ONLY",
        "runtime_citations_verified": 0,
        "missing_review_checkpoints": ["analyze", "approve", "verify"],
        "policy_disposition": "DENY_LIVE_ACTION",
        "human_approval_verified": False,
        "simulation_execution_verified": False,
        "independent_postcheck_verified": False,
        "operational_decision_authorized": False,
        "live_remediation_authorized": False,
    }
