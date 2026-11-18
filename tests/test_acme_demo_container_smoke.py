"""Offline container smoke contract regression tests."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from portal.acme_demo_container_smoke import verify_packaged_demo


def test_packaged_demo_two_screens_remain_synthetic():
    result = verify_packaged_demo()
    assert result["accepted"] is True
    assert result["scope"] == "LOCAL_SYNTHETIC_ONLY"
    assert result["runtime_attested"] is False
    assert result["live_actions_authorized"] is False
    assert len(result["source_sha256"]) == 64


def test_packaged_demo_rejects_forged_positive_register():
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def forged(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            payload["decision"] = "GO_READ_ONLY_PILOT"
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=forged):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()


@contextmanager
def patched_preview_endpoint(smoke, replacement):
    # Keep the registered endpoint and its renderer identical so the test
    # reaches the intended rendering failure rather than the route guard.
    original = smoke.acme_grafana_pilot_preview_page
    routes = [
        SimpleNamespace(path=route.path, methods=getattr(route, "methods", None),
                        endpoint=replacement if getattr(route, "endpoint", None) is original
                        else getattr(route, "endpoint", None))
        for route in smoke.portal_app.routes
    ]
    with patch.object(smoke.portal_app.router, "routes", routes):
        with patch.object(smoke, "acme_grafana_pilot_preview_page", replacement):
            yield


def test_packaged_demo_rejects_missing_customer_screen():
    import portal.acme_demo_container_smoke as smoke
    def unavailable():
        raise ValueError("unavailable")

    with patched_preview_endpoint(smoke, unavailable):
        with pytest.raises(ValueError, match="unavailable"):
            verify_packaged_demo()

def test_packaged_demo_rejects_missing_evidence_source():
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def incomplete(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            del payload["sources"]["independent_postcheck"]
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=incomplete):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()

@pytest.mark.parametrize("mutation", ["forged_pass", "forged_evidence_ref", "missing_negative_test"])
def test_packaged_demo_rejects_forged_pilot_evidence(mutation):
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def forged(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            if mutation == "forged_pass":
                payload["negative_tests"]["cross_tenant_zero_upstream_calls"] = "PASS"
            elif mutation == "forged_evidence_ref":
                payload["sources"]["grafana"]["evidence_refs"] = ["fabricated"]
            else:
                del payload["negative_tests"]["n8n_existing_execution_no_replay"]
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=forged):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()

@pytest.mark.parametrize("mutation", ["root_array", "source_null", "schema_invalid"])
def test_packaged_demo_rejects_malformed_register_shapes(mutation):
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def malformed(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            if mutation == "root_array":
                return json.dumps([payload])
            if mutation == "source_null":
                payload["sources"]["grafana"] = None
            else:
                payload["schema"] = "unknown"
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=malformed):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()

@pytest.mark.parametrize("mutation", ["fabricated_grafana_digest", "assigned_environment", "claimed_temporal_start"])
def test_packaged_demo_rejects_claimed_runtime_metadata(mutation):
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def forged(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            if mutation == "fabricated_grafana_digest":
                payload["sources"]["grafana"]["response_sha256"] = "f" * 64
            elif mutation == "assigned_environment":
                payload["environment"]["name"] = "production"
            else:
                payload["sources"]["core_temporal"]["start_intent_present"] = True
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=forged):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()

def test_packaged_demo_rejects_broken_customer_navigation():
    import portal.acme_demo_container_smoke as smoke
    original = smoke.acme_grafana_pilot_preview_page

    def broken():
        response = original()
        response.body = response.body.replace(
            b"href='/demo/acme-incident-cockpit'",
            b"href='/demo/missing-cockpit'",
        )
        return response

    with patched_preview_endpoint(smoke, broken):
        with pytest.raises(ValueError, match="synthetic_customer_navigation_missing"):
            verify_packaged_demo()

def test_packaged_demo_rejects_customer_route_with_write_method():
    import portal.acme_demo_container_smoke as smoke
    from types import SimpleNamespace

    routes = [SimpleNamespace(path=route.path, endpoint=getattr(route, "endpoint", None),
                              methods=getattr(route, "methods", None))
              for route in smoke.portal_app.routes]
    for route in routes:
        if route.path == "/demo/acme-incident-cockpit":
            route.methods = {"GET", "POST"}
    with patch.object(smoke.portal_app.router, "routes", routes):
        with pytest.raises(ValueError, match="synthetic_customer_route_not_get_only"):
            verify_packaged_demo()


def test_packaged_demo_rejects_unexpected_null_source_field():
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def forged(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            payload["sources"]["grafana"]["unreviewed_claim"] = None
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=forged):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()


def test_packaged_demo_rejects_unreviewed_top_level_claim():
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def forged(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            payload["real_glpi_verified"] = True
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=forged):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()


def test_packaged_demo_rejects_forged_operator_trust_notes():
    import portal.acme_demo_container_smoke as smoke
    original = Path.read_text

    def forged(path, *args, **kwargs):
        if str(path).endswith("acme-readonly-pilot-register.template.json"):
            payload = json.loads(original(path, *args, **kwargs))
            payload["notes"] = ["GLPI, Grafana and Temporal are fully verified in production."]
            return json.dumps(payload)
        return original(path, *args, **kwargs)

    with patch.object(smoke.Path, "read_text", new=forged):
        with pytest.raises(ValueError, match="packaged_register_not_blocked"):
            verify_packaged_demo()
