"""Identity-bound, side-effect-free entrypoint for FS DEMO.

The caller must fetch Evidence and Policy from their real services and enforce
OIDC/actor ACL. This module does not establish authenticity of either response.
"""
from typing import Mapping
from worker.fs_debian_stage_contract import StageDecision, decide_fs_stage

IDENTITY_KEYS = ("tenant_id", "incident_id", "run_id")


def decide_bound_fs_stage(
    *, scenario: str, mode: str, stage: str,
    expected: Mapping, evidence: Mapping | None,
    policy: Mapping | None = None, stop_auto: bool = False,
) -> StageDecision:
    """Reject cross-run/tenant evidence and policy, even with PASS verdicts."""
    if scenario != "FS-DEBIAN-SYNTHETIC" or mode != "DEMO":
        return StageDecision("NOT_APPLICABLE", None, reason="other_scenario")
    if stop_auto:
        return StageDecision("BLOCKED", None, reason="stop_auto")
    if not isinstance(expected, Mapping) or any(
        not isinstance(expected.get(k), str) or not expected[k]
        for k in IDENTITY_KEYS
    ):
        return StageDecision("BLOCKED", None, reason="expected_identity_missing")
    if not isinstance(evidence, Mapping) or any(
        evidence.get(k) != expected[k] for k in IDENTITY_KEYS
    ):
        return StageDecision("BLOCKED", None, reason="evidence_identity_mismatch")
    # An explicitly selected Evidence record cannot be substituted by another\n    # record from the same tenant/incident/run.\n    if "evidence_id" in expected and (\n        not isinstance(expected["evidence_id"], str)\n        or not expected["evidence_id"]\n        or evidence.get("evidence_id") != expected["evidence_id"]\n    ):\n        return StageDecision("BLOCKED", None, reason="evidence_record_mismatch")\n    if stage == "POLICY" and (
        not isinstance(policy, Mapping)
        or any(policy.get(k) != expected[k] for k in IDENTITY_KEYS)
    ):
        return StageDecision("BLOCKED", None, reason="policy_identity_mismatch")
    return decide_fs_stage(
        scenario=scenario, mode=mode, stage=stage,
        evidence=evidence, policy=policy, stop_auto=stop_auto,
    )
