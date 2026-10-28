"""Operator-only DEMO boundary; targeted port from PR #57, no LIVE grant."""
from __future__ import annotations
import hmac
import os
import re
from fastapi import HTTPException

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}

def _valid_token(value):
    return (isinstance(value, str) and 32 <= len(value) <= 256
            and value.isascii() and value.isprintable()
            and not any(char.isspace() for char in value))

def require_demo_operator(authorization: str | None, env=None) -> None:
    env = os.environ if env is None else env
    operator = env.get("AIOPS_PORTAL_OPERATOR_TOKEN", "")
    viewer = env.get("AIOPS_PORTAL_READ_TOKEN", "")
    internal = env.get("AIOPS_INTERNAL_TOKEN", "")
    if (not _valid_token(operator) or
            (viewer and (not _valid_token(viewer) or operator == viewer)) or
            (internal and operator == internal)):
        raise HTTPException(503, "portal_operator_not_configured", headers=NO_STORE)
    scheme, sep, supplied = (authorization or "").partition(" ")
    if (scheme.lower() != "bearer" or not sep or not _valid_token(supplied)
            or not hmac.compare_digest(supplied, operator)):
        raise HTTPException(401, "invalid_portal_operator_token",
                            headers={**NO_STORE, "WWW-Authenticate": "Bearer"})

IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,127}$")
def require_core_identifier(value, prefix):
    if not isinstance(value, str) or not value.startswith(prefix) or not IDENT.fullmatch(value):
        raise ValueError("invalid Core identifier")
    return value
