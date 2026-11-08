"""FS147 canonical Unicode regression tests (pure, no external I/O)."""
from dataclasses import replace

import pytest

from app.core.fs147_binding_key import KeyStatus, derive_fs147_key
from app.core.fs147_binding_replay import BindingSnapshot, ReplayDecision, classify_binding_replay


def snapshot(run_id="run"):
    fields = dict(tenant_id="tenant", alert_fingerprint="alert", incident_id="incident",
                  run_id=run_id, evidence_id="evidence", ticket_id=147, mode="DEMO")
    result = derive_fs147_key(**fields)
    return result, BindingSnapshot(**fields, key=result.key)


@pytest.mark.parametrize("field", [
    "tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id",
])
def test_decomposed_unicode_identifier_is_unknown(field):
    fields = dict(tenant_id="tenant", alert_fingerprint="alert", incident_id="incident",
                  run_id="run", evidence_id="evidence", ticket_id=147, mode="DEMO")
    fields[field] = "cafe\u0301"  # NFD: visually confusable with NFC café
    assert derive_fs147_key(**fields).status is KeyStatus.UNKNOWN


def test_nfc_unicode_identifier_remains_supported_and_deterministic():
    first, _ = snapshot("caf\u00e9")
    second, _ = snapshot("caf\u00e9")
    assert first.status is KeyStatus.READY
    assert first.key == second.key


def test_noncanonical_request_never_replays_as_same_binding():
    _, persisted = snapshot("caf\u00e9")
    _, requested = snapshot("cafe\u0301")
    assert classify_binding_replay(requested, persisted, authoritative_read=True) is ReplayDecision.UNKNOWN


def test_noncanonical_persisted_snapshot_never_replays_as_same_binding():
    _, requested = snapshot("caf\u00e9")
    _, malformed = snapshot("cafe\u0301")
    assert classify_binding_replay(requested, malformed, authoritative_read=True) is ReplayDecision.UNKNOWN


def test_unicode_control_character_is_unknown_not_match():
    _, valid = snapshot()
    _, malformed = snapshot("bad\u202e")
    assert classify_binding_replay(malformed, valid, authoritative_read=True) is ReplayDecision.UNKNOWN


def test_no_snapshot_mutation_on_replay():
    _, persisted = snapshot()
    requested = replace(persisted)
    before = repr(requested), repr(persisted)
    classify_binding_replay(requested, persisted, authoritative_read=True)
    assert before == (repr(requested), repr(persisted))
