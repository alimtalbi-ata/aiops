"""Build deterministic NOC service state from validated synthetic RAG events.

An offline integration fixture, not a live Checkmk/Thruk adapter.
"""
from __future__ import annotations
import json
from pathlib import Path
from demo.validate_rag_ops_fixtures import validate_catalog

SEVERITY_BY_EVENT = {
 "DEMO_FC_PORT_CRC_SPIKE": "CRIT",
 "DEMO_VSAN_ISL_DOWN": "CRIT",
 "DEMO_SRDF_REPLICATION_LAG": "WARN",
 "DEMO_ARRAY_LATENCY_P95": "WARN",
 "DEMO_ESXI_APD": "CRIT",
 "DEMO_DM_MULTIPATH_PATH_FAIL": "WARN",
}
ORDER = {"OK":0,"WARN":1,"UNKNOWN":2,"CRIT":3}
def build_noc_snapshot(catalog:dict, run_id:str="RUN-SYNTHETIC-NOC") -> dict:
    validate_catalog(catalog)
    if not isinstance(run_id,str) or not run_id.startswith("RUN-") or len(run_id)>96 or not all(x.isalnum() or x in "-_." for x in run_id):
        raise ValueError("invalid synthetic run ID")
    hosts={}
    services={}
    alerts=[]
    for item in catalog["scenarios"]:
        key=item["event_key"]
        if key not in SEVERITY_BY_EVENT:
            raise ValueError("unreviewed synthetic event")
        state=SEVERITY_BY_EVENT[key]
        host=item["asset"]
        service=item["service"]
        entry={"event_id":item["doc_id"],"asset_id":host,"service":service,
               "state":state,"signal":item["signal_type"],"runbook_doc_id":item["doc_id"],
               "provenance":"SYNTHETIC"}
        alerts.append(entry)
        previous=hosts.get(host,{"state":"OK","alerts":0})
        hosts[host]={"state":state if ORDER[state]>ORDER[previous["state"]] else previous["state"],
                     "alerts":previous["alerts"]+1}
        prior=services.get(service,{"state":"OK","alerts":0})
        services[service]={"state":state if ORDER[state]>ORDER[prior["state"]] else prior["state"],
                           "alerts":prior["alerts"]+1}
    return {"schema":"aiops-noc-synthetic-snapshot-v1","run_id":run_id,
            "provenance":"SYNTHETIC_SIMULATION_ONLY","runtime_authenticated":False,
            "checkmk_live":False,"thruk_live":False,"live_remediation_authorized":False,
            "hosts":hosts,"business_services":services,"alerts":alerts,
            "totals":{"hosts":len(hosts),"services":len(services),"alerts":len(alerts)}}

if __name__=="__main__":
    catalog=json.loads((Path(__file__).parent/"rag_ops_fixture_catalog.json").read_text(encoding="utf-8"))
    print(json.dumps(build_noc_snapshot(catalog),indent=2))
