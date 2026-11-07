"""Pure tests: no GLPI, DB, Temporal or production access."""
from dataclasses import replace

from app.core.fs147_native_resume_gate import NativeApproval, Fencing, native_resume_gate
from app.core.fs364_outbox_envelope import ResumeEnvelope
from app.core.fs364_dispatch_guard import DispatchState
from app.core.fs364_outbox_transition import OutboxRecord


def fixtures():
    envelope = ResumeEnvelope("alert-a", "incident-a", "run-a", "evidence-a",
                              "tenant-a", "DEMO", 147, "key-a", "v1", "p1")
    state = DispatchState("tenant-a", "run-a", "DEMO", 147, "WAITING_HUMAN",
                          "v1", "ALLOW", "p1", False, True, True, True,
                          True, True, True)
    record = OutboxRecord("event-a", 3, "CLAIMED", 1, "tenant-a", "key-a", 147, "DEMO")
    approval = NativeApproval(147, "tenant-a", "run-a", "inspect-fs", "/fs-lab/file",
                              "sha256-a", "validation-a", "validator-a", "requester-a",
                              200, "ACCEPTED", True)
    fence = Fencing("event-a", "worker-a", 7, 7, 150, True)
    return record, envelope, state, approval, fence


def gate(record, envelope, state, approval, fence, **kwargs):
    options = dict(action_id="inspect-fs", path="/fs-lab/file",
                   content_fingerprint="sha256-a", now_epoch=100,
                   expected_revision=3, expected_owner_id="worker-a", authoritative_read=True)
    options.update(kwargs)
    return native_resume_gate(record, envelope, envelope, state, state,
                              approval, fence, **options)


def test_deterministic_no_effect_replay():
    args = fixtures()
    assert gate(*args)
    assert gate(*args)
    assert args == fixtures()


def test_native_approval_must_match_action_and_identity():
    record, env, state, approval, fence = fixtures()
    for bad in (
        replace(approval, ticket_id=146),
        replace(approval, action_id="delete"),
        replace(approval, path="/other"),
        replace(approval, content_fingerprint="sha256-b"),
        replace(approval, run_id="run-other"),
        replace(approval, validator_id="requester-a"),
        replace(approval, decision="REJECTED"),
        replace(approval, verified_native=False),
        replace(approval, expires_at_epoch=100),
    ):
        assert not gate(record, env, state, bad, fence)


def test_fencing_and_missing_data_fail_closed():
    record, env, state, approval, fence = fixtures()
    for bad in (replace(fence, token=6), replace(fence, db_verified=False),
                replace(fence, event_id="other"), replace(fence, lease_expires_epoch=100)):
        assert not gate(record, env, state, approval, bad)
    assert not gate(record, env, state, None, fence)
    assert not gate(record, env, state, approval, None)
    assert not gate(record, env, state, approval, fence, authoritative_read=None)
    assert not gate(record, env, state, approval, fence, now_epoch=None)


def test_policy_live_and_revision_refused():
    record, env, state, approval, fence = fixtures()
    assert not gate(record, env, replace(state, policy_decision="DENY"), approval, fence)
    assert not gate(record, env, replace(state, stop_auto=True), approval, fence)
    assert not gate(record, replace(env, mode="LIVE"), state, approval, fence)
    assert not gate(record, env, state, approval, fence, expected_revision=2)


def test_explicit_owner_binding_and_unknown_snapshots():
    record, env, state, approval, fence = fixtures()
    assert gate(record, env, state, approval, fence)
    assert not gate(record, env, state, approval, fence, expected_owner_id=None)
    assert not gate(record, env, state, approval, fence, expected_owner_id="worker-other")
    assert not gate(record, env, state, approval, replace(fence, owner_id="worker-other"))
    assert not gate(None, env, state, approval, fence)
    assert not gate(record, None, state, approval, fence)
    assert not gate(record, env, state, approval, fence, expected_owner_id=True)
