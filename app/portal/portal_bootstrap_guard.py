"""Fail-closed browser read gate, adapted narrowly from PR #36 bootstrap contract.

This protects Core/Twin data but does not assert SSO or tenant isolation.
"""
from __future__ import annotations

import hmac
import os

from fastapi.responses import JSONResponse


def _denied(detail: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"detail": detail}, status_code=status,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


def require_portal_bootstrap_read(authorization: str | None) -> JSONResponse | None:
    """Return an HTTP denial or None; never contact Core/Twin on denial."""
    expected = os.getenv("AIOPS_PORTAL_READ_TOKEN", "")
    if not expected:
        return _denied("portal_read_auth_not_configured", 503)
    scheme, sep, supplied = (authorization or "").partition(" ")
    if (not sep or scheme.lower() != "bearer" or not supplied
            or supplied.strip() != supplied or " " in supplied
            or not hmac.compare_digest(supplied, expected)):
        return _denied("invalid_portal_read_token", 401)
    return None
