"""Pure fail-closed authorization for an existing GLPI ticket update.

Candidate only. Does not perform HTTP, create tickets, attest xrefs, or change
GLPI/Copilot endpoints. Callers must obtain observations independently from
authenticated Core and GLPI adapters; never from browser-provided JSON.
"""
import hmac
import re

_RUN = re.compile(r"RUN-[A-Z0-9]{8,64}\Z")
_INCIDENT = re.compile(r"INC-[A-Za-z0-9_-]{4,128}\Z")
_TICKET = re.compile(r"[1-9][0-9]*\Z")


def authorize_existing_ticket_update(core, glpi):
    """Return an authorized identity tuple or raise ValueError (fail closed).

    This is a *necessary*, not sufficient, condition for PUT. The caller must
    independently enforce server-side actor/tenant ACL and Policy/HITL fences.
    No CREATE is ever authorized by this function.
    """
    if not isinstance(core, dict) or not isinstance(glpi, dict):
        raise ValueError("xref_unverified")
    if core.get("mode") != "DEMO" or core.get("execution_allowed") is not False:
        raise ValueError("mode_or_execution_not_safe")
    if core.get("core_run_readback_verified") is not True:
        raise ValueError("core_readback_unverified")
    if glpi.get("glpi_ticket_readback_verified") is not True:
        raise ValueError("glpi_readback_unverified")
    if core.get("tenant_acl_verified") is not True or core.get("actor_acl_verified") is not True:
        raise ValueError("acl_unverified")
    if core.get("association_state") != "ACTIVE":
        raise ValueError("association_not_active")
    fields = ("tenant_id", "glpi_instance_id", "glpi_entity_id", "ticket_id",
              "incident_id", "run_id")
    for field in fields:
        a, b = core.get(field), glpi.get(field)
        if not isinstance(a, str) or not a or not isinstance(b, str) or not b:
            raise ValueError("xref_identity_missing")
        if not hmac.compare_digest(a.encode(), b.encode()):
            raise ValueError("xref_identity_mismatch")
    if not _RUN.fullmatch(core["run_id"]) or not _INCIDENT.fullmatch(core["incident_id"]):
        raise ValueError("invalid_core_identity")
    if not _TICKET.fullmatch(core["ticket_id"]):
        raise ValueError("invalid_ticket_id")
    if core.get("association_count") != 1 or glpi.get("matching_ticket_count") != 1:
        raise ValueError("ambiguous_association")
    return {field: core[field] for field in fields}
