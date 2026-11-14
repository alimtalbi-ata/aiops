"""Fail-closed server-side gate for future read-only Incident/Run/GLPI views.

No network access, token verification or authorization is performed here.
Only a separately authenticated, server-derived scope may be evaluated.
Never accept this scope from HTTP headers, query parameters or JSON bodies.
"""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import re

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)


def _valid(value: object) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


@dataclass(frozen=True)
class VerifiedReadScope:
    """Issued only after upstream authentication and tenant/entity authorization.

    A constructed object alone is NOT evidence that a real ACL was checked.
    This is an additional local restriction, not an authentication provider.
    """
    actor_id: str
    tenant_id: str
    glpi_entity_id: str
    permitted_incident_ids: frozenset[str]


def evaluate_ticket_read_scope(
    scope: VerifiedReadScope | None,
    *,
    tenant_id: object,
    glpi_entity_id: object,
    incident_id: object,
    mode: object,
) -> dict[str, object]:
    """Return no identities, even on denial; never authorize LIVE or writes."""
    result: dict[str, object] = {
        "state": "DENIED",
        "reason": "SERVER_AUTHORIZATION_REQUIRED",
        "read_scope_match": False,
        "runtime_attested": False,
        "live_remediation_authorized": False,
        "glpi_write_enabled": False,
    }
    if not isinstance(scope, VerifiedReadScope):
        return result
    fields = (scope.actor_id, scope.tenant_id, scope.glpi_entity_id,
              tenant_id, glpi_entity_id, incident_id)
    if not all(_valid(value) for value in fields):
        result["reason"] = "INVALID_IDENTITY"
        return result
    if not isinstance(scope.permitted_incident_ids, frozenset) or not all(
        _valid(value) for value in scope.permitted_incident_ids
    ):
        result["reason"] = "INVALID_SCOPE"
        return result
    if mode not in ("DEMO", "REPLAY", "STORY"):
        result["reason"] = "LIVE_OR_UNKNOWN_MODE_REFUSED"
        return result
    if not hmac.compare_digest(scope.tenant_id, tenant_id) or not hmac.compare_digest(
        scope.glpi_entity_id, glpi_entity_id
    ):
        result["reason"] = "SCOPE_MISMATCH"
        return result
    if incident_id not in scope.permitted_incident_ids:
        result["reason"] = "INCIDENT_NOT_PERMITTED"
        return result
    result["state"] = "SCOPE_MATCH_UNATTESTED"
    result["reason"] = "LOCAL_SCOPE_MATCH_NOT_AUTHENTICATION"
    result["read_scope_match"] = True
    return result
