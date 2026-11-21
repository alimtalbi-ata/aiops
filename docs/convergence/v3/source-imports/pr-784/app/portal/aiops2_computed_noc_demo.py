"""Isolated computed SAN -> Payments demo route, not a live integration."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from aiops2_noc_decision import build_noc_decision
from aiops2_noc_decision_html import render_computed_noc_html

router = APIRouter()
_NOW = "2026-11-15T12:00:00Z"


def _synthetic_projection() -> dict:
    events = [
        {"tenant_id": "acme-synthetic", "source": "checkmk",
         "source_event_id": "san-p1", "ci_id": "san-01", "service_id": "payments",
         "severity": "P1", "evidence_sha256": "a" * 64,
         "observed_at": "2026-11-15T11:59:00Z", "known_at": "2026-11-15T11:59:05Z"},
        {"tenant_id": "acme-synthetic", "source": "prometheus",
         "source_event_id": "payments-p2", "ci_id": "payments-api", "service_id": "payments",
         "severity": "P2", "evidence_sha256": "b" * 64,
         "observed_at": "2026-11-15T11:59:10Z", "known_at": "2026-11-15T11:59:15Z"},
    ]
    edges = [
        {"tenant_id": "acme-synthetic", "from_id": "san-01", "to_id": "storage",
         "source_id": "synthetic-cmdb", "evidence_sha256": "c" * 64,
         "observed_at": "2026-11-15T11:59:00Z"},
        {"tenant_id": "acme-synthetic", "from_id": "storage", "to_id": "payments",
         "source_id": "synthetic-cmdb", "evidence_sha256": "d" * 64,
         "observed_at": "2026-11-15T11:59:00Z"},
    ]
    return build_noc_decision(events, edges, as_of=_NOW)


_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"}


@router.get("/demo/aiops2-computed-noc", response_class=HTMLResponse)
def computed_noc_demo():
    return HTMLResponse(render_computed_noc_html(_synthetic_projection()), headers=_HEADERS)


@router.get("/demo/api/aiops2-computed-noc", response_class=JSONResponse)
def computed_noc_demo_json():
    return JSONResponse(_synthetic_projection(), headers=_HEADERS)
