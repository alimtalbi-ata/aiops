"""Synthetic only: no GLPI, DB or Temporal calls."""
from dataclasses import replace

from app.core.fs147_temporal_signal_admission import (
    SignalIntent, SignalStatus, classify_signal,
)


BASE = SignalIntent("tenant-a", "key-a", "run-a", "workflow-a",
                    "inspect-fs", "validation-a", 7, "DEMO", 147)


def check(intent=BASE, receipt=None, **changes):
    params = dict(authoritative_absence=True, authoritative_receipt=False,
                  temporal_state="WAITING_HUMAN", policy="ALLOW",
                  approval="ACCEPTED", stop_auto=False)
    params.update(changes)
    return classify_signal(intent, receipt, **params)


def test_candidate_is_not_dispatch_and_replays_stable():
    assert check() is SignalStatus.NEW_CANDIDATE
    assert check() is SignalStatus.NEW_CANDIDATE
    assert check(receipt=BASE, authoritative_absence=False,
                 authoritative_receipt=True) is SignalStatus.REPLAY


def test_conflicting_receipt_is_never_a_replay():
    for field, value in (("run_id", "run-other"),
                         ("workflow_id", "workflow-other"),
                         ("action_id", "delete"),
                         ("approval_id", "validation-other"),
                         ("fence_token", 8),
                         ("tenant_id", "tenant-other"),
                         ("idempotency_key", "key-other")):
        assert check(receipt=replace(BASE, **{field: value}),
                     authoritative_absence=False,
                     authoritative_receipt=True) is SignalStatus.CONFLICT


def test_unverified_or_contradictory_authority_unknown():
    assert check(authoritative_absence=False) is SignalStatus.UNKNOWN
    assert check(authoritative_absence=1) is SignalStatus.UNKNOWN
    assert check(receipt=BASE, authoritative_receipt=True) is SignalStatus.UNKNOWN
    assert check(receipt=BASE, authoritative_absence=False) is SignalStatus.UNKNOWN
    assert check(receipt=BASE, authoritative_absence=False,
                 authoritative_receipt="true") is SignalStatus.UNKNOWN
    assert check(receipt=object(), authoritative_absence=False,
                 authoritative_receipt=True) is SignalStatus.UNKNOWN


def test_policy_hitl_and_temporal_refusals():
    for changes in (dict(policy="DENY"), dict(policy="BLOCKED"),
                    dict(stop_auto=True), dict(approval="REJECTED"),
                    dict(approval="EXPIRED"), dict(temporal_state="COMPLETED"),
                    dict(temporal_state="CANCELLED")):
        assert check(**changes) is SignalStatus.DENIED
    assert check(approval="PENDING") is SignalStatus.NEEDS_HUMAN
    assert check(policy=None) is SignalStatus.UNKNOWN
    assert check(temporal_state=None) is SignalStatus.UNKNOWN


def test_live_wrong_ticket_and_missing_identity_fail_closed():
    assert check(replace(BASE, mode="LIVE")) is SignalStatus.DENIED
    assert check(replace(BASE, ticket_id=146)) is SignalStatus.DENIED
    assert check(replace(BASE, fence_token=True)) is SignalStatus.UNKNOWN
    assert check(replace(BASE, run_id="")) is SignalStatus.UNKNOWN
    assert check(None) is SignalStatus.UNKNOWN
