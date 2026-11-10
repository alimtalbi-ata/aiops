"""Read-only Core/GLPI xref qualification using raw upstream response shapes.

A server-owned signed-xref resolver is mandatory. Raw upstream observations
cannot attest tenant or actor ACL. This operation deliberately returns a
*comparison*, not a Copilot authorization or write permission.
"""
from collections.abc import Callable

from shared.glpi_readback_comparison import compare_raw_readbacks_to_association
from shared.glpi_signed_xref_boundary import resolve_signed_glpi_xref


class GLPIRawQualificationBlocked(RuntimeError):
    pass


def qualify_raw_glpi_core_readbacks(
    *, actor: str, tenant_id: str, ticket_id: str,
    fetch_signed_event: Callable | None = None,
    verify_event_and_acl: Callable | None = None,
    read_core_raw: Callable | None = None,
    read_glpi_raw: Callable | None = None,
):
    """Check authenticated source responses against independently verified xref.

    Server-owned readers must use authenticated upstream clients and must not
    fabricate identity fields. No default adapters exist. No side effects.
    """
    if not callable(read_core_raw) or not callable(read_glpi_raw):
        raise GLPIRawQualificationBlocked("raw_readers_unavailable")
    try:
        association = resolve_signed_glpi_xref(
            actor=actor, tenant_id=tenant_id, ticket_id=ticket_id,
            fetch_signed_event=fetch_signed_event,
            verify_event_and_acl=verify_event_and_acl,
        )
        core = read_core_raw(actor=actor, tenant_id=tenant_id,
                             run_id=association["run_id"])
        glpi = read_glpi_raw(actor=actor, tenant_id=tenant_id,
                             ticket_id=association["ticket_id"],
                             glpi_instance_id=association["glpi_instance_id"])
        comparison = compare_raw_readbacks_to_association(
            association=association, core_payload=core, glpi_payload=glpi
        )
        return {
            "status": "RAW_READBACKS_MATCH_SIGNED_XREF_CLAIMS",
            "run_id": comparison["run_id"],
            "incident_id": comparison["incident_id"],
            "ticket_id": comparison["ticket_id"],
            "glpi_entity_id": comparison["glpi_entity_id"],
            "tenant_id": association["tenant_id"],
            "glpi_instance_id": association["glpi_instance_id"],
            "copilot_query_performed": False,
            "hitl_proposal_created": False,
            "glpi_write_performed": False,
            "execution_allowed": False,
        }
    except Exception as exc:
        raise GLPIRawQualificationBlocked("canonical_raw_readbacks_not_qualified") from exc
