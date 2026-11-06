"""FS.1051: read-only Prometheus/Twin visualization extension for the existing portal."""
import json
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from portal.explorer_api import _check

router = APIRouter()
_PROM = "http://aiops2-rebuild-prometheus:9090"
_TWIN = "http://aiops2-rebuild-twin:811"
_MAX_BYTES = 2_000_000


def _fetch(url):
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET"),
            timeout=6,
        ) as response:
            if response.status != 200:
                raise HTTPException(502, "upstream_http_error")
            payload = response.read(_MAX_BYTES + 1)
            if len(payload) > _MAX_BYTES:
                raise HTTPException(502, "upstream_response_too_large")
            return json.loads(payload)
    except HTTPException:
        raise
    except (OSError, ValueError, UnicodeError) as exc:
        raise HTTPException(502, "upstream_unavailable") from exc


@router.get("/api/fs1051/prometheus")
def prometheus(request: Request):
    _check(request)
    targets = _fetch(_PROM + "/api/v1/targets?state=active")
    query = _fetch(_PROM + "/api/v1/query?query=up")
    if targets.get("status") != "success" or query.get("status") != "success":
        raise HTTPException(502, "prometheus_invalid_response")
    active = targets.get("data", {}).get("activeTargets", [])
    vector = query.get("data", {}).get("result", [])
    if not isinstance(active, list) or not isinstance(vector, list):
        raise HTTPException(502, "prometheus_invalid_shape")
    return {
        "targets": [
            {
                "job": str(t.get("labels", {}).get("job", ""))[:120],
                "instance": str(t.get("labels", {}).get("instance", ""))[:160],
                "health": str(t.get("health", "unknown"))[:24],
            }
            for t in active[:300]
        ],
        "up": sum(str(x.get("value", ["", ""])[1]) == "1" for x in vector),
        "down": sum(str(x.get("value", ["", ""])[1]) == "0" for x in vector),
        "total": len(vector),
    }


@router.get("/api/fs1051/twin")
def twin(request: Request):
    _check(request)
    graph = _fetch(_TWIN + "/api/twin/graph")
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise HTTPException(502, "twin_invalid_shape")
    return {"nodes": nodes[:1000], "edges": edges[:2000], "total_nodes": len(nodes), "total_edges": len(edges)}


@router.get("/explorer/visual", response_class=HTMLResponse)
def visual(request: Request):
    _check(request)
    from pathlib import Path
    return HTMLResponse(Path(__file__).with_name("fs1051_visual.html").read_text(encoding="utf-8"))
