"""Synthetic, no GLPI/Temporal/host effects."""
from dataclasses import replace
from app.core.fs147_signal_key import SignalIdentity, KeyStatus, classify_signal_key


def sample():
    return SignalIdentity(
        "tenant", "idem", "alert", "incident", "run", "evidence",
        "a" * 64, "workflow", "action", "approval", 7, 147, "DEMO"
    )


def test_stable_replay_and_field_binding():
    source = sample()
    status, digest = classify_signal_key(source)
    assert status == KeyStatus.VALID
    assert classify_signal_key(source) == (status, digest)
    for field, value in (
        ("run_id", "run2"), ("action_id", "action2"),
        ("approval_id", "approval2"), ("fence_token", 8),
        ("alert_fingerprint", "other"), ("evidence_sha256", "b" * 64),
    ):
        changed_status, changed_digest = classify_signal_key(replace(source, **{field: value}))
        assert changed_status == KeyStatus.VALID
        assert changed_digest != digest


def test_no_delimiter_collision():
    first = replace(sample(), tenant_id="a:b", idempotency_key="c")
    second = replace(sample(), tenant_id="a", idempotency_key="b:c")
    assert classify_signal_key(first)[1] != classify_signal_key(second)[1]


def test_denials_and_unknown():
    source = sample()
    assert classify_signal_key(replace(source, mode="LIVE")) == (KeyStatus.DENIED, None)
    assert classify_signal_key(replace(source, ticket_id=146)) == (KeyStatus.DENIED, None)
    for change in (
        {"mode": "UNKNOWN"}, {"ticket_id": True}, {"fence_token": True},
        {"fence_token": 0}, {"run_id": ""}, {"approval_id": "bad\\nvalue"},
        {"evidence_sha256": "A" * 64}, {"idempotency_key": " "},
    ):
        assert classify_signal_key(replace(source, **change)) == (KeyStatus.UNKNOWN, None)
    assert classify_signal_key(None) == (KeyStatus.UNKNOWN, None)
