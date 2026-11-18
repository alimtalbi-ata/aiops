"""Unregistered activity body adapted from #348; explicit injected transport only."""
import asyncio
from worker.acme_simulated_hitl import (
    SandboxDenied, validated_service_origin, decode_authority_json,
    simulate_no_effect,
)

def read_bounded_authority_response(response):
    """Consume an authenticated HTTP readback with a hard streaming byte cap.

    requests.Response.content buffers the *entire* response before a size
    check. A compromised internal peer could exhaust Worker memory before
    fail-closed validation. Require stream=True at the GET call site.
    """
    if response.status_code != 200:
        raise SandboxDenied("sandbox_service_denied_or_unavailable")
    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=8192):
        if type(chunk) is not bytes:
            raise SandboxDenied("sandbox_readback_json_unqualified")
        total += len(chunk)
        if total > 32768:
            raise SandboxDenied("sandbox_service_denied_or_unavailable")
        chunks.append(chunk)
    return decode_authority_json(b"".join(chunks))



async def acme_simulated_no_effect(intent, *, enabled, origins, token, session_factory, now=None):
    """Offline preparation: no default transport, registration or environment lookup."""
    if enabled is not True:
        raise SandboxDenied("sandbox_disabled")

    async def read(component, path):
        origin = validated_service_origin(component, origins.get(component))

        def fetch():
            with session_factory() as session:
                session.trust_env = False
                with session.get(
                    origin.rstrip("/") + path,
                    headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
                    timeout=8, allow_redirects=False, stream=True) as response:
                    return read_bounded_authority_response(response)

        return await asyncio.to_thread(fetch)

    return await simulate_no_effect(intent, get=read, now=now)
