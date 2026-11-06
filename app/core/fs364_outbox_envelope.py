"""FS.364 read-only outbox envelope validation before any Temporal dispatch.

This module does not fetch GLPI, claim an outbox row, signal Temporal or
authorize LIVE. All identities and versions must come from authoritative
backend reads; the dispatcher must revalidate them atomically.
"""
from dataclasses import dataclass
from .fs364_dispatch_guard import DispatchState, dispatch_still_admissible


@dataclass(frozen=True)
class ResumeEnvelope:
    alert_fingerprint: str
    incident_id: str
    run_id: str
    evidence_id: str
    tenant_id: str
    mode: str
    ticket_id: int
    idempotency_key: str
    state_version: str
    policy_version: str


def envelope_still_admissible(
    admitted: ResumeEnvelope,
    current: ResumeEnvelope,
    admitted_state: DispatchState,
    current_state: DispatchState,
) -> bool:
    """Pure fail-closed predicate. Positive result is NOT dispatch permission."""
    if not isinstance(admitted, ResumeEnvelope) or not isinstance(current, ResumeEnvelope):
        return False
    try:
        for envelope in (admitted, current):
            for name in (
                "alert_fingerprint", "incident_id", "run_id", "evidence_id",
                "tenant_id", "idempotency_key", "state_version", "policy_version",
            ):
                value = getattr(envelope, name)
                if (not isinstance(value, str) or not value or value != value.strip()
                        or not value.isprintable() or any(ch.isspace() for ch in value)):
                    return False
            if envelope.mode != "DEMO" or type(envelope.ticket_id) is not int or envelope.ticket_id != 147:
                return False
        if admitted != current:
            return False
        if not dispatch_still_admissible(admitted_state, current_state):
            return False
        return all(
            envelope.run_id == state.run_id
            and envelope.tenant_id == state.tenant_id
            and envelope.mode == state.mode
            and envelope.ticket_id == state.ticket_id
            and envelope.state_version == state.state_version
            and envelope.policy_version == state.policy_version
            for envelope, state in ((admitted, admitted_state), (current, current_state))
        )
    except (AttributeError, TypeError, ValueError):
        return False
