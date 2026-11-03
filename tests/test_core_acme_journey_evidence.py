"""T2 Core synthetic evidence references: read-only, no actor/LIVE authority."""
from datetime import timedelta

import pytest

from test_core_acme_journey import (
    ATTEMPT, SOURCE_IDS, TIME, core, fixture, journey,
)


@pytest.mark.parametrize("resolved", [False, True])
def test_evidence_references_are_canonical_and_explicitly_unattested(resolved):
    snapshot, rows = fixture(resolved)
    result = journey.project_journey(snapshot, rows, ATTEMPT)
    assert [e["event_key"] for e in result["timeline"][:7]] == SOURCE_IDS
    assert result["timeline"][7]["event_key"] == core.ident("SIM-PREPARED-", ATTEMPT)
    assert result["timeline"][7]["evidence_ids"] == []
    if resolved:
        assert result["timeline"][8]["event_key"] == core.ident("SIM-RESOLVED-", ATTEMPT)
    expected = sorted(core.ident("EVID-SIM-", ATTEMPT + ":" + str(i)) for i in (1, 2))
    assert result["source_evidence_refs"] == expected
    for i, event in enumerate(result["timeline"][:7], 1):
        assert event["evidence_ids"] == [
            core.ident("EVID-SIM-", ATTEMPT + ":" + str(1 + ((i - 1) % 2)))
        ]
    assert result["source_evidence_authority"] == "CORE_PG16_SYNTHETIC_FIXTURE_REFS_ONLY"
    assert result["source_evidence_independently_attested"] is False
    assert result["journey_digest_kind"] == "LOCAL_CORE_READBACK_SHA256_NOT_SIGNATURE"
    assert len(result["journey_sha256"]) == 64
    assert result["twin_graph_019"] == "NOT_BOUND_TO_THIS_RUN"


def test_valid_but_wrong_source_evidence_binding_fails_closed():
    snapshot, rows = fixture()
    # EVID-SIM-2 exists and is valid, but SOURCE #1 must cite EVID-SIM-1.
    rows[0] = (*rows[0][:6], [core.ident("EVID-SIM-", ATTEMPT + ":2")], rows[0][7])
    with pytest.raises(Exception) as caught:
        journey.project_journey(snapshot, rows, ATTEMPT)
    assert getattr(caught.value, "status_code", None) == 503


@pytest.mark.parametrize("mutation", [
    "foreign_evidence", "boolean_evidence", "boolean_payload_sequence",
    "foreign_source_snapshot", "duplicate_source_snapshot",
])
def test_evidence_and_source_corruption_fail_closed(mutation):
    snapshot, rows = fixture()
    # The parent fixture reuses a module-level list; never mutate it across cases.
    snapshot["source_event_ids"] = list(snapshot["source_event_ids"])
    if mutation == "foreign_evidence":
        rows[0] = (*rows[0][:6], ["EVID-SIM-FOREIGN"], rows[0][7])
    elif mutation == "boolean_evidence":
        rows[0] = (*rows[0][:6], [True], rows[0][7])
    elif mutation == "boolean_payload_sequence":
        rows[0][7]["sequence"] = True
    elif mutation == "foreign_source_snapshot":
        snapshot["source_event_ids"][0] = "SYN-EVT-FOREIGN"
    elif mutation == "duplicate_source_snapshot":
        snapshot["source_event_ids"][1] = SOURCE_IDS[0]
    with pytest.raises(Exception) as caught:
        journey.project_journey(snapshot, rows, ATTEMPT)
    assert getattr(caught.value, "status_code", None) == 503


def test_same_run_digest_repeatable_and_sensitive_to_pg_event_timestamp():
    snapshot, rows = fixture()
    original = journey.project_journey(snapshot, rows, ATTEMPT)
    repeated = journey.project_journey(snapshot, rows, ATTEMPT)
    assert original["journey_sha256"] == repeated["journey_sha256"]
    rows[7] = (*rows[7][:4], TIME + timedelta(seconds=1), *rows[7][5:])
    modified = journey.project_journey(snapshot, rows, ATTEMPT)
    assert original["journey_sha256"] != modified["journey_sha256"]
    assert original["run_id"] == modified["run_id"]
    assert modified["source_evidence_independently_attested"] is False
