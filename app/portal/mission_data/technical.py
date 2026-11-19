"""Prometheus-generated technical metrics only; no tenant counters."""
import json
import math
import time
import urllib.parse
import urllib.request

METRICS = {"scrape-duration": ("scrape_duration_seconds", "seconds"),
           "scrape-samples": ("scrape_samples_scraped", "samples")}

def technical_series(jobs, origin, redirect_handler, metric, minutes):
    name, unit = METRICS[metric]
    end = int(time.time()) // 60 * 60
    start = end - minutes * 60
    # Maximum across replicas, not a sum of duplicate exporters.
    query = 'max by (job) (' + name + '{job=~"' + "|".join(jobs) + '"})'
    params = urllib.parse.urlencode(dict(query=query,start=start,end=end,step=60))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), redirect_handler())
    with opener.open(origin+"/api/v1/query_range?"+params,timeout=5) as response:
        raw = response.read(1048577)
    if len(raw)>1048576:
        raise ValueError("oversize")
    body=json.loads(raw)
    if body["status"]!="success" or body["data"]["resultType"]!="matrix" or body.get("warnings"):
        raise ValueError("invalid result")
    observed={}
    for row in body["data"]["result"]:
        job=row["metric"]["job"]
        if job not in jobs or job in observed:
            raise ValueError("unexpected series")
        points={}
        for stamp,value in row["values"]:
            stamp,value=float(stamp),float(value)
            if not math.isfinite(stamp) or not start<=stamp<=end or (stamp-start)%60 or stamp in points or not math.isfinite(value) or value<0:
                raise ValueError("invalid sample")
            points[stamp]=value
        observed[job]=points
    series=[]
    for job in jobs:
        points=observed.get(job,{})
        series.append({"job":job,"points":[{"at":t,"value":points.get(t)} for t in range(start,end+1,60)],
                       "coverage":len(points)/(minutes+1),"last_evaluated_at":max(points,default=None)})
    return {"metric":metric,"prometheus_metric":name,"unit":unit,"series":series,"start":start,"end":end,
            "step_seconds":60,"classification":"PLATFORM_TECHNICAL_ONLY",
            "freshness":"QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME","aggregation":"MAX_BY_JOB"}
