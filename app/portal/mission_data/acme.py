"""Explicit DEMO only; never a fallback for LIVE or a Core tenant read."""
from portal.acme_impact_read_model import _load_or_503

def project_acme():
    m = _load_or_503()
    t = m["twin_evidence"]
    if (m["provenance"] != "SIMULATED_TARGET" or t["scope"] != "STORY_OFFLINE"
            or t["binding_status"] != "UNBOUND" or t["tenant_id"] is not None
            or m["runtime_attested"] is not False or m["live_remediation_authorized"] is not False):
        raise ValueError("unqualified simulation")
    return {
        "classification": "SYNTHETIC_SIMULATION_ONLY",
        "source_sha256": m["source_sha256"], "source_artifact": m["source_artifact"],
        "observed_at": None, "freshness": "UNKNOWN", "runtime_attested": False,
        "live_remediation_authorized": False,
        "kpis": {"ci_count": m["ci_count"], "incident_count": m["incident_count"],
                 "affected_ci_count": len(m["affected_ci_ids"]), "runtime_open_incidents": None},
        "graph": {"nodes": [{"node_id": n["node_id"], "type": n["kind"], "name": n["name"],
                             "state": "UNKNOWN", "health": None, "provenance": n["provenance"]}
                            for n in t["nodes"]],
                  "edges": [{"source_id": e["source_id"], "target_id": e["target_id"],
                             "relation_type": e["relation_type"], "provenance": e["provenance"]}
                            for e in t["edges"]]},
        "impact": {"path": m["impact_path"], "affected_ci_ids": m["affected_ci_ids"],
                   "operational_impact": "UNKNOWN"},
        "incidents": [{"incident_id": m["incident_id"], "severity": "P1", "role": m["incident_role"]},
                      {"incident_id": m["impact_incident_id"], "severity": "P2", "role": m["impact_role"]}],
        "history": [{"sequence": i, "cue": e["cue"], "service": e["service"],
                     "status": "MISSING", "observed_at": None}
                    for i, e in enumerate(m["checkpoint_evidence"])],
    }
