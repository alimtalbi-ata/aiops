"""Isolated authorization adapter; not connected to HTTP or a real IdP.

The membership resolver must be a trusted server-side authority, not a
browser-provided claim. Its failures must never grant access.
"""
from portal.incident_read_policy import IncidentReadPrincipal, may_read_incident


def authorize_incident_read(sessions, token, resource_tenant, membership_resolver):
    try:
        principal = sessions.resolve(token)
        if not may_read_incident(principal, resource_tenant):
            return False
        current = membership_resolver(principal.subject, principal.tenant)
        if type(current) is not IncidentReadPrincipal or current != principal:
            sessions.revoke(token)
            return False
        return may_read_incident(current, resource_tenant)
    except Exception:
        return False
