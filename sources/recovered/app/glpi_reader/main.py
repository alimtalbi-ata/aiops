"""Internal-only, read-only GLPI ticket observation gateway.

This service must not be published on a host port or exposed by the Portal.
A machine token gates all ticket reads; no end-user RBAC is asserted.
"""
from __future__ import annotations

import hmac
import os
import re

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from shared.glpi_ticket_read import GLPIUnverified, read_ticket

app = FastAPI(title="AIOps GLPI internal read gateway", version="1.0")
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9._~+/-]{32,512}\Z")


def _authorize(value: str | None, *, env=None) -> None:
    """Fail before any GLPI I/O if the caller or configured token is invalid."""
    env = os.environ if env is None else env
    expected = env.get("AIOPS_GLPI_READER_TOKEN", "")
    if not isinstance(expected, str) or TOKEN_PATTERN.fullmatch(expected) is None:
        raise HTTPException(status_code=503, detail="reader_not_configured")
    if not isinstance(value, str) or not value.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    supplied = value[7:]
    if TOKEN_PATTERN.fullmatch(supplied) is None or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
def health():
    return {"component": "glpi-reader", "state": "NOT_ATTESTED"}


@app.get("/internal/glpi/tickets/{ticket_id}")
def observe_ticket(ticket_id: str, mode: str = "DEMO",
                   authorization: str | None = Header(default=None)):
    _authorize(authorization)
    if mode not in ("DEMO", "SIMULATION"):
        return JSONResponse(
            {"state": "UNKNOWN", "reason": "mode_not_qualified",
             "ticket_id": None, "runtime_attested": False},
            status_code=403, headers=HEADERS,
        )
    try:
        observed = read_ticket(ticket_id, mode=mode)
    except GLPIUnverified:
        return JSONResponse(
            {"state": "UNKNOWN", "reason": "glpi_unavailable_or_unverified",
             "ticket_id": None, "runtime_attested": False},
            status_code=503, headers=HEADERS,
        )
    return JSONResponse(observed, headers=HEADERS)
