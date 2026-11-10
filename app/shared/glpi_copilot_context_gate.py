"""Read-only canonical GLPI → Core Run context selection.

Pure adapter boundary for the historical Copilot route. Never trust ticket text,
browser role/tenant headers, or caller-provided 'verified' booleans as evidence.
Inputs MUST be independently authenticated server-side observations and a
tenant-scoped canonical association obtained by trusted adapters.
This function performs no network calls, writes, proposals or execution.
"""
from shared.glpi_sync_authority import authorize_existing_ticket_update


def select_copilot_run_context(core_association, glpi_observation):
    """Return Run context identity only after strict precondition checks.

    Deliberately reuses the conservative DEMO-only authority gate for now;
    this is not an authorization decision for GLPI PUT or Core proposal.
    The returned object is a candidate, not an attestation.
    """
    identity = authorize_existing_ticket_update(core_association, glpi_observation)
    return {
        "status": "CANDIDATE_VERIFIED_INPUTS",
        "run_id": identity["run_id"],
        "incident_id": identity["incident_id"],
        "ticket_id": identity["ticket_id"],
        "tenant_id": identity["tenant_id"],
        "glpi_entity_id": identity["glpi_entity_id"],
        "glpi_instance_id": identity["glpi_instance_id"],
        "proposal_created": False,
        "execution_allowed": False,
        "actions_performed": [],
    }
