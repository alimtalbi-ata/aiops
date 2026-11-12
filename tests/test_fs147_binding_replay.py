"""Offline, synthetic FS147 replay tests: no DB, GLPI or Temporal calls."""
from dataclasses import replace
import pytest

from app.core.fs147_binding_key import derive_fs147_key
from app.core.fs147_binding_replay import (
    BindingSnapshot, ReplayDecision, classify_binding_replay,
)


def binding(**changes):
    values = dict(tenant_id="tenant", alert_fingerprint="alert", incident_id="incident",
                  run_id="run", evidence_id="evidence", ticket_id=147, mode="DEMO")
    values.update(changes)
    result = derive_fs147_key(**values)
    return BindingSnapshot(**values, key=result.key)


def test_exact_replay_is_only_observational():
    record = binding()
    assert classify_binding_replay(record, record, authoritative_read=True) is ReplayDecision.SAME_BINDING


@pytest.mark.parametrize("field", ["tenant_id", "alert_fingerprint", "incident_id",
                                   "run_id", "evidence_id"])
def test_divergent_identity_is_conflict(field):
    original = binding()
    other = binding(**{field: "different"})
    assert classify_binding_replay(other, original, authoritative_read=True) is ReplayDecision.CONFLICT


@pytest.mark.parametrize("bad", [None, False, "true", 1])
def test_unverified_read_never_matches(bad):
    record = binding()
    assert classify_binding_replay(record, record, authoritative_read=bad) is ReplayDecision.UNKNOWN


def test_missing_persisted_row_never_claims_success():
    assert classify_binding_replay(binding(), None, authoritative_read=True) is ReplayDecision.UNKNOWN


def test_stale_or_forged_key_conflicts():
    record = binding()
    assert classify_binding_replay(replace(record, key="fs147:v1:forged"), record,
                                   authoritative_read=True) is ReplayDecision.CONFLICT


def test_live_and_wrong_ticket_denied_without_effect():
    for bad in (binding(mode="LIVE"), binding(ticket_id=146)):
        assert classify_binding_replay(bad, binding(), authoritative_read=True) is ReplayDecision.DENIED


def test_malformed_identifier_unknown():
    assert classify_binding_replay(binding(run_id="bad\\u202e"), binding(),
                                   authoritative_read=True) is ReplayDecision.UNKNOWN


def test_snapshot_unchanged():
    record = binding()
    before = repr(record)
    classify_binding_replay(record, record, authoritative_read=True)
    assert repr(record) == before
