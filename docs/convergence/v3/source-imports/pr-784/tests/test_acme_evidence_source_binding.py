"""Source MAC authenticity does not establish runtime observation or tenant ACL."""
import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_lifecycle_read_model import build_synthetic_incident_lifecycle
from portal.acme_evidence_source_binding import inspect_source_bound_receipts

KEY = b"source-key-from-trusted-resolver-32bytes"


def fixture():
    lifecycle = build_synthetic_incident_lifecycle()
    item = {
        "checkpoint": "detect", "source": "grafana",
        "evidence_type": "ALERT_STATE", "source_id": "alert:01",
        "observed_at": "2026-11-14T12:00:00Z", "content_sha256": "a" * 64,
    }
    manifest = {
        "schema": "aiops.synthetic-evidence-manifest.v1",
        "mode": "DEMO", "source_sha256": lifecycle["source_sha256"],
        "incident_id": lifecycle["source_incident_id"], "items": [item],
    }
    receipt = {
        "schema": "aiops.synthetic-source-bound-receipt.v1",
        "mode": "DEMO", "tenant_id": "acme-demo",
        "checkpoint": "detect", "source": "grafana",
        "source_id": item["source_id"], "content_sha256": item["content_sha256"],
        "observed_at": item["observed_at"], "source_sha256": lifecycle["source_sha256"],
    }
    raw = json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode()
    receipt["mac_sha256"] = hmac.new(KEY, raw, hashlib.sha256).hexdigest()
    return lifecycle, manifest, receipt


def resolver(tenant, source):
    assert (tenant, source) == ("acme-demo", "grafana")
    return KEY


def test_valid_mac_is_not_runtime_attestation():
    lifecycle, manifest, receipt = fixture()
    report = inspect_source_bound_receipts(lifecycle, manifest, [receipt], resolver)
    assert report["valid_source_mac_count"] == 1
    assert report["results"][0]["receipt_integrity"] == "MAC_VALID_SOURCE_KEY_UNATTESTED"
    assert report["results"][0]["tenant_actor_authorized"] is False
    assert report["runtime_attested_count"] == 0
    assert report["evidence_accepted"] is False
    assert report["live_remediation_authorized"] is False


def test_wrong_key_and_resolver_failure_fail_closed():
    lifecycle, manifest, receipt = fixture()
    bad = inspect_source_bound_receipts(lifecycle, manifest, [receipt], lambda *_: b"x" * 32)
    assert bad["results"][0]["receipt_integrity"] == "MAC_MISMATCH"
    def fail(*_):
        raise RuntimeError("sensitive source secret")
    unavailable = inspect_source_bound_receipts(lifecycle, manifest, [receipt], fail)
    assert unavailable["results"][0]["receipt_integrity"] == "SOURCE_KEY_UNAVAILABLE"
    assert "sensitive source secret" not in str(unavailable)


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "other-tenant"),
    ("source", "glpi"),
    ("source_id", "alert:other"),
    ("content_sha256", "b" * 64),
    ("observed_at", "2026-11-14T12:01:00Z"),
])
def test_receipt_binding_rejects_substitution(field, value):
    lifecycle, manifest, receipt = fixture()
    receipt[field] = value
    if field == "tenant_id":
        # Tenant substitution is MAC-protected, even if a key resolver accepts it.
        report = inspect_source_bound_receipts(lifecycle, manifest, [receipt], lambda *_: KEY)
        assert report["results"][0]["receipt_integrity"] == "MAC_MISMATCH"
    else:
        with pytest.raises(ValueError, match="binding_mismatch"):
            inspect_source_bound_receipts(lifecycle, manifest, [receipt], resolver)


def test_duplicate_receipt_and_forged_approval_rejected():
    lifecycle, manifest, receipt = fixture()
    with pytest.raises(ValueError, match="duplicate"):
        inspect_source_bound_receipts(lifecycle, manifest, [receipt, receipt], resolver)
    receipt["approved"] = True
    with pytest.raises(ValueError, match="shape"):
        inspect_source_bound_receipts(lifecycle, manifest, [receipt], resolver)
