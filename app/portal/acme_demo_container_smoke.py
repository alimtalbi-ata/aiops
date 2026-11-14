"""Offline smoke contract for the packaged SAN -> Payments customer demo.

Run inside the Portal image with --network none. This proves only local
synthetic presentation and never attests Grafana, GLPI, Temporal or LIVE.
"""
from __future__ import annotations

import json
from pathlib import Path

from portal.acme_impact_read_model import (
    acme_grafana_pilot_preview_page,
    acme_incident_cockpit_page,
    build_acme_impact_read_model,
)
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from portal.main import app as portal_app


def verify_packaged_demo() -> dict[str, object]:
    template = Path(__file__).resolve().with_name(
        "acme-readonly-pilot-register.template.json"
    )
    register = json.loads(template.read_text(encoding="utf-8"))
    expected_sources = {"oidc", "grafana", "n8n", "glpi_cmdb", "core_temporal", "policy_hitl", "independent_postcheck"}
    expected_negative_tests = {
        "cross_tenant_zero_upstream_calls",
        "cross_entity_zero_upstream_calls",
        "revoked_actor_zero_upstream_calls",
        "replayed_token_zero_upstream_calls",
        "glpi_acl_denial_zero_upstream_reads",
        "temporal_inspection_no_start_or_restart",
        "n8n_existing_execution_no_replay",
    }
    expected_environment = {
        "name": "UNASSIGNED", "owner": "UNASSIGNED",
        "is_ephemeral": None, "created_at_utc": None,
        "expires_at_utc": None, "destruction_record": None,
    }
    permitted_source_fields = {
        "status": "UNKNOWN", "evidence_refs": [],
        "arguments_comparison": "UNKNOWN", "execution_outcome": "UNKNOWN",
        "decision": "UNKNOWN",
    }
    if (not isinstance(register, dict)
            or register.get("schema") != "aiops2.readonly-pilot-evidence-register.v1"
            or register.get("pilot_id") != "UNASSIGNED"
            or register.get("git_revision") is not None
            or register.get("environment") != expected_environment
            or register.get("decision") != "BLOCKED"
            or register.get("live_actions_authorized") is not False
            or not isinstance(register.get("sources"), dict)
            or set(register["sources"]) != expected_sources
            or not isinstance(register.get("negative_tests"), dict)
            or set(register["negative_tests"]) != expected_negative_tests
            or any(value != "NOT_RUN" for value in register["negative_tests"].values())
            or any(not isinstance(v, dict) or v.get("status") != "UNKNOWN"
                   or v.get("evidence_refs") != []
                   or any(field not in permitted_source_fields or
                          value != permitted_source_fields[field]
                          for field, value in v.items())
                   or any(v.get(field) != permitted_source_fields[field]
                          for field in ("arguments_comparison", "execution_outcome", "decision")
                          if field in v)
                   for v in register["sources"].values())):
        raise ValueError("packaged_register_not_blocked")

    customer_routes = {
        "/demo/acme-incident-cockpit": acme_incident_cockpit_page,
        "/demo/acme-grafana-pilot-preview": acme_grafana_pilot_preview_page,
    }
    for path, endpoint in customer_routes.items():
        matches = [route for route in portal_app.routes if getattr(route, "path", None) == path]
        if (len(matches) != 1 or matches[0].endpoint is not endpoint
                or matches[0].methods != {"GET"}):
            raise ValueError("synthetic_customer_route_not_get_only")

    grafana = acme_grafana_pilot_preview_page()
    cockpit = acme_incident_cockpit_page()
    if grafana.status_code != 200 or cockpit.status_code != 200:
        raise ValueError("synthetic_customer_pages_unavailable")
    if (b"UNKNOWN / BLOCKED" not in grafana.body
            or b"NO-GO LIVE" not in cockpit.body
            or b"<script" in grafana.body.lower()
            or b"<script" in cockpit.body.lower()):
        raise ValueError("synthetic_customer_safety_markers_missing")
    if (b"href='/demo/acme-grafana-pilot-preview'" not in cockpit.body
            or b"href='/demo/acme-incident-cockpit'" not in grafana.body):
        raise ValueError("synthetic_customer_navigation_missing")
    for response in (grafana, cockpit):
        if (response.headers.get("cache-control") != "no-store"
                or "default-src 'none'" not in
                response.headers.get("content-security-policy", "")):
            raise ValueError("synthetic_customer_security_headers_missing")

    scenario = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    if (scenario.get("overall_qualification") != "UNKNOWN"
            or scenario.get("runtime_attested") is not False
            or scenario.get("live_remediation_authorized") is not False):
        raise ValueError("synthetic_scenario_unqualified")
    for field in ("incident_id", "business_impact_incident_id", "source_sha256"):
        value = str(scenario[field]).encode("utf-8")
        if value not in grafana.body or value not in cockpit.body:
            raise ValueError("synthetic_scenario_correlation_missing")
    return {
        "schema": "aiops2.packaged-demo-smoke.v1",
        "accepted": True,
        "scope": "LOCAL_SYNTHETIC_ONLY",
        "runtime_attested": False,
        "live_actions_authorized": False,
        "incident_id": scenario["incident_id"],
        "source_sha256": scenario["source_sha256"],
    }


if __name__ == "__main__":
    print(json.dumps(verify_packaged_demo(), sort_keys=True))
