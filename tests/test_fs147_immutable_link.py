"""FS147 correlation replay/negative tests, fully offline."""
from dataclasses import replace
from app.core.fs147_immutable_link import Link, LinkDecision, classify_link


def link():
    return Link("tenant1", "key1", "alert1", "INC1", "RUN1", "EVID1",
                "a" * 64, 147, "DEMO")


def test_repeated_replay_is_pure():
    x = link()
    for _ in range(20):
        assert classify_link(x) == LinkDecision.NEW
        assert classify_link(x, x) == LinkDecision.REPLAY
    assert x == link()


def test_identity_and_evidence_conflicts():
    x = link()
    for field, value in (
        ("tenant_id", "other"), ("idempotency_key", "other"),
        ("alert_fingerprint", "other"), ("incident_id", "other"),
        ("run_id", "other"), ("evidence_id", "other"),
        ("evidence_sha256", "b" * 64),
    ):
        assert classify_link(replace(x, **{field: value}), x) == LinkDecision.CONFLICT


def test_live_and_other_ticket_are_denied():
    x = link()
    assert classify_link(replace(x, mode="LIVE")) == LinkDecision.DENIED
    assert classify_link(replace(x, glpi_ticket_id=146)) == LinkDecision.DENIED
    assert classify_link(replace(x, glpi_ticket_id=True)) == LinkDecision.UNKNOWN


def test_missing_or_untrusted_existing_is_unknown():
    x = link()
    assert classify_link(None) == LinkDecision.UNKNOWN
    assert classify_link(replace(x, evidence_sha256="")) == LinkDecision.UNKNOWN
    assert classify_link(replace(x, incident_id="bad space")) == LinkDecision.UNKNOWN
    assert classify_link(x, object()) == LinkDecision.UNKNOWN
    assert classify_link(x, replace(x, glpi_ticket_id=146)) == LinkDecision.CONFLICT
