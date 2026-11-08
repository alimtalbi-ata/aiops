"""Synthetic read-only FS147 content integrity tests."""
from dataclasses import replace
from hashlib import sha256

from app.core.fs147_evidence_content import (
    ContentStatus, EvidenceContentRead, classify_evidence_content,
)
from app.core.fs147_evidence_provenance import EvidenceBinding, EvidenceObservation


PAYLOAD = b"synthetic-fs147-evidence"
BINDING = EvidenceBinding("tenant", "alert", "incident", "run", "evidence",
                          sha256(PAYLOAD).hexdigest(), 147, "DEMO")


def sample(**kwargs):
    return EvidenceContentRead(EvidenceObservation(BINDING, True, True),
                               PAYLOAD, True, True).__class__(
        **({**dict(observation=EvidenceObservation(BINDING, True, True),
                 content=PAYLOAD, complete=True, authenticated=True), **kwargs})
    )


def test_replay_deterministic_and_empty_bytes_supported():
    assert classify_evidence_content(BINDING, sample()) == ContentStatus.MATCH
    assert classify_evidence_content(BINDING, sample()) == ContentStatus.MATCH
    empty = replace(BINDING, evidence_sha256=sha256(b"").hexdigest())
    assert classify_evidence_content(empty, sample(
        observation=EvidenceObservation(empty, True, True), content=b"")) == ContentStatus.MATCH


def test_tampered_bytes_conflict():
    assert classify_evidence_content(BINDING, sample(content=b"tampered")) == ContentStatus.CONFLICT


def test_missing_partial_untrusted_fail_closed():
    assert classify_evidence_content(BINDING, None) == ContentStatus.UNKNOWN
    for candidate in (sample(complete=False), sample(authenticated=False),
                      sample(content="not bytes"), sample(complete=1),
                      sample(observation=EvidenceObservation(BINDING, False, True))):
        assert classify_evidence_content(BINDING, candidate) == ContentStatus.UNKNOWN


def test_identity_conflict_and_denied():
    other = replace(BINDING, run_id="other")
    assert classify_evidence_content(BINDING, sample(
        observation=EvidenceObservation(other, True, True))) == ContentStatus.CONFLICT
    assert classify_evidence_content(replace(BINDING, mode="LIVE"), sample()) == ContentStatus.DENIED
    assert classify_evidence_content(replace(BINDING, ticket_id=146), sample()) == ContentStatus.DENIED


def test_invalid_digest_unknown():
    assert classify_evidence_content(replace(BINDING, evidence_sha256="invalid"), sample()) == ContentStatus.UNKNOWN
