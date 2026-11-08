"""FS147 Unicode identity spoofing regression (pure, no external I/O)."""
from dataclasses import replace
from hashlib import sha256

import pytest

from app.core.fs147_evidence_provenance import (
    EvidenceBinding, EvidenceObservation, EvidenceStatus, classify_evidence_binding,
)
from app.core.fs147_evidence_content import (
    ContentStatus, EvidenceContentRead, classify_evidence_content,
)

PAYLOAD = b"fs147-unicode-regression"
BASE = EvidenceBinding("tenant", "fingerprint", "incident", "run", "evidence",
                       sha256(PAYLOAD).hexdigest(), 147, "DEMO")
FIELDS = ("tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id")
SPOOF = ("\\u202e", "\\u200d", "\\u2066", "\\u200b", "\\ufeff", "\\u0085", "\\ud800")


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("escaped", SPOOF)
def test_spoofing_identity_is_unknown_even_when_both_reads_agree(field, escaped):
    char = escaped.encode("ascii").decode("unicode_escape")
    forged = replace(BASE, **{field: "prefix" + char + "suffix"})
    observation = EvidenceObservation(forged, True, True)
    assert classify_evidence_binding(forged, observation) is EvidenceStatus.UNKNOWN
    read = EvidenceContentRead(observation, PAYLOAD, True, True)
    assert classify_evidence_content(forged, read) is ContentStatus.UNKNOWN


def test_valid_unicode_letters_are_not_overblocked():
    valid = replace(BASE, incident_id="incident-équipe")
    observation = EvidenceObservation(valid, True, True)
    assert classify_evidence_binding(valid, observation) is EvidenceStatus.MATCH
    assert classify_evidence_content(
        valid, EvidenceContentRead(observation, PAYLOAD, True, True)
    ) is ContentStatus.MATCH
