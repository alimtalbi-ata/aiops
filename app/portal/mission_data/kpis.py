"""Fixed aggregate reads; authorization must be qualified by deployment owner."""
import json
import math
import os
import time
import urllib.parse
import urllib.request

CATALOG = {
    "core": ("aiops_runs_total","aiops_runs_running","aiops_runs_blocked","aiops_runs_resolved"),
    "evidence": ("aiops_evidence_total",),
    "twin": ("aiops_twin_nodes","aiops_twin_degraded","aiops_twin_failed"),
    "fs-lab": ("aiops2_fs_lab_used_percent","aiops2_fs_lab_alert_firing"),
    "services": ("aiops_worker_up","aiops_policy_up","aiops_portal_up"),
}

def authorized(group):
    # Default deny. Deployment owner must explicitly qualify each aggregate group.
    # This is a platform-wide aggregate grant, not tenant ACL qualification.
    return group in os.getenv("AIOPS_MISSION_AGGREGATE_GROUPS","").split(",")

def read_kpis(group, origin, redirect_handler, minutes):
    names = CATALOG[group]
    end = int(time.time()) // 60 * 60
    start = end - minutes*60
    # No sum/max across unknown partitions: require one source series per metric.
    query = '{__name__=~"' + "|".join(names) + '"}'
    params = urllib.parse.urlencode(dict(query=query,start=start,end=end,step=60))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),redirect_handler())
    with opener.open(origin+"/api/v1/query_range?"+params,timeout=5) as response:
        raw=response.read(1048577)
    if len(raw)>1048576:
        raise ValueError("oversize")
    body=json.loads(raw)
    if body["status"]!="success" or body["data"]["resultType"]!="matrix" or body.get("warnings"):
        raise ValueError("invalid response")
    observed={}
    ambiguous=set()
    for row in body["data"]["result"]:
        name=row["metric"]["__name__"]
        if name not in names:
            raise ValueError("unexpected metric")
        if name in observed:
            ambiguous.add(name)
            continue
        points={}
        for stamp,value in row["values"]:
            stamp,value=float(stamp),float(value)
            if not math.isfinite(stamp) or not start<=stamp<=end or (stamp-start)%60 or stamp in points or not math.isfinite(value) or value<0:
                raise ValueError("invalid sample")
            if name.endswith("_up") or name.endswith("_alert_firing"):
                if value not in (0,1): raise ValueError("invalid binary")
            elif name.endswith("_percent"):
                if value>100: raise ValueError("invalid percent")
            elif not value.is_integer():
                raise ValueError("invalid count")
            points[stamp]=value
        observed[name]=points
    series=[]
    for name in names:
        points={} if name in ambiguous else observed.get(name,{})
        series.append({"metric":name,"unit":"percent" if name.endswith("_percent") else "binary" if name.endswith(("_up","_alert_firing")) else "count",
                       "value":points.get(end),"points":[{"at":t,"value":points.get(t)} for t in range(start,end+1,60)],
                       "coverage":len(points)/(minutes+1),"last_evaluated_at":max(points,default=None),
                       "reason":"AMBIGUOUS_SERIES" if name in ambiguous else None if end in points else "NO_CURRENT_SAMPLE"})
    return {"group":group,"series":series,"start":start,"end":end,"step_seconds":60,
            "classification":"PLATFORM_AGGREGATES_UNPARTITIONED","freshness":"QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME",
            "coverage":sum(s["coverage"] for s in series)/len(series)}
