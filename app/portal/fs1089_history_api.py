"""FS1089 read-only bounded Prometheus historical series API."""
import math
import time
from fastapi import HTTPException, Request

_FS1089_QUERIES = {"availability": "up", "scrape_duration": "scrape_duration_seconds"}
_FS1089_WINDOWS = {"1h": 3600, "6h": 21600, "24h": 86400}

@router.get("/api/fs1089/prometheus/history")
def fs1089_history(request: Request, metric: str = "availability", window: str = "1h"):
    _check(request)
    if metric not in _FS1089_QUERIES or window not in _FS1089_WINDOWS:
        raise HTTPException(400, "unsupported_metric_or_window")
    duration = _FS1089_WINDOWS[window]
    step = max(60, math.ceil(duration / 240))
    end = int(time.time())
    params = urllib.parse.urlencode({
        "query": _FS1089_QUERIES[metric], "start": end - duration,
        "end": end, "step": step,
    })
    payload = _fetch(_PROM + "/api/v1/query_range?" + params)
    if payload.get("status") != "success" or payload.get("data", {}).get("resultType") != "matrix":
        raise HTTPException(502, "prometheus_invalid_history")
    series = payload["data"].get("result")
    if not isinstance(series, list):
        raise HTTPException(502, "prometheus_invalid_shape")
    output = []
    for entry in series[:30]:
        if not isinstance(entry, dict):
            raise HTTPException(502, "prometheus_invalid_shape")
        labels = entry.get("metric", {})
        values = entry.get("values", [])
        if not isinstance(labels, dict) or not isinstance(values, list):
            raise HTTPException(502, "prometheus_invalid_shape")
        points = []
        for pair in values[:260]:
            if not isinstance(pair, list) or len(pair) != 2:
                continue
            try:
                stamp, val = float(pair[0]), float(pair[1])
            except (ValueError, TypeError):
                continue
            if math.isfinite(stamp) and math.isfinite(val):
                points.append([int(stamp), val])
        output.append({
            "job": str(labels.get("job", ""))[:120],
            "instance": str(labels.get("instance", ""))[:160],
            "points": points,
        })
    return {"metric": metric, "window": window, "step_seconds": step, "series": output}
