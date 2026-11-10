"""Compose HMAC-authenticated canonical xref and raw Core/GLPI comparison.

All dependencies are server-injected. This does not install any production
key, event store, ACL, HTTP client or Portal route. No write or proposal.
"""
from collections.abc import Callable

from shared.glpi_readback_comparison import compare_raw_readbacks_to_association
from shared.glpi_xref_resolver_factory import make_hmac_canonical_xref_resolver


class GLPIHmacQualificationBlocked(RuntimeError):
    pass


def make_hmac_glpi_qualifier(
    *, secret: bytes, fetch_signed_event: Callable,
    consume_nonce: Callable, authorize_actor: Callable,
    read_core_raw: Callable, read_glpi_raw: Callable,
    clock: Callable | None = None,
):
    """Return a read-only qualifier, with all trust dependencies required."""
    if not callable(read_core_raw) or not callable(read_glpi_raw):
        raise ValueError("authenticated_raw_readers_missing")
    resolver = make_hmac_canonical_xref_resolver(
        secret=secret, fetch_signed_event=fetch_signed_event,
        consume_nonce=consume_nonce, authorize_actor=authorize_actor,
        clock=clock,
    )

    def qualify(*, actor, tenant_id, ticket_id):
        try:
            association = resolver(actor=actor, tenant_id=tenant_id,
                                   ticket_id=ticket_id)
            core_payload = read_core_raw(
                actor=actor, tenant_id=tenant_id,
                run_id=association["run_id"])
            glpi_payload = read_glpi_raw(
                actor=actor, tenant_id=tenant_id,
                ticket_id=association["ticket_id"],
                glpi_instance_id=association["glpi_instance_id"])
            comparison = compare_raw_readbacks_to_association(
                association=association, core_payload=core_payload,
                glpi_payload=glpi_payload,
            )
            return {
                "status": "READ_ONLY_XREF_COMPARISON",
                "run_id": comparison["run_id"],
                "incident_id": comparison["incident_id"],
                "ticket_id": comparison["ticket_id"],
                "glpi_entity_id": comparison["glpi_entity_id"],
                "tenant_id": association["tenant_id"],
                "glpi_instance_id": association["glpi_instance_id"],
                "glpi_write_performed": False,
                "copilot_query_performed": False,
                "hitl_proposal_created": False,
                "execution_allowed": False,
            }
        except Exception as exc:
            raise GLPIHmacQualificationBlocked("glpi_core_xref_not_qualified") from exc

    return qualify
