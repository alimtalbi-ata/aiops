"""Read-only canonical Incident inventory from Core; no portal-side database access."""
from fastapi import APIRouter
from shared.db import db

router = APIRouter()

@router.get("/api/incidents")
def list_incidents():
    with db() as cursor:
        rows = cursor.execute(
            "select incident_id, external_id, title, severity, state, service_id, "
            "opened_at, source, synthetic from aiops.incidents "
            "order by opened_at desc limit 50"
        ).fetchall()
    keys = ("incident_id", "external_id", "title", "severity", "state",
            "service_id", "opened_at", "source", "synthetic")
    return {"items": [dict(zip(keys, row)) for row in rows]}
