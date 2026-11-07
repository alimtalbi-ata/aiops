"""FS147 launch admission: pure, fail-closed boundary, no side effects.

A positive identity check is not a permission to dispatch a Temporal signal.
Authoritative adapters must revalidate each attestation and commit a PG16 CAS
outbox transaction before any downstream effect.
"""
from dataclasses import dataclass
from enum import Enum


class LaunchDecision(str, Enum):
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    ELIGIBLE_FOR_REVALIDATION = "ELIGIBLE_FOR_REVALIDATION"


@dataclass(frozen=True)
class LaunchEvidence:
    tenant_id: str
    alert_fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    ticket_id: int
    mode: str
    action_id: str
    action_path: str
    idempotency_key: str
    policy: str
    native_hitl: str
    approval_action_id: str
    approval_run_id: str
    approval_ticket_id: int
    approval_path: str
    owner_id: str
    lease_owner_id: str
    fencing_token: int
    observed_fencing_token: int
    temporal_state: str
    authoritative_reads: bool
    lease_cas_verified: bool


def classify_launch(value):
    """Classify supplied evidence only; NEVER perform launch/resume."""
    if not isinstance(value, LaunchEvidence):
        return LaunchDecision.UNKNOWN
    if value.mode == "LIVE" or (type(value.ticket_id) is int and value.ticket_id != 147):
        return LaunchDecision.DENIED
    if value.policy == "DENY" or value.native_hitl == "REJECTED":
        return LaunchDecision.DENIED
    if value.mode != "DEMO" or type(value.ticket_id) is not int:
        return LaunchDecision.UNKNOWN
    fields = ("tenant_id", "alert_fingerprint", "incident_id", "run_id",
              "evidence_id", "action_id", "action_path", "idempotency_key",
              "owner_id", "lease_owner_id", "approval_action_id",
              "approval_run_id", "approval_path")
    if any(type(getattr(value, key)) is not str or
           not getattr(value, key) or
           getattr(value, key).strip() != getattr(value, key) or
           len(getattr(value, key)) > 512 or
           any(ord(ch) < 32 or ord(ch) == 127 for ch in getattr(value, key))
           for key in fields):
        return LaunchDecision.UNKNOWN
    if value.policy not in {"ALLOW", "DENY", "UNKNOWN"}:
        return LaunchDecision.UNKNOWN
    if value.native_hitl not in {"ACCEPTED", "REJECTED", "PENDING", "UNKNOWN"}:
        return LaunchDecision.UNKNOWN
    if value.policy == "UNKNOWN":
        return LaunchDecision.UNKNOWN
    if value.native_hitl in {"PENDING", "UNKNOWN"}:
        return LaunchDecision.NEEDS_HUMAN
    if type(value.approval_ticket_id) is not int:
        return LaunchDecision.UNKNOWN
    if (value.approval_ticket_id != 147 or
        value.approval_action_id != value.action_id or
        value.approval_run_id != value.run_id or
        value.approval_path != value.action_path):
        return LaunchDecision.DENIED
    if (type(value.fencing_token) is not int or
        type(value.observed_fencing_token) is not int or
        value.fencing_token <= 0 or value.observed_fencing_token <= 0):
        return LaunchDecision.UNKNOWN
    if value.owner_id != value.lease_owner_id or value.fencing_token != value.observed_fencing_token:
        return LaunchDecision.DENIED
    if type(value.authoritative_reads) is not bool or type(value.lease_cas_verified) is not bool:
        return LaunchDecision.UNKNOWN
    if not value.authoritative_reads or not value.lease_cas_verified:
        return LaunchDecision.UNKNOWN
    if value.temporal_state in {"DISPATCHING", "UNCERTAIN", "DELIVERED"}:
        return LaunchDecision.UNKNOWN
    if value.temporal_state != "PENDING":
        return LaunchDecision.UNKNOWN
    return LaunchDecision.ELIGIBLE_FOR_REVALIDATION
