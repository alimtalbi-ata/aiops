from dataclasses import replace
from datetime import datetime, timedelta, timezone
import pytest

from app.core.fs147_hitl_scope import ApprovalScope, ScopeDecision, classify_approval_scope

NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)
SHA = "a" * 64
BASE = ApprovalScope(147, "run-1", "inspect-1", "/fs-lab/a", SHA,
                     "requester", "validator", "ACCEPTED", NOW + timedelta(minutes=5),
                     True, True)
ARGS = dict(ticket_id=147, run_id="run-1", action_id="inspect-1",
            path="/fs-lab/a", content_sha256=SHA, requester_id="requester", now=NOW)


def classify(approval=BASE, **changes):
    return classify_approval_scope(approval, **(ARGS | changes))


def test_exact_match_is_not_authorization():
    assert classify() == ScopeDecision.SCOPE_MATCH
    assert classify() == ScopeDecision.SCOPE_MATCH


@pytest.mark.parametrize("change", [
    {"ticket_id": 146}, {"run_id": "run-2"}, {"action_id": "delete"},
    {"path": "/fs-lab/b"}, {"content_sha256": "b" * 64},
    {"requester_id": "other"}, {"validator_id": "requester"},
    {"expires_at": NOW}, {"expires_at": NOW - timedelta(seconds=1)},
])
def test_mismatches_denied(change):
    assert classify(replace(BASE, **change)) == ScopeDecision.DENIED


@pytest.mark.parametrize("change", [
    {"native_authenticated": False}, {"durable_read": False},
    {"native_authenticated": 1}, {"durable_read": "true"},
    {"expires_at": NOW.replace(tzinfo=None)},
    {"content_sha256": "not-a-hash"},
    {"run_id": "run\u200b1"},
])
def test_untrusted_or_malformed_unknown(change):
    assert classify(replace(BASE, **change)) == ScopeDecision.UNKNOWN


def test_pending_rejected_and_missing():
    assert classify(replace(BASE, status="PENDING")) == ScopeDecision.NEEDS_HUMAN
    assert classify(replace(BASE, status="REJECTED")) == ScopeDecision.DENIED
    assert classify(None) == ScopeDecision.UNKNOWN


def test_wrong_ticket_and_clock():
    assert classify(ticket_id=146) == ScopeDecision.DENIED
    assert classify(now=NOW.replace(tzinfo=None)) == ScopeDecision.UNKNOWN
