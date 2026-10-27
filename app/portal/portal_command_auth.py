"""Fail-closed operator authorization for the legacy Golden DEMO write endpoint.

The portal must never silently reuse its internal service token as a browser
credential. This guard authorizes only a synthetic DEMO command, not LIVE.
"""
from __future__ import annotations

import hmac
import os

from fastapi import HTTPException

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff"}


def _valid_token(value: object) -> bool:
    return (isinstance(value, str) and 32 <= len(value) <= 256
            and value.isascii() and value.isprintable()
            and not any(character.isspace() for character in value))


def require_demo_operator(authorization: str | None, env=None) -> None:
    """Authorize a one-shot DEMO write with the scoped portal operator token.

    Deliberately fail with 503 if credentials are absent or ambiguous; an
    invalid/missing caller credential gets 401. Neither case calls Core.
    """
    env = os.environ if env is None else env
    operator = env.get("AIOPS_PORTAL_OPERATOR_TOKEN", "")
    viewer = env.get("AIOPS_PORTAL_READ_TOKEN", "")
    if not _valid_token(operator) or (viewer and operator == viewer):
        raise HTTPException(503, "portal_operator_not_configured",
                            headers=NO_STORE)
    scheme, separator, supplied = (authorization or "").partition(" ")
    if (scheme.lower() != "bearer" or not separator
            or not _valid_token(supplied)
            or not hmac.compare_digest(supplied, operator)):
        raise HTTPException(401, "invalid_portal_operator_token",
                            headers={**NO_STORE, "WWW-Authenticate": "Bearer"})
