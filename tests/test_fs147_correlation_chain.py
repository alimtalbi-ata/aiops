"""Pure, offline FS147 correlation boundary tests."""
from dataclasses import replace

import pytest

from app.core.fs147_correlation_chain import (
    CorrelationDecision, CorrelationLink, classify_correlation,
)


@pytest.fixture
def link():
    return CorrelationLink(
        tenant_id="tenant-a", alert_fingerprint="sha256:abc",
        incident_id="incident-1", run_id="run-1", evidence_id="evidence-1",
        ticket_id=147, mode="DEMO",
    )


def test_identical_snapshot_only_matches(link):
    assert classify_correlation(link, link) is CorrelationDecision.MATCH


@pytest.mark.parametrize("field", [
    "tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id",
])
def test_identity_conflict(link, field):
    assert classify_correlation(link, replace(link, **{field: "different"})) is CorrelationDecision.CONFLICT


@pytest.mark.parametrize("field", [
    "tenant_id", "alert_fingerprint", "incident_id", "run_id", "evidence_id",
])
@pytest.mark.parametrize("bad", ["", " ", "x\u200b", "x\u202e", "x\x00", None, 42])
def test_missing_or_untrusted_identifiers_fail_closed(link, field, bad):
    assert classify_correlation(link, replace(link, **{field: bad})) is CorrelationDecision.UNKNOWN


@pytest.mark.parametrize("mode", ["LIVE", "live", "", None])
def test_mode_boundary(link, mode):
    decision = classify_correlation(link, replace(link, mode=mode))
    assert decision is (CorrelationDecision.DENIED if mode == "LIVE" else CorrelationDecision.UNKNOWN)


@pytest.mark.parametrize("ticket", [146, 148, 0, True, None, "147"])
def test_ticket_boundary(link, ticket):
    decision = classify_correlation(link, replace(link, ticket_id=ticket))
    expected = CorrelationDecision.DENIED if type(ticket) is int else CorrelationDecision.UNKNOWN
    assert decision is expected


def test_no_mutation_and_deterministic_replay(link):
    before = repr(link)
    assert [classify_correlation(link, link)] * 3 == [
        classify_correlation(link, link) for _ in range(3)
    ]
    assert repr(link) == before


def test_invalid_snapshot_unknown(link):
    assert classify_correlation(link, None) is CorrelationDecision.UNKNOWN
