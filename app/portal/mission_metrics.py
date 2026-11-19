"""Minimal Portal scrape contract. No tenant or request identifiers."""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()

@router.get("/metrics", include_in_schema=False)
def portal_metrics():
    return PlainTextResponse(
        "# HELP aiops_portal_up Portal metrics handler reachable.\n"
        "# TYPE aiops_portal_up gauge\n"
        "aiops_portal_up 1\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Cache-Control":"no-store"},
    )
