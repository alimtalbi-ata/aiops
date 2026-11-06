"""FS.364 dispatch-time revalidation contract; pure, fail-closed, no I/O.

This is NOT a Temporal signal dispatcher. The coordinator must obtain both
snapshots from authoritative stores under an appropriate concurrency protocol;
a positive result is never an execution permit by itself.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DispatchState:
    tenant_id: str
    run_id: str
    mode: str
    ticket_id: int
    state: str
    state_version: str
    policy_decision: str
    policy_version: str
    stop_auto: bool
    human_answer_verified: bool
    approval_specific: bool
    approval_valid: bool
    glpi_verified: bool
    authenticated: bool
    acl_ok: bool


def dispatch_still_admissible(admitted: DispatchState, current: DispatchState) -> bool:
    """Reject revocations, version drift, invalid identities and LIVE.

    The caller must check outbox ownership and deduplicate the workflow signal.
    No external service is called and no state is mutated.
    """
    try:
        if not isinstance(admitted, DispatchState) or not isinstance(current, DispatchState):
            return False
        if any(type(getattr(snapshot, name)) is not bool for snapshot in (admitted, current) for name in (
            "stop_auto", "human_answer_verified", "approval_specific",
            "approval_valid", "glpi_verified", "authenticated", "acl_ok"
        )):
            return False
        for name in ("tenant_id", "run_id", "state_version", "policy_version"):
            value = getattr(current, name)
            if not isinstance(value, str) or not value or value != value.strip():
                return False
            if getattr(admitted, name) != value:
                return False
        if admitted.mode != "DEMO" or current.mode != "DEMO":
            return False
        if admitted.ticket_id != 147 or current.ticket_id != 147:
            return False
        return all(
            snapshot.state == "WAITING_HUMAN"
            and snapshot.policy_decision == "ALLOW"
            and not snapshot.stop_auto
            and snapshot.human_answer_verified
            and snapshot.approval_specific
            and snapshot.approval_valid
            and snapshot.glpi_verified
            and snapshot.authenticated
            and snapshot.acl_ok
            for snapshot in (admitted, current)
        )
    except (AttributeError, TypeError, ValueError):
        return False
