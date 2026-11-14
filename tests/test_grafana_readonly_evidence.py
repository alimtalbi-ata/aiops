import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.grafana_readonly_evidence import collect_grafana_alert_readonly

NOW = "2026-11-14T12:00:00Z"
PAYLOAD = {"rule_uid":"san-p1", "tenant_id":"acme-test", "dashboard_uid":"san-ops",
           "state":"firing", "observed_at_utc":"2026-11-14T11:59:00Z"}

def collect(callback, **kwargs):
    return collect_grafana_alert_readonly(fetch_alert=callback, rule_uid="san-p1",
        tenant_id="acme-test", service_identity="grafana-test-reader",
        max_age_seconds=300, now_utc=NOW, **kwargs)

def test_readonly_projection_is_explicitly_unattested():
    calls=[]
    def fetch(rule, tenant):
        calls.append((rule,tenant)); return dict(PAYLOAD)
    r=collect(fetch)
    assert calls==[("san-p1","acme-test")]
    assert r["status"]=="UNATTESTED"
    assert r["runtime_attested"] is False
    assert r["native_tenant_acl_verified"] is False
    assert r["live_actions_authorized"] is False
    assert len(r["response_sha256"])==64

def test_cross_tenant_response_is_rejected():
    with pytest.raises(ValueError,match="grafana_tenant_or_rule_mismatch"):
        collect(lambda *_:{**PAYLOAD,"tenant_id":"other-tenant"})

def test_cross_rule_response_is_rejected():
    with pytest.raises(ValueError,match="grafana_tenant_or_rule_mismatch"):
        collect(lambda *_:{**PAYLOAD,"rule_uid":"other-rule"})

def test_stale_and_future_evidence_are_rejected():
    for observed in ("2026-11-14T11:54:59Z","2026-11-14T12:00:01Z"):
        with pytest.raises(ValueError,match="grafana_alert_stale_or_future"):
            collect(lambda *_:{**PAYLOAD,"observed_at_utc":observed})

def test_unscoped_request_never_invokes_transport():
    calls=[]
    with pytest.raises(ValueError,match="grafana_request_scope_invalid"):
        collect_grafana_alert_readonly(fetch_alert=lambda *_:calls.append(True),
            rule_uid="san-p1",tenant_id="",service_identity="reader",
            max_age_seconds=300,now_utc=NOW)
    assert calls==[]

def test_wrong_fingerprint_is_rejected():
    with pytest.raises(ValueError,match="grafana_fingerprint_mismatch"):
        collect(lambda *_:dict(PAYLOAD),expected_fingerprint="0"*64)

def test_invalid_alert_state_is_rejected():
    with pytest.raises(ValueError,match="grafana_alert_state_invalid"):
        collect(lambda *_:{**PAYLOAD,"state":"unknown"})
