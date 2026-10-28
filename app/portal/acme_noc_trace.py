"""Read-only ACME NOC projection from the canonical synthetic scenario.

Metric values are absent until an authorized real Grafana datasource is wired.
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Header, HTTPException
from portal.acme_impact_read_model import _load_or_503
from portal.acme_scenario_contract import build_acme_scenario_contract
from portal.noc_demo_rag import build_demo_rag
from portal.noc_runtime import _require_portal_read_auth, _noc_json_response
from shared.tenant_scope import reject_unqualified_tenant_scope

router = APIRouter()
SCHEMA = "aiops.acme-noc-trace.v1"
CLOCK = "2026-10-25T09:00:00Z"


def build_trace(model: dict) -> dict:
    reject_unqualified_tenant_scope(model)
    contract = build_acme_scenario_contract(model)
    if (model.get("simulation_checkpoint_timestamp_utc") != CLOCK
            or model.get("simulation_timestamp_provenance") != "FIXED_SCENARIO_CLOCK_NOT_RUNTIME_EVENT"):
        raise ValueError("unqualified virtual clock")
    hosts = [ci for ci in model.get("affected_cis", [])
             if isinstance(ci, dict) and ci.get("id") == "HOST-ESX-01"]
    if len(hosts) != 1 or hosts[0].get("name") != "esx-acme-01":
        raise ValueError("unqualified asset mapping")
    rag = build_demo_rag(hosts[0]["name"])
    if (rag.get("asset") != "esx-acme-01"
            or rag.get("data_classification") != "SYNTHETIC_SIMULATION_ONLY"
            or rag.get("source_runtime_observed") is not False
            or rag.get("llm_inference_performed") is not False
            or rag.get("tenant_acl_qualified") is not False
            or rag.get("state") not in ("SYNTHETIC_REFERENCE_ONLY", "UNKNOWN")):
        raise ValueError("unqualified RAG catalog")
    citations = rag.get("citations")
    if not isinstance(citations, list) or len(citations) > 8:
        raise ValueError("invalid citations")
    if bool(citations) != (rag["state"] == "SYNTHETIC_REFERENCE_ONLY"):
        raise ValueError("inconsistent RAG state")
    for row in citations:
        if (row.get("asset") != "esx-acme-01"
                or row.get("provenance") != "SYNTHETIC_SIMULATION_ONLY"):
            raise ValueError("unqualified RAG citation")
    anchor = datetime(2026, 10, 25, 9, tzinfo=timezone.utc)
    events = [{
        "event_id": event["id"], "cue": event["cue"], "service": event["service"],
        "status": "MISSING", "event_timestamp_utc": None,
        "virtual_offset_seconds": (event["sequence"] - 1) * 60,
        "virtual_time_utc": (anchor + timedelta(minutes=event["sequence"] - 1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    } for event in contract["events"]]
    return {
        "schema": SCHEMA, "scenario_schema": contract["schema"],
        "mode": "DEMO", "state": "SIMULATED_UNVERIFIED", "provenance": "SIMULATED_TARGET",
        "source_sha256": contract["source_sha256"],
        "run_id": contract["scenario"]["run_id"],
        "incident_id": contract["scenario"]["incident_id"],
        "impact_incident_id": contract["scenario"]["impact_incident_id"],
        "impact_path": contract["scenario"]["impact_path"],
        "virtual_clock": {"anchor_utc": CLOCK, "cadence_seconds": 60,
                          "provenance": "PRESENTATION_ONLY_NOT_RUNTIME_EVENT"},
        "events": events,
        "metrics": [
            {"id": "san_fc_crc_delta", "ci_id": "SAN-FABRIC-A", "label": "Erreurs CRC FC",
             "unit": "errors/min", "value": None, "state": "NOT_OBSERVED",
             "source": "GRAFANA_NOT_QUERIED"},
            {"id": "payments_p95_latency", "ci_id": "APP-PAY-01", "label": "Latence Payments p95",
             "unit": "ms", "value": None, "state": "NOT_OBSERVED",
             "source": "GRAFANA_NOT_QUERIED"},
        ],
        "diagnostic": {
            "state": "SYNTHETIC_HYPOTHESIS_ONLY" if citations else "UNKNOWN_NO_EXACT_SOURCE",
            "asset": "esx-acme-01", "catalog_sha256": rag["catalog_sha256"],
            "citations": [{"doc_id": c["doc_id"], "doc_sha256": c["doc_sha256"],
                           "asset": c["asset"], "provenance": c["provenance"]}
                          for c in citations],
            "llm_inference_performed": False,
        },
        "grafana_observation": "NOT_TESTED", "checkmk_thruk_observation": "NOT_TESTED",
        "tenant_acl_qualified": False, "runtime_attested": False,
        "production_qualified": False, "live_remediation_authorized": False,
        "backend_writes": False,
    }


@router.get("/api/noc/acme-trace")
def acme_noc_trace(authorization: str | None = Header(default=None)):
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        return _noc_json_response({"detail": exc.detail}, status_code=exc.status_code)
    try:
        return _noc_json_response(build_trace(_load_or_503()))
    except Exception:
        return _noc_json_response({"state": "UNKNOWN", "detail": "synthetic_noc_trace_unavailable"},
                                  status_code=503)
