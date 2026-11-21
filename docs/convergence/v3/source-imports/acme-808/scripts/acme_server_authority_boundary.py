"""Fail-closed ACME autonomous-workbench viewer authorization boundary.

No HTTP, IdP network, Core/Worker I/O or credentials. An actual Portal adapter
must independently verify the server session and obtain authoritative grants.
This contract deliberately has no positive authorization path until a trusted
runtime provider is implemented and separately qualified.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VerifiedActor:
    issuer: str
    subject: str


class IdentityProvider(Protocol):
    def authenticated_actor(self, server_session_id: str) -> VerifiedActor | None: ...


class GrantProvider(Protocol):
    def tenant_allowed(self, actor: VerifiedActor, tenant_id: str) -> bool: ...
    def exact_run_allowed(self, actor: VerifiedActor, tenant_id: str,
                          run_id: str) -> bool: ...


def authorize_acme_view(*, session_id: object, tenant_id: object,
                        attempt_id: object, run_id: object,
                        identity_provider: IdentityProvider | None = None,
                        grant_provider: GrantProvider | None = None) -> dict:
    """A design boundary, NOT a browser or Core access grant.

    Provider objects are injectable and therefore NOT runtime attestation.
    Even if they return true, this function must fail closed until the real
    Portal verifies identity, grants and persisted Core attempt/run binding.
    """
    denied = {"status": "NO_GO", "http_status": 503,
              "reason": "VIEWER_AUTHORITY_NOT_RUNTIME_QUALIFIED",
              "evidence_read_allowed": False, "autonomous_action_allowed": False}
    if identity_provider is None or grant_provider is None:
        return denied
    if (type(session_id) is not str or not session_id
            or type(tenant_id) is not str or type(attempt_id) is not str
            or type(run_id) is not str):
        return {**denied, "http_status": 401, "reason": "VIEWER_SESSION_INVALID"}
    # Do not invoke caller-injected providers here: without a trusted runtime
    # adapter, their booleans are forgeable and could leak existence of runs.
    return denied
