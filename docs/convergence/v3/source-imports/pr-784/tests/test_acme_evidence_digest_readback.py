"""Digest match is not source authentication, ITIL approval or LIVE evidence."""
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_lifecycle_read_model import build_synthetic_incident_lifecycle
from portal.acme_evidence_digest_readback import compare_synthetic_evidence_readbacks


def sample():
    lifecycle = build_synthetic_incident_lifecycle()
    payload = b"independent readback bytes"
    manifest = {
        "schema": "aiops.synthetic-evidence-manifest.v1",
        "mode": "DEMO",
        "source_sha256": lifecycle["source_sha256"],
        "incident_id": lifecycle["source_incident_id"],
        "items": [{
            "checkpoint": "detect", "source": "grafana",
            "evidence_type": "ALERT_STATE", "source_id": "alert:001",
            "observed_at": "2026-11-14T12:00:00Z",
            "content_sha256": hashlib.sha256(payload).hexdigest(),
        }],
    }
    return lifecycle, manifest, payload


def test_digest_match_remains_unattested_and_no_go():
    lifecycle, manifest, payload = sample()
    calls = []
    def readback(source, source_id):
        calls.append((source, source_id))
        return payload
    result = compare_synthetic_evidence_readbacks(lifecycle, manifest, readback)
    assert calls == [("grafana", "alert:001")]
    assert result["digest_match_count"] == 1
    assert result["comparisons"][0]["comparison_state"] == "DIGEST_MATCH_UNATTESTED"
    assert result["comparisons"][0]["source_identity_authenticated"] is False
    assert result["comparisons"][0]["tenant_scope_verified"] is False
    assert result["independently_attested_count"] == 0
    assert result["evidence_accepted"] is False
    assert result["itil_transition_authorized"] is False
    assert result["live_remediation_authorized"] is False


def test_mismatch_and_callback_failure_fail_closed():
    lifecycle, manifest, payload = sample()
    mismatch = compare_synthetic_evidence_readbacks(lifecycle, manifest, lambda *_: b"other")
    assert mismatch["comparisons"][0]["comparison_state"] == "DIGEST_MISMATCH"
    def failure(*_):
        raise RuntimeError("secret bearer must not leak")
    failed = compare_synthetic_evidence_readbacks(lifecycle, manifest, failure)
    assert failed["comparisons"][0]["comparison_state"] == "READBACK_UNAVAILABLE"
    assert "secret bearer" not in str(failed)
    assert failed["independently_attested_count"] == 0


@pytest.mark.parametrize("readback", [lambda *_: b"", lambda *_: "not bytes",
                                       lambda *_: b"x" * (1024 * 1024 + 1)])
def test_bad_readback_never_accepted(readback):
    lifecycle, manifest, _ = sample()
    result = compare_synthetic_evidence_readbacks(lifecycle, manifest, readback)
    assert result["comparisons"][0]["comparison_state"] == "READBACK_UNAVAILABLE"
    assert result["evidence_accepted"] is False


def test_untrusted_manifest_rejected_before_readback():
    lifecycle, manifest, _ = sample()
    manifest["items"][0]["content_sha256"] = "INVALID"
    calls = []
    with pytest.raises(ValueError):
        compare_synthetic_evidence_readbacks(
            lifecycle, manifest, lambda *_: calls.append(True))
    assert calls == []


def test_callback_is_mandatory():
    lifecycle, manifest, _ = sample()
    with pytest.raises(ValueError, match="readback_callback_required"):
        compare_synthetic_evidence_readbacks(lifecycle, manifest, None)
