"""FS.364 deterministic, side-effect-free correlation admission.

A storage adapter must enforce UNIQUE(tenant_id, idempotency_key) atomically.
This module does not create GLPI tickets, runs or Temporal signals.
"""
from dataclasses import dataclass
from .fs364_outbox_envelope import ResumeEnvelope


@dataclass(frozen=True)
class AdmissionResult:
    status: str
    envelope: ResumeEnvelope | None


def admit_correlation(proposed: ResumeEnvelope, existing: ResumeEnvelope | None) -> AdmissionResult:
    """Return NEW, REPLAY or CONFLICT; never mutate either input.

    REPLAY requires byte-for-byte equivalent typed identity, not just a key.
    The caller must verify the ticket by authenticated read and persist with
    a transaction/unique constraint; NEW is not authorization to dispatch.
    """
    if not isinstance(proposed, ResumeEnvelope):
        return AdmissionResult("CONFLICT", None)
    fields = (
        "alert_fingerprint", "incident_id", "run_id", "evidence_id",
        "tenant_id", "idempotency_key", "state_version", "policy_version",
    )
    if any(
        not isinstance(getattr(proposed, name), str)
        or not getattr(proposed, name)
        or getattr(proposed, name) != getattr(proposed, name).strip()
        or not getattr(proposed, name).isprintable()
        or any(ch.isspace() for ch in getattr(proposed, name))
        for name in fields
    ):
        return AdmissionResult("CONFLICT", None)
    if proposed.mode != "DEMO" or type(proposed.ticket_id) is not int or proposed.ticket_id != 147:
        return AdmissionResult("CONFLICT", None)
    if existing is None:
        return AdmissionResult("NEW", proposed)
    if not isinstance(existing, ResumeEnvelope):
        return AdmissionResult("CONFLICT", None)
    if (existing.tenant_id, existing.idempotency_key) != (proposed.tenant_id, proposed.idempotency_key):
        return AdmissionResult("CONFLICT", None)
    if existing == proposed and type(existing.ticket_id) is int:
        return AdmissionResult("REPLAY", existing)
    return AdmissionResult("CONFLICT", None)
