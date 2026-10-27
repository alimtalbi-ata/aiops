"""Parse exported Checkmk/Thruk host states, offline, never fetch APIs.

Requires a timestamped operator-approved export; no evidence of present runtime.
"""
from __future__ import annotations
from datetime import datetime, timezone

STATE={"0":"OK","1":"WARN","2":"CRIT","3":"UNKNOWN"}
def parse_host_status_export(payload:dict, *, now_utc:str, max_age_seconds:int=300)->dict:
    if not isinstance(payload,dict) or payload.get("schema")!="aiops-checkmk-host-export-v1" or payload.get("source")!="CHECKMK_EXPORT":
        raise ValueError("untrusted Checkmk export")
    if payload.get("read_only") is not True or payload.get("live_remediation_authorized") is not False:
        raise ValueError("unsafe monitoring export")
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=3600:
        raise ValueError("invalid freshness bound")
    def parse_stamp(value):
        if not isinstance(value,str) or not value.endswith("Z"):
            raise ValueError("timestamp must be UTC Z")
        return datetime.fromisoformat(value.replace("Z","+00:00"))
    captured=parse_stamp(payload.get("captured_at"))
    now=parse_stamp(now_utc)
    elapsed=(now-captured).total_seconds()
    if elapsed<0 or elapsed>max_age_seconds:
        raise ValueError("monitoring export stale or from the future")
    rows=payload.get("hosts")
    if not isinstance(rows,list) or not 1<=len(rows)<=500:
        raise ValueError("invalid host export")
    seen=set();hosts={}
    for row in rows:
        if not isinstance(row,dict) or set(row)!={"name","state","output"}:
            raise ValueError("invalid host record")
        name,state,output=row["name"],row["state"],row["output"]
        if (not isinstance(name,str) or not 1<=len(name)<=96 or not all(c.isalnum() or c in "._-" for c in name)
                or name in seen or str(state) not in STATE or type(state) is bool
                or not isinstance(output,str) or len(output)>1000):
            raise ValueError("untrusted host state")
        seen.add(name)
        hosts[name]={"state":STATE[str(state)],"output":output}
    return {"schema":"aiops-checkmk-offline-readonly-v1","captured_at":payload["captured_at"],
            "age_seconds":elapsed,"host_count":len(hosts),"hosts":hosts,
            "provenance":"OPERATOR_EXPORT_UNVERIFIED","runtime_authenticated":False,
            "live_remediation_authorized":False}
