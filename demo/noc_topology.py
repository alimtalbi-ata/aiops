"""Synthetic dependency map linked to the existing NOC snapshot.

Links are illustrative, not discovered CMDB topology.
"""
from __future__ import annotations

ASSET_ROLES={
    "brocade-fc01":"FC Fabric A",
    "mds-fc02":"FC Fabric B",
    "powermax-01":"Storage replication",
    "flasharray-01":"Primary storage",
    "esx-acme-01":"Compute / VMware",
    "pay-api-01":"Application host",
}
DEPENDENCIES=(
    ("brocade-fc01","flasharray-01"),
    ("mds-fc02","powermax-01"),
    ("flasharray-01","esx-acme-01"),
    ("powermax-01","esx-acme-01"),
    ("esx-acme-01","pay-api-01"),
    ("pay-api-01","ACME Payments"),
)
def build_noc_topology(snapshot:dict)->dict:
    if not isinstance(snapshot,dict) or snapshot.get("schema")!="aiops-noc-synthetic-snapshot-v1" or snapshot.get("provenance")!="SYNTHETIC_SIMULATION_ONLY":
        raise ValueError("untrusted NOC snapshot")
    if any(snapshot.get(k) is not False for k in ("checkmk_live","thruk_live","runtime_authenticated","live_remediation_authorized")):
        raise ValueError("live attestations not permitted")
    hosts=snapshot.get("hosts")
    services=snapshot.get("business_services")
    if not isinstance(hosts,dict) or not isinstance(services,dict):
        raise ValueError("missing CMDB simulation")
    if set(hosts)!=set(ASSET_ROLES) or set(services)!={"ACME Payments"}:
        raise ValueError("unreviewed dependency dataset")
    nodes=[{"id":a,"role":role,"state":hosts[a]["state"],"kind":"HOST"} for a,role in ASSET_ROLES.items()]
    nodes.append({"id":"ACME Payments","role":"Business service","state":services["ACME Payments"]["state"],"kind":"BUSINESS_SERVICE"})
    return {"schema":"aiops-noc-synthetic-topology-v1","run_id":snapshot["run_id"],
            "provenance":"SYNTHETIC_DEPENDENCIES_ONLY","nodes":nodes,
            "edges":[{"from":a,"to":b} for a,b in DEPENDENCIES],
            "live_discovery":False,"cmdb_verified":False,"live_remediation_authorized":False}
