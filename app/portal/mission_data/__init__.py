"""Read-only Mission Control technical projection; no tenant data."""
import json
import math
import time
import urllib.parse
import urllib.request
from typing import Literal

from fastapi import APIRouter, Header, Query
from portal.noc_runtime import _require_portal_read_auth, _noc_json_response
from fastapi import HTTPException

router = APIRouter(prefix="/api/mission-data", tags=["mission-data"])
JOBS = ("aiops2-core", "aiops2-worker", "aiops2-twin", "aiops2-policy", "aiops2-evidence", "aiops2-portal")
PROM = "http://aiops2-rebuild-prometheus:9090"
Mode = Literal["LIVE", "DEMO"]
HealthMode = Literal["PLATFORM", "LIVE", "DEMO"]
Dataset = Literal["incidents", "core", "fs-lab", "evidence", "logs", "traces", "twin", "impact", "noc"]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def query_prom(job, minutes):
    expr = 'min(up{job="' + job + '"})'
    now = int(time.time())
    params = {"query": expr}
    path = "/api/v1/query"
    if minutes:
        path += "_range"
        params.update(start=now-minutes*60, end=now, step=60)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(PROM + path + "?" + urllib.parse.urlencode(params), timeout=3) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError("oversize")
    body = json.loads(raw)
    data = body["data"]
    if body["status"] != "success" or data["resultType"] != ("matrix" if minutes else "vector"):
        raise ValueError("invalid result")
    rows = data["result"]
    if not rows:
        return []
    if len(rows) != 1:
        raise ValueError("unexpected series")
    pairs = rows[0]["values"] if minutes else [rows[0]["value"]]
    points = []
    for stamp, value in pairs:
        stamp, value = float(stamp), float(value)
        if not math.isfinite(stamp) or stamp > now + 5 or value not in (0, 1):
            raise ValueError("invalid sample")
        points.append({"at": stamp, "up": int(value)})
    return points

def envelope(mode, source, reason, data=None):
    return {"mode": mode, "source": source, "state": "AVAILABLE" if reason is None else "UNKNOWN",
            "reason": reason, "retrieved_at": int(time.time()), "data": data,
            "tenant_acl_qualified": False}

def auth_error(authorization):
    try:
        _require_portal_read_auth(authorization)
    except HTTPException as exc:
        return _noc_json_response({"detail": exc.detail}, status_code=exc.status_code)
    return None

@router.get("/health")
def health(job: Literal["aiops2-core", "aiops2-worker", "aiops2-twin", "aiops2-policy", "aiops2-evidence", "aiops2-portal"],
           mode: HealthMode, minutes: int = Query(0, ge=0, le=1440),
           authorization: str | None = Header(default=None)):
    denied = auth_error(authorization)
    if denied is not None:
        return denied
    # This is platform scrape health, not a claim of business health or LIVE remediation.
    # The configured Prometheus has no verified DEMO/LIVE partition.
    if mode != "PLATFORM":
        return _noc_json_response(envelope(mode, "prometheus", "MODE_NOT_QUALIFIED"), status_code=503)
    try:
        points = query_prom(job, minutes)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, AttributeError, IndexError):
        return _noc_json_response(envelope(mode, "prometheus", "UPSTREAM_UNAVAILABLE"), status_code=503)
    if not points:
        return _noc_json_response(envelope(mode, "prometheus", "NO_SAMPLES"), status_code=503)
    return _noc_json_response(envelope(mode, "prometheus", None, {
        "job": job, "points": points, "classification": "PLATFORM_TECHNICAL_ONLY",
        "freshness": "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME"}))

@router.get("/datasets/{dataset}")
def dataset(dataset: Dataset, mode: Mode, authorization: str | None = Header(default=None)):
    denied = auth_error(authorization)
    if denied is not None:
        return denied
    # Shared viewer authentication cannot authorize tenant records or raw telemetry.
    return _noc_json_response(envelope(mode, dataset, "TENANT_ACL_NOT_QUALIFIED"), status_code=503)

@router.get("/health/jobs")
def health_jobs(authorization: str | None = Header(default=None)):
    denied = auth_error(authorization)
    if denied is not None:
        return denied
    # Fixed query only. Do not expose arbitrary target labels or scrape URLs.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        query = 'min by (job) (up{job=~"aiops2-core|aiops2-worker|aiops2-twin|aiops2-policy|aiops2-evidence|aiops2-portal"})'
        with opener.open(PROM + "/api/v1/query?" + urllib.parse.urlencode({"query": query}), timeout=3) as response:
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("oversize")
        body = json.loads(raw)
        if body["status"] != "success" or body["data"]["resultType"] != "vector":
            raise ValueError("invalid result")
        observed = {}
        for row in body["data"]["result"]:
            job = row["metric"]["job"]
            stamp, value = map(float, row["value"])
            if job not in JOBS or job in observed or not math.isfinite(stamp) or stamp > time.time()+5 or value not in (0,1):
                raise ValueError("invalid sample")
            observed[job] = {"job": job, "status": "UP" if value == 1 else "DOWN", "at": stamp, "reason": None}
    except (OSError, ValueError, KeyError, TypeError, OverflowError, AttributeError, IndexError):
        return _noc_json_response(envelope("PLATFORM", "prometheus", "UPSTREAM_UNAVAILABLE"), status_code=503)
    items = [observed.get(job, {"job": job, "status": "UNKNOWN", "at": None, "reason": "NO_SAMPLES"}) for job in JOBS]
    return _noc_json_response(envelope("PLATFORM", "prometheus", None, {
        "items": items, "classification": "PLATFORM_TECHNICAL_ONLY",
        "freshness": "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME",
        "counts": {status: sum(item["status"] == status for item in items) for status in ("UP","DOWN","UNKNOWN")}
    }))

@router.get("/acme")
def acme(mode: Mode, authorization: str | None = Header(default=None)):
    denied = auth_error(authorization)
    if denied is not None:
        return denied
    if mode != "DEMO":
        return _noc_json_response(envelope(mode, "acme", "TENANT_ACL_NOT_QUALIFIED"), status_code=503)
    from portal.mission_data.acme import project_acme
    try:
        data = project_acme()
    except (HTTPException, OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return _noc_json_response(envelope(mode, "acme", "SYNTHETIC_SOURCE_UNAVAILABLE"), status_code=503)
    return _noc_json_response(envelope(mode, "acme", None, data))

@router.get("/health/history")
def health_history(minutes: int = Query(60, ge=1, le=1440),
                   authorization: str | None = Header(default=None)):
    denied = auth_error(authorization)
    if denied is not None:
        return denied
    from portal.mission_data.history import history
    try:
        data = history(JOBS, PROM, NoRedirect, minutes)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, AttributeError, IndexError):
        return _noc_json_response(envelope("PLATFORM", "prometheus", "UPSTREAM_UNAVAILABLE"), status_code=503)
    return _noc_json_response(envelope("PLATFORM", "prometheus", None, data))

@router.get("/metrics", include_in_schema=False)
def portal_metrics():
    # Same public liveness classification as the existing /health endpoint.
    # No tenant information, counters, secrets or dependency claims.
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("# TYPE aiops_portal_up gauge\naiops_portal_up 1\n",
                             media_type="text/plain; version=0.0.4",
                             headers={"Cache-Control": "no-store"})
