"""Pure authorization policy for future tenant-scoped incident reads.

Not an authentication provider. Callers must derive the principal and resource
tenant from independently authenticated server-side sources, never request input.
Not wired to browser routes until those sources are qualified.
"""
from dataclasses import dataclass
import re

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", re.ASCII)
_READ_ROLES = frozenset({"N1", "N2", "N3", "MANAGER"})


@dataclass(frozen=True)
class IncidentReadPrincipal:
    subject: str
    tenant: str
    role: str


def _identifier(value):
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def may_read_incident(principal: IncidentReadPrincipal | None, resource_tenant: str | None) -> bool:
    """Deny unknown identities, scopes and roles; require exact tenant match."""
    return (
        type(principal) is IncidentReadPrincipal
        and _identifier(principal.subject)
        and _identifier(principal.tenant)
        and isinstance(principal.role, str)
        and principal.role in _READ_ROLES
        and _identifier(resource_tenant)
        and principal.tenant == resource_tenant
    )
