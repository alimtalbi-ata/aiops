"""Deterministic safety policy. No model output can bypass these rules."""
from typing import Any
VALID_SEVERITIES = {"P1", "P2", "P3", "P4"}
HIGH_RISK = {"restart", "failover", "delete", "rollback", "power_off", "fence", "change_config"}

def evaluate(incident: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    severity = str(analysis.get("severity", "UNKNOWN")).upper()
    confidence = analysis.get("confidence", 0.0)
    evidence = analysis.get("evidence", [])
    action = str(analysis.get("proposed_action", "observe")).lower()
    reasons: list[str] = []
    if severity not in VALID_SEVERITIES: reasons.append("severity_unknown")
    if not isinstance(confidence, (float, int)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        confidence = 0.0
        reasons.append("confidence_invalid")
    if not isinstance(evidence, list) or not evidence: reasons.append("evidence_missing")
    if severity == "P1": reasons.append("p1_must_escalate")
    if any(word in action for word in HIGH_RISK): reasons.append("high_risk_action_requires_human_approval")
    if confidence < 0.75: reasons.append("confidence_below_0_75")
    if severity == "P1" or "severity_unknown" in reasons or "evidence_missing" in reasons:
        decision = "ESCALATE"
    elif "high_risk_action_requires_human_approval" in reasons or confidence < 0.75:
        decision = "HUMAN_APPROVAL"
    else: decision = "OBSERVE"
    return {"decision": decision, "policy_version": "2.0.0",
            "automatic_remediation_allowed": False, "reasons": reasons or ["advisory_only"]}