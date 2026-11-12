"""Regression: control characters cannot become authoritative FS147 identities.

Pure snapshots; no DB/GLPI/Temporal calls.
"""
from dataclasses import replace

import pytest

from app.core.fs147_evidence_provenance import (
    EvidenceBinding, EvidenceObservation, EvidenceStatus, classify_evidence_binding,
)


def binding():
    return EvidenceBinding(
        tenant_id="tenant-a", alert_fingerprint="alert-1", incident_id="incident-1",
        run_id="run-1", evidence_id="evidence-1", evidence_sha256="a" * 64,
        ticket_id=147, mode="DEMO",
    )


def observed(value):
    return EvidenceObservation(binding=value, authenticated_read=True, durable_read=True)


@pytest.mark.parametrize("field", [
    "tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id",
])
@pytest.mark.parametrize("bad", ["\x00", "\n", "\r", "\t", "\x1f", "\x7f"])
def test_control_character_never_matches(field, bad):
    value = replace(binding(), **{field: "prefix" + bad + "suffix"})
    assert classify_evidence_binding(value, observed(value)) == EvidenceStatus.UNKNOWN
    assert classify_evidence_binding(binding(), observed(value)) == EvidenceStatus.UNKNOWN


def test_clean_replay_matches_but_does_not_authorize():
    value = binding()
    assert classify_evidence_binding(value, observed(value)) == EvidenceStatus.MATCH


def test_missing_authenticated_observation_remains_unknown():
    value = binding()
    assert classify_evidence_binding(
        value, EvidenceObservation(value, authenticated_read=False, durable_read=True)
    ) == EvidenceStatus.UNKNOWN


def test_live_and_wrong_ticket_denied():
    value = binding()
    assert classify_evidence_binding(replace(value, mode="LIVE"), observed(value)) == EvidenceStatus.DENIED
    assert classify_evidence_binding(replace(value, ticket_id=146), observed(value)) == EvidenceStatus.DENIED
