"""Development-only identity simulator routes.

The simulator issues short-lived signed fixture assertions. It does not
authenticate real users and must never be used for LIVE approvals.
"""
import os
import hmac

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from shared.hitl_identity import (
    IdentityError,
    issue_simulated_assertion,
    simulator_catalog,
    simulator_enabled,
    simulator_ready,
    oidc_configured,
)

router = APIRouter(tags=["HITL identity simulator"])


def _require_internal(authorization: str | None) -> None:
    expected = os.getenv("AIOPS_INTERNAL_TOKEN", "")
    supplied = (authorization or "").removeprefix("Bearer ")
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "invalid_internal_token")


class SimulatorTokenRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=100)
    ttl_seconds: int = Field(default=300, ge=30, le=600)


@router.get("/api/hitl/identity/health")
def identity_health():
    mode = os.getenv("AIOPS_HITL_IDENTITY_MODE", "DISABLED").upper()
    enabled = simulator_enabled()
    oidc_ready = oidc_configured()
    if not enabled and oidc_ready:
        mode = "OIDC"
    return {
        "component": "hitl-identity",
        "mode": mode,
        "simulator_enabled": enabled,
        "simulator_ready": simulator_ready(),
        "production_directory": (
            "OIDC_CONFIGURED_NOT_QUALIFIED" if oidc_ready else "NOT_CONFIGURED"
        ),
        "oidc_configured": oidc_ready,
        "live_approval_ready": False,
        "execution_allowed": False,
    }


@router.get("/api/hitl/identity/simulator/catalog")
def identity_simulator_catalog(authorization: str | None = Header(default=None)):
    _require_internal(authorization)
    if not simulator_enabled():
        raise HTTPException(404, "identity_simulator_disabled")
    return {"items": simulator_catalog(), "simulated": True, "execution_allowed": False}


@router.post("/api/hitl/identity/simulator/token")
def identity_simulator_token(request: SimulatorTokenRequest, authorization: str | None = Header(default=None)):
    _require_internal(authorization)
    if not simulator_enabled():
        raise HTTPException(404, "identity_simulator_disabled")
    try:
        token, claims = issue_simulated_assertion(request.subject, request.ttl_seconds)
    except IdentityError as exc:
        raise HTTPException(403, str(exc)) from exc
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_at": claims["exp"],
        "identity": claims,
        "simulated": True,
        "execution_allowed": False,
    }
