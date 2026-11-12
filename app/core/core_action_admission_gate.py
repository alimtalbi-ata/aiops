"""Fail-closed action admission supplement to the read-only Core lineage gate.

Qualification is not an authorization to execute. No IO or side effects.
"""
from dataclasses import dataclass
from enum import Enum
from .core_lineage_gate import Receipt, Verdict, evaluate


class Admission(str, Enum):
    DENIED = "DENIED"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    UNKNOWN = "UNKNOWN"
    ELIGIBLE_FOR_REVALIDATION = "ELIGIBLE_FOR_REVALIDATION"


@dataclass(frozen=True)
class ActionProof:
    tenant_id: str
    run_id: str
    action_id: str
    action_digest: str
    policy_state: str
    hitl_state: str
    hitl_action_id: str
    hitl_action_digest: str
    owner_id: str
    observed_owner_id: str
    fencing_token: str
    observed_fencing_token: str
    temporal_state: str
    temporal_reconciled: bool


def admit(receipt: object, proof: object) -> Admission:
    """Classify a candidate only; the Worker must revalidate authoritative state."""
    if isinstance(receipt, Receipt) and receipt.mode == "LIVE":
        return Admission.DENIED
    if isinstance(proof, ActionProof):
        if proof.policy_state in ("DENY", "STOP_AUTO") or proof.hitl_state == "REJECTED":
            return Admission.DENIED
        if proof.hitl_state in ("PENDING", "UNKNOWN"):
            return Admission.NEEDS_HUMAN
    if not isinstance(receipt, Receipt) or not isinstance(proof, ActionProof):
        return Admission.UNKNOWN
    if evaluate(receipt).verdict != Verdict.PASS or not receipt.execution_expected:
        return Admission.UNKNOWN
    if proof.policy_state != "ALLOW" or proof.hitl_state != "APPROVED":
        return Admission.UNKNOWN
    fields = (proof.tenant_id, proof.run_id, proof.action_id, proof.action_digest,
              proof.hitl_action_id, proof.hitl_action_digest, proof.owner_id,
              proof.observed_owner_id, proof.fencing_token, proof.observed_fencing_token)
    if any(type(x) is not str or not x.strip() for x in fields):
        return Admission.UNKNOWN
    if (proof.tenant_id != receipt.tenant_id or proof.run_id != receipt.run_id
            or proof.action_id != receipt.action_id
            or proof.hitl_action_id != proof.action_id
            or proof.hitl_action_digest != proof.action_digest
            or proof.owner_id != proof.observed_owner_id
            or proof.fencing_token != proof.observed_fencing_token):
        return Admission.DENIED
    if type(proof.temporal_reconciled) is not bool or not proof.temporal_reconciled:
        return Admission.UNKNOWN
    if proof.temporal_state != "RECONCILED_SAFE_TO_RESUME":
        return Admission.UNKNOWN
    return Admission.ELIGIBLE_FOR_REVALIDATION
