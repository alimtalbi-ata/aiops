"""A valid source MAC plus matching bytes still cannot authorize remediation."""
import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_lifecycle_read_model import build_synthetic_incident_lifecycle
from portal.acme_evidence_joint_qualification import qualify_synthetic_evidence_jointly

KEY = b"independent-trusted-source-secret-32bytes"


def sample():
    lifecycle = build_synthetic_incident_lifecycle()
    raw = b"synthetic independent observation"
    item = {
        "checkpoint": "detect", "source": "grafana",
        "evidence_type": "ALERT_STATE", "source_id": "alert:001",
        "observed_at": "2026-11-14T12:00:00Z",
        "content_sha256": hashlib.sha256(raw).hexdigest(),
    }
    manifest = {
        "schema": "aiops.synthetic-evidence-manifest.v1", "mode": "DEMO",
        "source_sha256": lifecycle["source_sha256"],
        "incident_id": lifecycle["source_incident_id"], "items": [item],
    }
    receipt = {
        "schema": "aiops.synthetic-source-bound-receipt.v1", "mode": "DEMO",
        "tenant_id": "acme-demo", "checkpoint": "detect",
        "source": "grafana", "source_id": item["source_id"],
        "content_sha256": item["content_sha256"],
        "observed_at": item["observed_at"],
        "source_sha256": lifecycle["source_sha256"],
    }
    body = json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode()
    receipt["mac_sha256"] = hmac.new(KEY, body, hashlib.sha256).hexdigest()
    return lifecycle, manifest, receipt, raw


def qualify(lifecycle, manifest, receipts, readback):
    return qualify_synthetic_evidence_jointly(
        lifecycle, manifest, receipts, readback, lambda *_: KEY,
        expected_tenant_id="acme-demo")


def test_both_checks_match_but_no_runtime_or_itil_authority():
    lifecycle, manifest, receipt, raw = sample()
    result = qualify(lifecycle, manifest, [receipt], lambda *_: raw)
    assert result["integrity_consistent_unattested_count"] == 1
    assert result["checkpoints"][0]["integrity_consistent_unattested"] is True
    assert result["independently_attested_count"] == 0
    assert result["overall_qualification"] == "UNKNOWN"
    assert result["evidence_accepted"] is False
    assert result["itil_transition_authorized"] is False
    assert result["live_remediation_authorized"] is False


def test_wrong_mac_cannot_be_rescued_by_matching_bytes():
    lifecycle, manifest, receipt, raw = sample()
    receipt["mac_sha256"] = "f" * 64
    result = qualify(lifecycle, manifest, [receipt], lambda *_: raw)
    assert result["checkpoints"][0]["digest_state"] == "READBACK_UNAVAILABLE"
    assert result["checkpoints"][0]["source_receipt_state"] == "MAC_MISMATCH"
    assert result["integrity_consistent_unattested_count"] == 0


def test_wrong_bytes_cannot_be_rescued_by_valid_mac():
    lifecycle, manifest, receipt, _ = sample()
    result = qualify(lifecycle, manifest, [receipt], lambda *_: b"tampered")
    assert result["checkpoints"][0]["digest_state"] == "DIGEST_MISMATCH"
    assert result["integrity_consistent_unattested_count"] == 0


def test_missing_receipt_remains_unqualified():
    lifecycle, manifest, _, raw = sample()
    result = qualify(lifecycle, manifest, [], lambda *_: raw)
    assert result["checkpoints"][0]["source_receipt_state"] == "SOURCE_RECEIPT_MISSING"
    assert result["integrity_consistent_unattested_count"] == 0


def test_forged_manifest_fails_before_any_callback():
    lifecycle, manifest, receipt, raw = sample()
    manifest["items"][0]["content_sha256"] = "INVALID"
    calls = []
    with pytest.raises(ValueError):
        qualify_synthetic_evidence_jointly(
            lifecycle, manifest, [receipt],
            lambda *_: calls.append("readback") or raw,
            lambda *_: calls.append("resolver") or KEY,
            expected_tenant_id="acme-demo",
        )
    assert calls == []


def test_foreign_tenant_receipt_rejected_before_any_callback():
    lifecycle, manifest, receipt, raw = sample()
    receipt["tenant_id"] = "other-tenant"
    calls = []
    with pytest.raises(ValueError, match="receipt_tenant_scope_mismatch"):
        qualify_synthetic_evidence_jointly(
            lifecycle, manifest, [receipt],
            lambda *_: calls.append("readback") or raw,
            lambda *_: calls.append("resolver") or KEY,
            expected_tenant_id="acme-demo",
        )
    assert calls == []


def test_expected_tenant_must_be_supplied_by_trusted_caller():
    lifecycle, manifest, receipt, raw = sample()
    with pytest.raises(TypeError):
        qualify_synthetic_evidence_jointly(
            lifecycle, manifest, [receipt], lambda *_: raw, lambda *_: KEY)
    with pytest.raises(ValueError, match="trusted_expected_tenant_required"):
        qualify_synthetic_evidence_jointly(
            lifecycle, manifest, [receipt], lambda *_: raw, lambda *_: KEY,
            expected_tenant_id="")


def test_invalid_mac_prevents_external_readback():
    lifecycle, manifest, receipt, raw = sample()
    receipt["mac_sha256"] = "f" * 64
    calls = []
    result = qualify(lifecycle, manifest, [receipt],
                     lambda *_: calls.append("external-read") or raw)
    assert calls == []
    assert result["checkpoints"][0]["digest_state"] == "READBACK_UNAVAILABLE"
    assert result["checkpoints"][0]["source_receipt_state"] == "MAC_MISMATCH"


def test_missing_receipt_prevents_external_readback():
    lifecycle, manifest, _, raw = sample()
    calls = []
    result = qualify(lifecycle, manifest, [],
                     lambda *_: calls.append("external-read") or raw)
    assert calls == []
    assert result["checkpoints"][0]["digest_state"] == "READBACK_UNAVAILABLE"
    assert result["checkpoints"][0]["source_receipt_state"] == "SOURCE_RECEIPT_MISSING"
