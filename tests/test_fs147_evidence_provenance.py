"""Synthetic, read-only FS147 evidence provenance negative matrix."""
from dataclasses import replace

from app.core.fs147_evidence_provenance import (
    EvidenceBinding, EvidenceObservation, EvidenceStatus, classify_evidence_binding,
)


def binding():
    return EvidenceBinding("tenant", "fingerprint", "INC-1", "RUN-1", "EVID-1", "a" * 64, 147, "DEMO")


def observed(b=None, authenticated=True, durable=True):
    return EvidenceObservation(b if b is not None else binding(), authenticated, durable)


def test_identical_authenticated_durable_read_is_only_match():
    b = binding()
    assert classify_evidence_binding(b, observed()) == EvidenceStatus.MATCH
    assert classify_evidence_binding(b, observed()) == EvidenceStatus.MATCH


def test_missing_or_untrusted_observation_fails_closed():
    b = binding()
    assert classify_evidence_binding(b, None) == EvidenceStatus.UNKNOWN
    assert classify_evidence_binding(b, observed(authenticated=False)) == EvidenceStatus.UNKNOWN
    assert classify_evidence_binding(b, observed(durable=False)) == EvidenceStatus.UNKNOWN
    assert classify_evidence_binding(b, observed(authenticated=1)) == EvidenceStatus.UNKNOWN


def test_run_evidence_and_digest_mismatch_are_conflicts():
    b = binding()
    for changed in (replace(b, run_id="RUN-2"), replace(b, evidence_id="EVID-2"),
                    replace(b, evidence_sha256="b" * 64)):
        assert classify_evidence_binding(b, observed(changed)) == EvidenceStatus.CONFLICT


def test_live_or_wrong_ticket_is_denied():
    b = binding()
    for changed in (replace(b, mode="LIVE"), replace(b, ticket_id=146)):
        assert classify_evidence_binding(changed, observed()) == EvidenceStatus.DENIED
        assert classify_evidence_binding(b, observed(changed)) == EvidenceStatus.DENIED


def test_malformed_and_missing_identity_remain_unknown():
    b = binding()
    for changed in (replace(b, evidence_sha256="not-a-hash"), replace(b, run_id=""),
                    replace(b, ticket_id=True), replace(b, mode="UNKNOWN")):
        assert classify_evidence_binding(changed, observed()) == EvidenceStatus.UNKNOWN
