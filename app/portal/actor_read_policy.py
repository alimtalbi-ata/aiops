"""Explicit actor/tenant read policy foundation. Not connected to authentication.
Only a trusted server-side identity provider may construct a principal.
No browser claims, shared tokens, or role labels establish identity.
"""
from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    N1 = "N1"
    N2 = "N2"
    N3 = "N3"
    MANAGER = "MANAGER"


@dataclass(frozen=True)
class Principal:
    actor_id: str
    tenant_id: str
    role: Role


_READ_PERMISSIONS = {
    Role.N1: frozenset({"incident.read", "run.read"}),
    Role.N2: frozenset({"incident.read", "run.read", "evidence.read"}),
    Role.N3: frozenset({"incident.read", "run.read", "evidence.read", "decision.read"}),
    Role.MANAGER: frozenset({"incident.read", "run.read", "decision.read"}),
}


def allows_read(principal: Principal | None, resource_tenant: str, permission: str) -> bool:
    """Deny unknown identity, tenant, role, and permission; no write grants."""
    if not isinstance(principal, Principal):
        return False
    if not isinstance(principal.role, Role):
        return False
    if not all(isinstance(v, str) and v and v == v.strip()
               for v in (principal.actor_id, principal.tenant_id, resource_tenant, permission)):
        return False
    return (principal.tenant_id == resource_tenant
            and permission in _READ_PERMISSIONS.get(principal.role, frozenset()))
