"""Synthetic, side-effect-free FS147 dispatch reconciliation tests."""
from dataclasses import replace
from app.core.fs147_dispatch_reconciliation import (
    DispatchSnapshot, ReconcileStatus as S, classify_dispatch,
)

BASE = DispatchSnapshot("tenant", "key", "run", "workflow", "action",
                        "native-validation", 4, 147, "DEMO")
GOOD = dict(outbox_state="PENDING", temporal_receipt=False,
            authoritative_read=True, policy="ALLOW", approval="ACCEPTED",
            stop_auto=False, fence_current=True)


def test_pending_is_only_eligible_for_revalidation():
    assert classify_dispatch(BASE, **GOOD) == S.ELIGIBLE_FOR_REVALIDATION
    assert classify_dispatch(BASE, **GOOD) == S.ELIGIBLE_FOR_REVALIDATION


def test_crash_window_is_unknown_not_retry():
    for state in ("DISPATCHING", "UNCERTAIN"):
        for receipt in (True, False, None):
            assert classify_dispatch(BASE, **(GOOD | dict(
                outbox_state=state, temporal_receipt=receipt))) == S.UNKNOWN


def test_recorded_receipt_never_authorizes_resend():
    assert classify_dispatch(BASE, **(GOOD | dict(
        outbox_state="DELIVERED", temporal_receipt=True))) == S.ALREADY_RECORDED
    assert classify_dispatch(BASE, **(GOOD | dict(
        outbox_state="PENDING", temporal_receipt=True))) == S.ALREADY_RECORDED
    assert classify_dispatch(BASE, **(GOOD | dict(
        outbox_state="DELIVERED", temporal_receipt=False))) == S.UNKNOWN


def test_explicit_denials_and_pending_human():
    for changes in (dict(policy="DENY"), dict(stop_auto=True),
                    dict(approval="REJECTED"), dict(approval="EXPIRED")):
        assert classify_dispatch(BASE, **(GOOD | changes)) == S.DENIED
    assert classify_dispatch(BASE, **(GOOD | dict(approval="PENDING"))) == S.NEEDS_HUMAN
    assert classify_dispatch(replace(BASE, mode="LIVE"), **GOOD) == S.DENIED
    assert classify_dispatch(replace(BASE, ticket_id=146), **GOOD) == S.DENIED


def test_missing_authority_and_bad_identity_fail_closed():
    for changes in (dict(authoritative_read=None), dict(fence_current=False),
                    dict(temporal_receipt=None), dict(stop_auto=None)):
        assert classify_dispatch(BASE, **(GOOD | changes)) == S.UNKNOWN
    assert classify_dispatch(replace(BASE, action_id=""), **GOOD) == S.UNKNOWN
    assert classify_dispatch(replace(BASE, fence_token=True), **GOOD) == S.UNKNOWN
    assert classify_dispatch(None, **GOOD) == S.UNKNOWN
