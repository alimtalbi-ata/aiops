"""FS147 Temporal resume preflight: pure classifier; never sends signals."""
from dataclasses import dataclass
from enum import Enum


class ResumeDecision(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    ELIGIBLE_FOR_REVALIDATION = "ELIGIBLE_FOR_REVALIDATION"


@dataclass(frozen=True)
class ResumeEvidence:
    tenant_id: str
    alert_fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    ticket_id: int
    mode: str
    workflow_id: str
    workflow_run_id: str
    expected_workflow_id: str
    expected_workflow_run_id: str
    action_id: str
    approved_action_id: str
    policy: str
    native_hitl: str
    owner_id: str
    lease_owner_id: str
    fencing_token: int
    observed_fencing_token: int
    durable_outbox_state: str
    temporal_state: str
    authoritative_reads: bool
    lease_cas_verified: bool


def classify_resume(evidence):
    """Classify snapshots only. Positive result requires fresh transactional revalidation."""
    if not isinstance(evidence, ResumeEvidence):
        return ResumeDecision.UNKNOWN
    if evidence.mode == "LIVE" or (type(evidence.ticket_id) is int and evidence.ticket_id != 147):
        return ResumeDecision.DENIED
    if evidence.policy == "DENY" or evidence.native_hitl == "REJECTED":
        return ResumeDecision.DENIED
    if evidence.mode != "DEMO" or type(evidence.ticket_id) is not int:
        return ResumeDecision.UNKNOWN
    fields = ("tenant_id", "alert_fingerprint", "incident_id", "run_id",
              "evidence_id", "workflow_id", "workflow_run_id", "expected_workflow_id",
              "expected_workflow_run_id", "action_id", "approved_action_id",
              "owner_id", "lease_owner_id")
    for name in fields:
        value = getattr(evidence, name)
        if (type(value) is not str or not value or len(value) > 512
                or value != value.strip()
                or any(ord(ch) < 32 or ord(ch) == 127 or
                       0x200b <= ord(ch) <= 0x200f or
                       0x202a <= ord(ch) <= 0x202e or
                       0x2066 <= ord(ch) <= 0x2069 for ch in value)):
            return ResumeDecision.UNKNOWN
    if evidence.policy not in ("ALLOW", "DENY", "UNKNOWN"):
        return ResumeDecision.UNKNOWN
    if evidence.native_hitl not in ("ACCEPTED", "REJECTED", "PENDING", "UNKNOWN"):
        return ResumeDecision.UNKNOWN
    if evidence.policy == "UNKNOWN":
        return ResumeDecision.UNKNOWN
    if evidence.native_hitl in ("PENDING", "UNKNOWN"):
        return ResumeDecision.NEEDS_HUMAN
    if (evidence.action_id != evidence.approved_action_id
            or evidence.workflow_id != evidence.expected_workflow_id
            or evidence.workflow_run_id != evidence.expected_workflow_run_id):
        return ResumeDecision.DENIED
    if (type(evidence.fencing_token) is not int
            or type(evidence.observed_fencing_token) is not int
            or evidence.fencing_token <= 0 or evidence.observed_fencing_token <= 0):
        return ResumeDecision.UNKNOWN
    if (evidence.owner_id != evidence.lease_owner_id
            or evidence.fencing_token != evidence.observed_fencing_token):
        return ResumeDecision.DENIED
    if (type(evidence.authoritative_reads) is not bool
            or type(evidence.lease_cas_verified) is not bool
            or not evidence.authoritative_reads or not evidence.lease_cas_verified):
        return ResumeDecision.UNKNOWN
    # A crash after dispatch may leave a signal delivered but the outbox unacknowledged.
    # Never resend without authoritative reconciliation and unique signal identity.
    if evidence.durable_outbox_state != "READY":
        return ResumeDecision.UNKNOWN
    if evidence.temporal_state != "WAITING_FOR_HUMAN":
        return ResumeDecision.UNKNOWN
    return ResumeDecision.ELIGIBLE_FOR_REVALIDATION
