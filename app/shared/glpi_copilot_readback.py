"""Server-side readback orchestrator for GLPI → Copilot (read-only).

Dependencies are injected *trusted server adapters*, never browser payloads.
Until a tenant-scoped canonical xref resolver is implemented, the default
resolver is absent and the orchestrator fails closed. No GLPI writes, HITL
proposal, Copilot query or Core mutation can be triggered by this module.
"""
from collections.abc import Callable
from shared.glpi_copilot_context_gate import select_copilot_run_context


class GLPICopilotReadbackBlocked(RuntimeError):
    pass


def resolve_glpi_copilot_context(
    *, ticket_id: str, actor: str, tenant_id: str,
    resolve_canonical_xref: Callable | None = None,
    read_core_run: Callable | None = None,
    read_glpi_ticket: Callable | None = None,
):
    """Independently read Core and GLPI before returning candidate context.

    The canonical resolver must enforce actor/tenant ACL and uniqueness.
    The readers must authenticate to their upstream and verify provenance.
    The adapter is deliberately unmounted until those contracts are proven.
    """
    if not all((isinstance(v, str) and v.strip()) for v in (ticket_id, actor, tenant_id)):
        raise GLPICopilotReadbackBlocked("actor_tenant_ticket_required")
    if not (ticket_id.isascii() and ticket_id.isdecimal()
            and len(ticket_id) <= 18 and ticket_id[0] in "123456789"):
        raise GLPICopilotReadbackBlocked("invalid_ticket_id")
    if not all(callable(fn) for fn in
               (resolve_canonical_xref, read_core_run, read_glpi_ticket)):
        raise GLPICopilotReadbackBlocked("authenticated_adapters_not_installed")
    try:
        association = resolve_canonical_xref(
            actor=actor, tenant_id=tenant_id, ticket_id=ticket_id)
        if not isinstance(association, dict):
            raise ValueError("association_missing")
        if association.get("tenant_id") != tenant_id or association.get("ticket_id") != ticket_id:
            raise ValueError("association_scope_mismatch")
        run_id = association.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_missing")
        core = read_core_run(actor=actor, tenant_id=tenant_id, run_id=run_id)
        glpi = read_glpi_ticket(actor=actor, tenant_id=tenant_id,
                                ticket_id=ticket_id,
                                glpi_instance_id=association.get("glpi_instance_id"))
        if not isinstance(core, dict) or not isinstance(glpi, dict):
            raise ValueError("upstream_payload_invalid")
        # Only the trusted resolver may supply the association's canonical
        # identity. Independently compare each reader to it, not to each other.
        fields = ("tenant_id", "glpi_instance_id", "glpi_entity_id",
                  "ticket_id", "incident_id", "run_id")
        for field in fields:
            if (not isinstance(association.get(field), str)
                    or core.get(field) != association[field]
                    or glpi.get(field) != association[field]):
                raise ValueError("readback_identity_mismatch")
        # Readback and ACL flags are *adapter claims*, not independent proof.
        # No production callsite is allowed until adapter provenance is audited.
        candidate = select_copilot_run_context(core, glpi)
        return candidate
    except Exception as exc:
        raise GLPICopilotReadbackBlocked("canonical_readback_unverified") from exc
