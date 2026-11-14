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


def verify_packaged_demo() -> dict[str, object]:
    template = Path(__file__).resolve().with_name(
        "acme-readonly-pilot-register.template.json"
    )
    register = json.loads(template.read_text(encoding="utf-8"))
    if (register.get("decision") != "BLOCKED"
            or register.get("live_actions_authorized") is not False
            or not isinstance(register.get("sources"), dict)
            or not register["sources"]
            or any(not isinstance(v, dict) or v.get("status") != "UNKNOWN"
                   for v in register["sources"].values())):
        raise ValueError("packaged_register_not_blocked")

    grafana = acme_grafana_pilot_preview_page()
    cockpit = acme_incident_cockpit_page()
    if grafana.status_code != 200 or cockpit.status_code != 200:
        raise ValueError("synthetic_customer_pages_unavailable")
    if (b"UNKNOWN / BLOCKED" not in grafana.body
            or b"NO-GO LIVE" not in cockpit.body
            or b"<script" in grafana.body.lower()
            or b"<script" in cockpit.body.lower()):
        raise ValueError("synthetic_customer_safety_markers_missing")
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
