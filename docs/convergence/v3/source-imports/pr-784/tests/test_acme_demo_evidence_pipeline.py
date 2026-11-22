"""Real offline composition with explicit injected readback/key callbacks."""
import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_demo_evidence_pipeline import inspect_acme_demo_evidence
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from portal.acme_impact_read_model import build_acme_impact_read_model

KEY = b"k" * 32
DATA = b"offline alert snapshot only"


def sample():
    cockpit = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    manifest = {
        "schema": "aiops.synthetic-evidence-manifest.v1", "mode": "DEMO",
        "source_sha256": cockpit["source_sha256"],
        "incident_id": cockpit["incident_id"],
        "items": [{
            "checkpoint": "detect", "source": "grafana",
            "evidence_type": "ALERT_STATE", "source_id": "offline-alert-01",
            "observed_at": "2026-11-14T10:00:00Z",
            "content_sha256": hashlib.sha256(DATA).hexdigest(),
        }],
    }
    item = manifest["items"][0]
    signed = {
        "schema": "aiops.synthetic-source-bound-receipt.v1", "mode": "DEMO",
        "tenant_id": "acme-demo", "checkpoint": "detect", "source": "grafana",
        "source_id": item["source_id"], "observed_at": item["observed_at"],
        "content_sha256": item["content_sha256"],
        "source_sha256": cockpit["source_sha256"],
    }
    mac = hmac.new(KEY, json.dumps(signed, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":"), allow_nan=False).encode(),
                   hashlib.sha256).hexdigest()
    return manifest, [dict(signed, mac_sha256=mac)]


def test_full_integrity_match_still_no_runtime_recovery():
    manifest, receipts = sample()
    seen = []
    def readback(source, source_id):
        seen.append((source, source_id))
        return DATA
    result = inspect_acme_demo_evidence(
        manifest, receipts, readback, lambda tenant, source: KEY,
        expected_tenant_id="acme-demo")
    assert seen == [("grafana", "offline-alert-01")]
    assert result["evidence_qualification"]["integrity_consistent_unattested_count"] == 1
    assert result["evidence_gate"]["evidence_integrity_consistent_unattested_count"] == 1
    assert result["actual_recovery_state"] == "UNKNOWN"
    assert result["itil_transition_authorized"] is False
    assert result["live_remediation_authorized"] is False


def test_foreign_tenant_denied_before_any_callback():
    manifest, receipts = sample()
    calls = []
    def forbidden(*args):
        calls.append(args)
        raise AssertionError("callback must not run")
    with pytest.raises(ValueError, match="receipt_tenant_scope_mismatch"):
        inspect_acme_demo_evidence(
            manifest, receipts, forbidden, forbidden, expected_tenant_id="other-tenant")
    assert calls == []


def test_wrong_mac_never_triggers_readback():
    manifest, receipts = sample()
    receipts[0]["mac_sha256"] = "0" * 64
    seen = []
    def readback(*args):
        seen.append(args)
        return DATA
    result = inspect_acme_demo_evidence(
        manifest, receipts, readback, lambda *_: KEY,
        expected_tenant_id="acme-demo")
    assert seen == []
    assert result["evidence_gate"]["evidence_integrity_consistent_unattested_count"] == 0
    assert result["actual_recovery_state"] == "UNKNOWN"


def test_foreign_incident_manifest_rejected_before_callbacks():
    manifest, receipts = sample()
    manifest["incident_id"] = "OTHER-INCIDENT"
    calls = []
    def forbidden(*args):
        calls.append(args)
        return KEY
    with pytest.raises(ValueError, match="evidence_manifest_scope"):
        inspect_acme_demo_evidence(
            manifest, receipts, forbidden, forbidden, expected_tenant_id="acme-demo")
    assert calls == []
