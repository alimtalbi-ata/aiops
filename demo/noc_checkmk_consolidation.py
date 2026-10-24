"""Consolidate *unverified* offline Checkmk host and service exports.

No live monitoring claim, no mutation, and no fallback to synthetic states.
"""
from __future__ import annotations

STATES={"OK","WARN","CRIT","UNKNOWN"}
RANK={"OK":0,"WARN":1,"UNKNOWN":2,"CRIT":3}

def consolidate_checkmk_snapshot(host_export:dict, service_export:dict)->dict:
    if not isinstance(host_export,dict) or not isinstance(service_export,dict):
        raise ValueError("invalid exports")
    if host_export.get("schema")!="aiops-checkmk-offline-readonly-v1" or service_export.get("schema")!="aiops-checkmk-services-loopback-v1":
        raise ValueError("invalid Checkmk export schemas")
    if host_export.get("provenance")!="OPERATOR_EXPORT_UNVERIFIED" or service_export.get("provenance")!="LOOPBACK_UNVERIFIED":
        raise ValueError("untrusted provenance")
    if any(obj.get("runtime_authenticated") is not False or obj.get("live_remediation_authorized") is not False for obj in (host_export,service_export)):
        raise ValueError("untrusted runtime attestation")
    if host_export.get("captured_at")!=service_export.get("captured_at") or host_export.get("age_seconds")!=service_export.get("age_seconds"):
        raise ValueError("unmatched acquisition window")
    hosts=host_export.get("hosts")
    services=service_export.get("services")
    if not isinstance(hosts,dict) or not isinstance(services,list) or not hosts or not services or len(hosts)>500 or len(services)>500:
        raise ValueError("invalid monitoring objects")
    combined={}
    for name,record in hosts.items():
        if not isinstance(name,str) or not isinstance(record,dict) or record.get("state") not in STATES:
            raise ValueError("invalid host state")
        combined[name]={"host_state":record["state"],"overall_state":record["state"],"services":[]}
    seen=set()
    for row in services:
        if not isinstance(row,dict) or row.get("host") not in combined or row.get("state") not in STATES or not isinstance(row.get("description"),str):
            raise ValueError("service without matching host")
        key=(row["host"],row["description"])
        if key in seen:raise ValueError("duplicate monitored service")
        seen.add(key)
        entry={"name":row["description"],"state":row["state"],"output":row.get("output","")}
        target=combined[row["host"]]
        target["services"].append(entry)
        if RANK[row["state"]]>RANK[target["overall_state"]]:
            target["overall_state"]=row["state"]
    return {"schema":"aiops-noc-checkmk-merged-offline-v1",
            "captured_at":host_export["captured_at"],"age_seconds":host_export["age_seconds"],
            "hosts":combined,"host_count":len(combined),"service_count":len(seen),
            "provenance":"UNVERIFIED_OFFLINE_EXPORTS",
            "runtime_authenticated":False,"live_remediation_authorized":False}
