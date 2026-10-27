"""Offline adapter for reviewed Checkmk Livestatus GET-shaped table exports.

Input is already-exported JSON, never a socket/API connection. Converts Checkmk
host rows into the strict freshness-aware import contract.
"""
from __future__ import annotations
from demo.noc_checkmk_export import parse_host_status_export

def normalize_livestatus_hosts(records: list, *, captured_at: str, now_utc: str) -> dict:
    if not isinstance(records,list) or not 1 <= len(records) <= 500:
        raise ValueError("invalid monitoring rows")
    hosts=[]
    for row in records:
        if not isinstance(row,dict) or set(row)!={"name","state","plugin_output"}:
            raise ValueError("unexpected Livestatus columns")
        if type(row["state"]) is not int or row["state"] not in (0,1,2,3):
            raise ValueError("unrecognized monitoring state")
        hosts.append({"name":row["name"],"state":row["state"],"output":row["plugin_output"]})
    payload={"schema":"aiops-checkmk-host-export-v1",
             "source":"CHECKMK_EXPORT","read_only":True,
             "live_remediation_authorized":False,"captured_at":captured_at,"hosts":hosts}
    result=parse_host_status_export(payload,now_utc=now_utc)
    result["transport"]="OFFLINE_LIVESTATUS_EXPORT"
    return result
