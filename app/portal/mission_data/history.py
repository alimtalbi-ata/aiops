"""Technical-only history; grid timestamps are evaluation times, not scrape times."""
import json
import math
import time
import urllib.parse
import urllib.request

def history(jobs, origin, redirect_handler, minutes):
    end = int(time.time()) // 60 * 60
    start = end - minutes * 60
    query = 'min by (job) (up{job=~"' + "|".join(jobs) + '"})'
    params = urllib.parse.urlencode(dict(query=query, start=start, end=end, step=60))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), redirect_handler())
    with opener.open(origin + "/api/v1/query_range?" + params, timeout=5) as response:
        raw = response.read(1048577)
    if len(raw) > 1048576:
        raise ValueError("oversize")
    body = json.loads(raw)
    if body["status"] != "success" or body["data"]["resultType"] != "matrix" or body.get("warnings"):
        raise ValueError("invalid result")
    observed = {}
    for row in body["data"]["result"]:
        job = row["metric"]["job"]
        if job not in jobs or job in observed:
            raise ValueError("unexpected series")
        samples = {}
        for stamp, value in row["values"]:
            stamp, value = float(stamp), float(value)
            if not math.isfinite(stamp) or not start <= stamp <= end or (stamp-start)%60 or stamp in samples or value not in (0,1):
                raise ValueError("invalid sample")
            samples[stamp] = int(value)
        observed[job] = samples
    series = []
    expected = minutes + 1
    for job in jobs:
        samples = observed.get(job, {})
        series.append({"job": job, "points": [{"at": t, "up": samples.get(t)} for t in range(start,end+1,60)],
                       "observed": len(samples), "expected": expected,
                       "coverage": len(samples)/expected, "last_evaluated_at": max(samples, default=None)})
    return {"series": series, "start": start, "end": end, "step_seconds": 60,
            "classification": "PLATFORM_TECHNICAL_ONLY",
            "freshness": "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME",
            "coverage": sum(s["observed"] for s in series)/(len(jobs)*expected)}
