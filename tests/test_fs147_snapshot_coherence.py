from dataclasses import replace

from app.core.fs147_snapshot_coherence import Coherence, LinkIdentity, classify_coherence


BASE = LinkIdentity("tenant", "key", "fingerprint", "INC-1", "RUN-1",
                    "EVID-1", "a" * 64, 147, "DEMO")


def test_replays_are_stable():
    assert classify_coherence(BASE, BASE, BASE) is Coherence.MATCH
    assert classify_coherence(BASE, BASE) is Coherence.MATCH


def test_any_link_mismatch_is_denied():
    for field, value in (("tenant_id", "other"), ("idempotency_key", "other"),
                         ("alert_fingerprint", "other"), ("incident_id", "other"),
                         ("run_id", "other"), ("evidence_id", "other"),
                         ("evidence_sha256", "b" * 64)):
        assert classify_coherence(BASE, replace(BASE, **{field: value})) is Coherence.DENIED


def test_live_and_other_ticket_denied():
    assert classify_coherence(BASE, replace(BASE, mode="LIVE")) is Coherence.DENIED
    assert classify_coherence(BASE, replace(BASE, glpi_ticket_id=146)) is Coherence.DENIED


def test_missing_and_malformed_remain_unknown():
    assert classify_coherence(BASE) is Coherence.UNKNOWN
    assert classify_coherence(BASE, None) is Coherence.UNKNOWN
    assert classify_coherence(BASE, replace(BASE, evidence_sha256="invalid")) is Coherence.UNKNOWN
    assert classify_coherence(BASE, replace(BASE, run_id="")) is Coherence.UNKNOWN
    assert classify_coherence(BASE, replace(BASE, glpi_ticket_id=True)) is Coherence.UNKNOWN
