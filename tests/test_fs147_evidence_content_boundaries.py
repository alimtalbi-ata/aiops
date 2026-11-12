"""FS147 evidence content boundary regression matrix (synthetic; no I/O)."""
from dataclasses import replace
from hashlib import sha256

import pytest

from app.core.fs147_evidence_content import (
    ContentStatus, EvidenceContentRead, classify_evidence_content,
)
from app.core.fs147_evidence_provenance import EvidenceBinding, EvidenceObservation


DATA = b"FS147\x00synthetic\xff"
BASE = EvidenceBinding(
    "tenant", "fingerprint", "incident", "run", "evidence",
    sha256(DATA).hexdigest(), 147, "DEMO",
)


def receipt(binding=BASE, payload=DATA, complete=True, authenticated=True,
            durable=True, read_authenticated=True):
    return EvidenceContentRead(
        EvidenceObservation(binding, read_authenticated, durable),
        payload, complete, authenticated,
    )


@pytest.mark.parametrize("payload", [
    b"FS147\x00synthetic", DATA + b"\x00", b"", b"FS147\x00synthetic\xfe",
])
def test_any_byte_change_conflicts_with_digest(payload):
    assert classify_evidence_content(BASE, receipt(payload=payload)) is ContentStatus.CONFLICT


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "other"), ("alert_fingerprint", "other"),
    ("incident_id", "other"), ("run_id", "other"), ("evidence_id", "other"),
    ("evidence_sha256", sha256(b"other").hexdigest()),
])
def test_cross_run_or_cross_evidence_reuse_conflicts(field, value):
    assert classify_evidence_content(
        BASE, receipt(binding=replace(BASE, **{field: value}))
    ) is ContentStatus.CONFLICT


@pytest.mark.parametrize("field,value", [
    ("complete", False), ("complete", 1), ("authenticated", False),
    ("authenticated", 1), ("content", bytearray(DATA)),
    ("content", memoryview(DATA)), ("content", None),
])
def test_untrusted_or_noncanonical_read_is_unknown(field, value):
    assert classify_evidence_content(
        BASE, replace(receipt(), **{field: value})
    ) is ContentStatus.UNKNOWN


@pytest.mark.parametrize("kwargs", [
    {"durable": False}, {"durable": 1},
    {"read_authenticated": False}, {"read_authenticated": 1},
])
def test_provenance_not_attested_is_unknown(kwargs):
    assert classify_evidence_content(BASE, receipt(**kwargs)) is ContentStatus.UNKNOWN


def test_replay_is_pure_and_never_a_launch_permission():
    before = receipt()
    assert classify_evidence_content(BASE, before) is ContentStatus.MATCH
    assert classify_evidence_content(BASE, before) is ContentStatus.MATCH
    assert before == receipt()
    assert BASE == receipt().observation.binding


@pytest.mark.parametrize("mode,ticket,status", [
    ("LIVE", 147, ContentStatus.DENIED),
    ("DEMO", 146, ContentStatus.DENIED),
    ("DEMO", 148, ContentStatus.DENIED),
    ("UNKNOWN", 147, ContentStatus.UNKNOWN),
])
def test_mode_and_existing_ticket_gate(mode, ticket, status):
    assert classify_evidence_content(
        replace(BASE, mode=mode, ticket_id=ticket), receipt()
    ) is status
