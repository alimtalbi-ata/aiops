"""Build a fail-closed candidate from independently read raw Core/GLPI data.

This is an adapter composition helper, NOT a canonical xref resolver.
Only a server-owned association resolver with audited ACL/provenance can
supply the missing tenant, instance and association identity.
"""
from shared.glpi_raw_readback import (
    normalize_core_run_readback, normalize_glpi_ticket_readback,
)


def compare_raw_readbacks_to_association(
    *, association, core_payload, glpi_payload
):
    """Check observed identities; never synthesize absent GLPI/Core fields."""
    if not isinstance(association, dict):
        raise ValueError("canonical_association_missing")
    run_id = association.get("run_id")
    ticket_id = association.get("ticket_id")
    if not isinstance(run_id, str) or not isinstance(ticket_id, str):
        raise ValueError("canonical_identity_missing")
    core = normalize_core_run_readback(core_payload, expected_run_id=run_id)
    glpi = normalize_glpi_ticket_readback(glpi_payload, expected_ticket_id=ticket_id)
    if core["incident_id"] != association.get("incident_id"):
        raise ValueError("core_incident_association_mismatch")
    if glpi["glpi_entity_id"] != association.get("glpi_entity_id"):
        raise ValueError("glpi_entity_association_mismatch")
    # The following are NOT asserted: tenant ACL, GLPI instance provenance,
    # unique canonical xref, signed attestation, authenticated HTTP, or HITL.
    return {
        "run_id": core["run_id"],
        "incident_id": core["incident_id"],
        "ticket_id": glpi["ticket_id"],
        "glpi_entity_id": glpi["glpi_entity_id"],
        "raw_readbacks_match": True,
        "canonical_association_attested": False,
        "tenant_acl_verified": False,
        "actor_acl_verified": False,
        "execution_allowed": False,
    }
