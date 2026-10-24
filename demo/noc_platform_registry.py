"""Single-portal component registry; status cannot be inferred from configuration.

Backend services remain private. A configured component is UNKNOWN until
the existing portal supplies an authenticated, recent observation.
"""
from __future__ import annotations
from datetime import datetime, timezone

COMPONENTS=(
 ("noc","NOC & incidents","/noc","portal"),
 ("checkmk","Checkmk monitoring","/noc/checkmk","monitoring"),
 ("thruk","Thruk operations","/noc/thruk","monitoring"),
 ("grafana","Grafana observability","/observability/grafana","observability"),
 ("prometheus","Prometheus metrics","/observability/metrics","observability"),
 ("alertmanager","Alertmanager alerts","/observability/alerts","observability"),
 ("glpi","GLPI ITSM & CMDB","/itsm","integration"),
 ("n8n","n8n integration flows","/workflows","integration"),
 ("core","Core incident lifecycle","/incidents","engine"),
 ("temporal","Temporal orchestration","/runs","engine"),
 ("worker","Worker activities","/runs/activities","engine"),
 ("intelligence","DGX Analyst & Critic","/intelligence","engine"),
 ("policy","Policy / HITL gate","/decisions","engine"),
 ("evidence","Evidence Center","/evidence","engine"),
 ("rag","RAG knowledge & runbooks","/knowledge","engine"),
 ("digital-twin","Digital Twin","/topology","engine"),
 ("simulator","Controlled simulation","/demo","engine"),
 ("copilot","Operations Copilot","/copilot","engine"),
 ("mattermost","Mattermost notifications","/notifications","integration"),
 ("pagerduty","PagerDuty escalation (mock/optional)","/escalations","integration"),
)
CATEGORIES={"portal","monitoring","observability","integration","engine"}
STATES={"OK","WARN","CRIT","UNKNOWN"}

def build_portal_component_registry(observations:dict|None=None, *, now_utc:str|None=None, max_age_seconds:int=300)->dict:
    if observations is None:observations={}
    if not isinstance(observations,dict) or not isinstance(max_age_seconds,int) or not 1<=max_age_seconds<=3600:
        raise ValueError("invalid observations")
    ids={name for name,_,_,_ in COMPONENTS}
    if set(observations)-ids:raise ValueError("unexpected component identity")
    if now_utc is not None:
        if not isinstance(now_utc,str) or not now_utc.endswith("Z"):raise ValueError("invalid clock")
        now=datetime.fromisoformat(now_utc.replace("Z","+00:00"))
    else:now=datetime.now(timezone.utc)
    entries=[]
    for ident,label,path,category in COMPONENTS:
        row=observations.get(ident)
        state="UNKNOWN";timestamp=None
        if row is not None:
            if not isinstance(row,dict) or set(row)!={"state","observed_at","authenticated"} or row["state"] not in STATES or type(row["authenticated"]) is not bool:
                raise ValueError("invalid component observation")
            if row["authenticated"] is True:
                stamp=row["observed_at"]
                if not isinstance(stamp,str) or not stamp.endswith("Z"):raise ValueError("invalid observation timestamp")
                observed=datetime.fromisoformat(stamp.replace("Z","+00:00"))
                age=(now-observed).total_seconds()
                if 0<=age<=max_age_seconds:
                    state=row["state"];timestamp=stamp
        entries.append({"id":ident,"name":label,"path":path,"category":category,
                        "state":state,"observed_at":timestamp,
                        "available_in_portal":False,
                        "requires_route_integration":True})
    return {"schema":"aiops-single-portal-component-registry-v1",
            "entrypoint":"http://10.79.94.202:17777/",
            "items":entries,"live_remediation_authorized":False}
