"""Offline NOC drill-down: associate synthetic asset alerts, RAG cases, CMDB dependencies."""
from __future__ import annotations
from demo.noc_topology import build_noc_topology
from demo.validate_rag_ops_fixtures import validate_catalog

def build_noc_drilldown(snapshot:dict, catalog:dict)->dict:
    validate_catalog(catalog)
    topology=build_noc_topology(snapshot)
    alerts=snapshot["alerts"]
    indexed={row["doc_id"]:row for row in catalog["scenarios"]}
    if len(alerts)!=len(indexed) or {x["event_id"] for x in alerts}!=set(indexed):
        raise ValueError("NOC alerts and RAG catalog diverged")
    nodes={}
    for node in topology["nodes"]:
        asset=node["id"]
        related=[a for a in alerts if a["asset_id"]==asset]
        notes=[]
        for alert in related:
            doc=indexed[alert["event_id"]]
            if doc["asset"]!=asset or doc["service"]!=alert["service"] or doc["source_type"]!="SYNTHETIC":
                raise ValueError("inconsistent alert/RAG identity")
            notes.append({"doc_id":doc["doc_id"],"event_key":doc["event_key"],
                          "sample":doc["sample"],"runbook":doc["runbook"],
                          "provenance":"SYNTHETIC"})
        nodes[asset]={"role":node["role"],"state":node["state"],
                      "upstream":[e["from"] for e in topology["edges"] if e["to"]==asset],
                      "downstream":[e["to"] for e in topology["edges"] if e["from"]==asset],
                      "diagnostics":notes}
    return {"schema":"aiops-noc-synthetic-drilldown-v1","run_id":snapshot["run_id"],
            "assets":nodes,"source":"SYNTHETIC_SIMULATION_ONLY",
            "live_remediation_authorized":False,"cmdb_verified":False}
