"""Side-effect-free Core gate: action-bound HITL and conditional Temporal resume.

ELIGIBLE is a local decision only; never a Temporal signal or LIVE authorization.
"""
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Admission:
    state: str
    reason: str


def admit_resume(intent: Mapping, policy: Mapping, approval: Mapping,
                 owner: Mapping, temporal: Mapping) -> Admission:
    records = (intent, policy, approval, owner, temporal)
    if any(not isinstance(x, Mapping) for x in records):
        return Admission("NEEDS_HUMAN", "invalid_contract")
    mode = intent.get("mode")
    if mode not in ("DEMO", "LIVE"):
        return Admission("NEEDS_HUMAN", "mode_unknown")
    keys = ("tenant_id", "run_id", "action_id", "action_digest")
    if any(type(intent.get(k)) is not str or not intent[k].strip()
           for k in (*keys, "incident_id", "fencing_token")):
        return Admission("NEEDS_HUMAN", "identity_unknown")
    epoch = intent.get("fencing_epoch")
    if type(epoch) is not int or epoch < 1:
        return Admission("NEEDS_HUMAN", "fence_unknown")
    for label, record in zip(("policy", "approval", "owner", "temporal"), records[1:]):
        if any(type(record.get(k)) is not str or record[k] != intent[k] for k in keys):
            return Admission("NEEDS_HUMAN", label + "_binding_mismatch")
    if policy.get("decision") != "ALLOW" or policy.get("mode") != mode:
        return Admission("DENIED", "policy_not_allow")
    # Approval must be an identifiable, action-specific native HITL decision
    # bound to the exact Policy decision, not a free-standing APPROVED flag.
    policy_id = policy.get("decision_id")
    if (type(policy_id) is not str or not policy_id.strip()
            or intent.get("policy_decision_id") != policy_id
            or approval.get("policy_decision_id") != policy_id):
        return Admission("NEEDS_HUMAN", "policy_decision_binding_unknown")
    if (approval.get("decision") != "APPROVED" or approval.get("mode") != mode
            or any(type(approval.get(k)) is not str or not approval[k].strip()
                   for k in ("approval_id", "approver_id"))):
        return Admission("NEEDS_HUMAN", "approval_not_bound")
    for label, record in (("owner", owner), ("temporal", temporal)):
        if (record.get("fencing_token") != intent["fencing_token"]
                or type(record.get("fencing_epoch")) is not int
                or record["fencing_epoch"] != epoch):
            return Admission("NEEDS_HUMAN", label + "_fence_mismatch")
    if owner.get("active") is not True:
        return Admission("NEEDS_HUMAN", "owner_not_active")
    if temporal.get("state") != "WAITING_APPROVAL" or temporal.get("resume_requested") is not False:
        return Admission("NEEDS_HUMAN", "temporal_not_resumable")
    if mode == "LIVE" and intent.get("live_preflight_verified") is not True:
        return Admission("NEEDS_HUMAN", "live_preflight_unknown")
    return Admission("ELIGIBLE", "all_guards_verified")
