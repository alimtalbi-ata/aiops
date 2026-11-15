"""Cross-layer offline E2E acceptance: real Portal HTTP + computed decision pipeline."""
import copy
import json
import socket
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app"))
from aiops2_noc_decision import build_noc_decision
from aiops2_noc_decision_html import render_computed_noc_html
from portal.main import app

NOW = "2026-11-15T12:00:00Z"


def event(tenant, source, identity, ci, severity="P2"):
    return dict(tenant_id=tenant, source=source, source_event_id=identity,
                ci_id=ci, service_id="payments", severity=severity,
                evidence_sha256=("a" if source == "checkmk" else "b") * 64,
                observed_at="2026-11-15T11:59:00Z", known_at="2026-11-15T11:59:05Z")


def edge(tenant, origin, destination):
    return dict(tenant_id=tenant, from_id=origin, to_id=destination,
                source_id="synthetic-cmdb", evidence_sha256="c" * 64,
                observed_at="2026-11-15T11:59:00Z")


def test_cross_layer_san_payments_tenant_isolation_and_replay():
    events = [event("acme", "checkmk", "san", "san-01", "P1"),
              event("acme", "prometheus", "pay", "payments-api"),
              event("other", "checkmk", "san", "san-01", "P1")]
    edges = [edge("acme", "san-01", "storage"), edge("acme", "storage", "payments")]
    original = copy.deepcopy((events, edges))
    result = build_noc_decision(events, edges, as_of=NOW)
    assert len(result["decisions"]) == 2
    tenants = {d["tenant_id"]: d for d in result["decisions"]}
    assert tenants["acme"]["impact_state"] == "SOURCED_SYNTHETIC_PATH"
    assert tenants["other"]["impact_state"] == "UNKNOWN"
    assert tenants["acme"]["event_count"] == 2
    assert all(d["policy_disposition"] == "DENY_LIVE" for d in result["decisions"])
    assert all(d["live_remediation_authorized"] is False for d in result["decisions"])
    assert result == build_noc_decision(list(reversed(events)), list(reversed(edges)), as_of=NOW)
    assert (events, edges) == original
    html = render_computed_noc_html(result)
    assert "san-01 → storage → payments" in html
    assert "COLLECT_MISSING_DEPENDENCY_EVIDENCE" in html
    assert "DENY_LIVE" in html and "SIMULATION" in html
    assert "<script" not in html.lower()
    assert json.loads(json.dumps(result)) == result


def test_cross_layer_conflicting_identity_and_stale_graph_fail_closed():
    first = event("acme", "checkmk", "san", "san-01", "P1")
    conflict = dict(first, ci_id="unrelated-ci")
    result = build_noc_decision([first, conflict],
                                [edge("acme", "san-01", "payments")], as_of=NOW)
    assert result["decisions"] == []
    assert result["rejected_events"]
    stale = edge("acme", "san-01", "payments")
    stale["observed_at"] = "2026-11-13T10:00:00Z"
    result = build_noc_decision([first], [stale], as_of=NOW)
    assert result["decisions"][0]["impact_state"] == "UNKNOWN"
    assert result["decisions"][0]["next_noc_action"] == "COLLECT_MISSING_DEPENDENCY_EVIDENCE"


def test_integrated_portal_http_e2e_offline_and_write_denial(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("unexpected external network I/O")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    client = TestClient(app)
    home = client.get("/")
    assert home.status_code == 200
    assert "/demo/aiops2-computed-noc" in home.text
    api = client.get("/demo/api/aiops2-computed-noc")
    html = client.get("/demo/aiops2-computed-noc")
    assert api.status_code == html.status_code == 200
    projection = api.json()
    assert projection["mode"] == "SIMULATION"
    assert projection["runtime_attested"] is False
    assert projection["live_remediation_authorized"] is False
    assert projection["decisions"][0]["policy_disposition"] == "DENY_LIVE"
    assert "san-01 → storage → payments" in html.text
    assert "SIMULATION" in html.text and "DENY_LIVE" in html.text
    for response in (api, html):
        assert response.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in response.headers["content-security-policy"]
    for route in ("/demo/aiops2-computed-noc", "/demo/api/aiops2-computed-noc"):
        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)(route).status_code == 405


def test_integrated_portal_protected_reads_and_commands_fail_closed(monkeypatch):
    """Unconfigured portal must not expose protected runtime data or accept commands."""
    for key in ("PORTAL_READ_TOKEN", "PORTAL_OPERATOR_TOKEN", "PORTAL_READ_TOKEN_SHA256",
                "PORTAL_OPERATOR_TOKEN_SHA256"):
        monkeypatch.delenv(key, raising=False)
    def no_network(*args, **kwargs):
        raise AssertionError("unexpected external network I/O")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    client = TestClient(app)
    for path in ("/api/portal/bootstrap", "/api/portal/components",
                 "/api/noc/runtime-state", "/api/noc/correlation"):
        response = client.get(path)
        assert response.status_code in (401, 403, 503), (path, response.text)
        assert "tenant_acl_qualified" not in response.text
    for path in ("/api/demo", "/api/copilot", "/api/demo/explore-story/control"):
        response = client.post(path, json={})
        assert response.status_code in (401, 403, 503), (path, response.text)
        assert "DEMO_SUBMITTED" not in response.text
