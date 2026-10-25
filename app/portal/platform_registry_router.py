"""Static, read-only component inventory mounted on the existing portal app.

This route has no upstream connections. It must never represent registry rows as
healthy or runtime-attested; connection routes require a separate reviewed adapter.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from portal.platform_registry import build_portal_component_registry

router = APIRouter()
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


@router.get("/api/platform/components", name="static_platform_component_registry")
def platform_components():
    """Return only the static convergence plan; no observations are fabricated."""
    payload = build_portal_component_registry()
    payload.update({
        "source_mode": "STATIC_REGISTRY_PLAN",
        "component_observation_source": "ABSENT",
        "route_mount_attested": False,
        "runtime_e2e_qualified": False,
        "production_qualified": False,
    })
    return JSONResponse(content=payload, headers=HEADERS)
