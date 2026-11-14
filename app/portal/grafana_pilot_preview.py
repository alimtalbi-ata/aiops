"""Safe preview of Grafana read-only evidence inside the SAN -> Payments pilot.

This preview never promotes injected transport data to VERIFIED and never
modifies the pilot evidence register. No network access is performed.
"""
from copy import deepcopy


def preview_grafana_pilot_evidence(register, projection):
    if not isinstance(register, dict) or not isinstance(projection, dict):
        raise ValueError("pilot_preview_invalid_input")
    if register.get("schema") != "aiops2.readonly-pilot-evidence-register.v1":
        raise ValueError("pilot_preview_register_schema_invalid")
    if register.get("live_actions_authorized") is not False:
        raise ValueError("pilot_preview_live_authorization_forbidden")
    sources = register.get("sources")
    if not isinstance(sources, dict) or not isinstance(sources.get("grafana"), dict):
        raise ValueError("pilot_preview_grafana_source_missing")
    if (projection.get("schema") != "aiops2.grafana-alert-evidence.v1"
            or projection.get("status") != "UNATTESTED"
            or projection.get("runtime_attested") is not False
            or projection.get("native_tenant_acl_verified") is not False
            or projection.get("live_actions_authorized") is not False):
        raise ValueError("pilot_preview_attestation_boundary_violation")
    if sources["grafana"].get("status") != "UNKNOWN":
        raise ValueError("pilot_preview_existing_source_must_be_unknown")
    for key in ("rule_uid", "dashboard_uid", "tenant_scope", "observed_at_utc",
                "service_identity", "response_sha256"):
        value = projection.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError("pilot_preview_" + key + "_invalid")
    # All fields are read from an untrusted, injected callback. They are hints,
    # never independently authenticated source evidence.
    result = deepcopy(register)
    result["decision"] = "BLOCKED"
    result["live_actions_authorized"] = False
    result["sources"]["grafana"].update({
        "status": "UNKNOWN",
        "rule_uid": projection["rule_uid"],
        "dashboard_uid": projection["dashboard_uid"],
        "tenant_scope": projection["tenant_scope"],
        "observed_at_utc": projection["observed_at_utc"],
        "service_identity": projection["service_identity"],
        "response_sha256": projection["response_sha256"],
        "evidence_refs": [],
    })
    return {
        "schema": "aiops2.grafana-pilot-preview.v1",
        "qualification": "UNKNOWN",
        "reason": "INJECTED_TRANSPORT_NOT_AUTHENTICATED",
        "runtime_attested": False,
        "live_actions_authorized": False,
        "register": result,
    }
