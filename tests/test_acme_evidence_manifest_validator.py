"""Untrusted offline evidence metadata must never become operational proof."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_lifecycle_read_model import build_synthetic_incident_lifecycle
from portal.acme_evidence_manifest_validator import inspect_synthetic_evidence_manifest


def fixture_manifest():
    lifecycle = build_synthetic_incident_lifecycle()
    return lifecycle, {
        "schema": "aiops.synthetic-evidence-manifest.v1",
        "mode": "DEMO",
        "source_sha256": lifecycle["source_sha256"],
        "incident_id": lifecycle["source_incident_id"],
        "items": [{
            "checkpoint": "detect",
            "source": "grafana",
            "evidence_type": "ALERT_STATE",
            "source_id": "alert:synthetic-01",
            "observed_at": "2026-11-14T12:00:00Z",
            "content_sha256": "a" * 64,
        }],
    }


def test_valid_metadata_never_attests_or_authorizes():
    lifecycle, manifest = fixture_manifest()
    report = inspect_synthetic_evidence_manifest(lifecycle, manifest)
    assert report["structurally_valid_count"] == 1
    assert report["independently_verified_count"] == 0
    assert report["inspected_items"][0]["authenticity"] == "UNVERIFIED"
    assert report["accepted_as_runtime_evidence"] is False
    assert report["itil_transition_authorized"] is False
    assert report["live_remediation_authorized"] is False
    assert len(report["unsubmitted_checkpoints"]) == 8


@pytest.mark.parametrize("field,value", [
    ("source", "glpi"),
    ("evidence_type", "POLICY_AND_HITL_DECISION"),
    ("source_id", "../unsafe"),
    ("observed_at", "2026-11-14T12:00:00+02:00"),
    ("content_sha256", "A" * 64),
])
def test_bad_evidence_item_rejected(field, value):
    lifecycle, manifest = fixture_manifest()
    manifest["items"][0][field] = value
    with pytest.raises(ValueError):
        inspect_synthetic_evidence_manifest(lifecycle, manifest)


def test_duplicate_checkpoint_and_foreign_incident_rejected():
    lifecycle, manifest = fixture_manifest()
    manifest["items"].append(copy.deepcopy(manifest["items"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        inspect_synthetic_evidence_manifest(lifecycle, manifest)
    manifest["items"].pop()
    manifest["incident_id"] = "foreign"
    with pytest.raises(ValueError, match="scope"):
        inspect_synthetic_evidence_manifest(lifecycle, manifest)


def test_untrusted_manifest_cannot_assert_approval():
    lifecycle, manifest = fixture_manifest()
    manifest["items"][0]["approved"] = True
    with pytest.raises(ValueError, match="shape"):
        inspect_synthetic_evidence_manifest(lifecycle, manifest)


def test_forged_lifecycle_pass_rejected():
    lifecycle, manifest = fixture_manifest()
    lifecycle["stages"][0]["evidence_state"] = "PASS"
    with pytest.raises(ValueError, match="unqualified_itil_stage"):
        inspect_synthetic_evidence_manifest(lifecycle, manifest)
