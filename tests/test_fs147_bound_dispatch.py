"""Synthetic FS147 receipt-bound dispatch tests; no network or writes."""
from dataclasses import replace

from app.core.fs147_dispatch_reconciliation import DispatchSnapshot
from app.core.fs147_bound_dispatch import (
    BoundReceipt, BoundStatus as S, classify_bound_dispatch,
)

SNAP = DispatchSnapshot("tenant", "key", "run", "wf", "action", "approval", 7, 147, "DEMO")
RECEIPT = BoundReceipt("tenant", "key", "run", "wf", "action", "approval", 7, 147, "DEMO")
GOOD = dict(outbox_state="PENDING", authoritative_read=True, policy="ALLOW",
            approval="ACCEPTED", stop_auto=False, fence_current=True)


def check(**changes):
    return classify_bound_dispatch(SNAP, **(GOOD | changes))


def test_verified_absence_only_candidate_not_signal():
    assert check(absence_verified=True, receipt_verified=False) == S.ELIGIBLE_FOR_REVALIDATION
    assert check(absence_verified=None, receipt_verified=False) == S.UNKNOWN
    assert check(absence_verified=False, receipt_verified=False) == S.UNKNOWN


def test_verified_matching_receipt_is_replay():
    assert check(receipt=RECEIPT, receipt_verified=True, absence_verified=False) == S.ALREADY_RECORDED
    assert check(receipt=RECEIPT, receipt_verified=False, absence_verified=False) == S.UNKNOWN


def test_identity_conflicts_never_replay():
    for field, value in (("tenant_id", "other"), ("run_id", "other"),
                         ("action_id", "other"), ("approval_id", "other"),
                         ("fence_token", 8), ("ticket_id", 146)):
        assert check(receipt=replace(RECEIPT, **{field: value}),
                     receipt_verified=True, absence_verified=False) == S.CONFLICT


def test_crash_window_and_contradictions_unknown():
    for state in ("DISPATCHING", "UNCERTAIN"):
        assert check(outbox_state=state, receipt=RECEIPT,
                     receipt_verified=True, absence_verified=False) == S.UNKNOWN
    assert check(receipt=RECEIPT, receipt_verified=True, absence_verified=True) == S.UNKNOWN


def test_denial_and_missing_authority_fail_closed():
    assert check(policy="DENY", absence_verified=True, receipt_verified=False) == S.DENIED
    assert check(approval="PENDING", absence_verified=True, receipt_verified=False) == S.NEEDS_HUMAN
    assert check(fence_current=None, absence_verified=True, receipt_verified=False) == S.UNKNOWN
    assert classify_bound_dispatch(replace(SNAP, mode="LIVE"), **GOOD,
                                  absence_verified=True, receipt_verified=False) == S.DENIED
