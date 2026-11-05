"""Fail-closed FS DEMO routing contract; NOT wired to the Debian active Worker.

This pure function deliberately has no network, Temporal or GLPI side effects.
The active Debian candidate must be reconciled against its divergent image
before the caller can use this contract.
"""
from dataclasses import dataclass
from typing import Mapping

FS_SCENARIO = "FS-DEBIAN-SYNTHETIC"
FS_STAGES = ("OBSERVE", "DGX_ANALYST", "DGX_CRITIC", "POLICY")


@dataclass(frozen=True)
class StageDecision:
    status: str
    next_stage: str | None
    effect_allowed: bool = False
    resolve_allowed: bool = False
    reason: str = ""


def decide_fs_stage(
    *, scenario: str, mode: str, stage: str,
    evidence: Mapping | None, policy: Mapping | None = None,
    stop_auto: bool = False,
) -> StageDecision:
    """Accept only independently fetched Evidence and Policy verdicts.

    No synthetic evidence is created. Caller must authenticate/authorize and
    bind evidence to the current tenant, incident and run before invoking.
    """
    if scenario != FS_SCENARIO or mode != "DEMO":
        return StageDecision("NOT_APPLICABLE", None, reason="other_scenario")
    if stop_auto:
        return StageDecision("BLOCKED", None, reason="stop_auto")
    if stage not in FS_STAGES:
        return StageDecision("BLOCKED", None, reason="unknown_stage")
    if not isinstance(evidence, Mapping):
        return StageDecision("BLOCKED", None, reason="evidence_missing")
    if evidence.get("verified") is not True or evidence.get("synthetic") is not True:
        return StageDecision("BLOCKED", None, reason="evidence_unqualified")
    if not all(isinstance(evidence.get(k), str) and evidence[k] for k in
               ("tenant_id", "incident_id", "run_id", "evidence_id")):
        return StageDecision("BLOCKED", None, reason="evidence_identity_missing")
    if stage == "POLICY":
        if not isinstance(policy, Mapping):
            return StageDecision("BLOCKED", None, reason="policy_unavailable")
        if policy.get("state") != "PASS" or policy.get("decision") != "SIMULATE":
            return StageDecision("BLOCKED", None, reason="policy_refused_or_non_synthetic")
        return StageDecision("NO_EFFECT", None, reason="policy_pass_no_remediation")
    return StageDecision("CONTINUE", FS_STAGES[FS_STAGES.index(stage) + 1])
