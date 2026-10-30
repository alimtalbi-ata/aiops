"""Read-only composition of existing Core AI Ledger, NOC and GLPI adapters.

The caller must obtain ``core_detail`` and ``ledger`` through existing
server-side authorized Core readers. This module does not authenticate Core,
verify evidence payloads or authorize tenant access. An internal ledger
reference is never an independently verified evidence capture.

Only the existing GLPI and Core Evidence-ref readers perform I/O: bounded
GETs using server-supplied credentials. A signed NOC ticket is a *claim*,
never a verified GLPI ticket. No writes, LIVE or remediation actions.
"""
from shared.acme_itsm_evidence_link import project_itsm_evidence
from shared.acme_glpi_ticket_read import read_verified_glpi_link
from shared.acme_core_evidence_refs_read import read_authenticated_core_evidence_refs


def join_incident_run_ticket_evidence(core_detail, ledger, signed_noc=None, *,
                                      glpi_base_url=None, glpi_session_token=None,
                                      glpi_app_token=None, glpi_opener=None,
                                      core_evidence_base_url=None,
                                      core_evidence_token=None,
                                      core_evidence_opener=None):
    """Compose qualified Core refs with optional authenticated GLPI/Core GETs.

    ``ticket_id`` is non-null only after GLPI explicitly matches both IDs.
    ``core_evidence_ref_ids_verified`` is a *synthetic Core reference* match
    from the authenticated read-only Core evidence-refs endpoint, not a
    runtime/tenant/evidence-capture attestation. Independently verified
    evidence remains UNKNOWN. Credentials must be server-owned, never from
    the browser; injected openers are for offline tests only.
    """
    projection = project_itsm_evidence(core_detail, ledger, signed_noc)
    result = read_verified_glpi_link(
        projection, base_url=glpi_base_url,
        session_token=glpi_session_token, app_token=glpi_app_token,
        opener=glpi_opener,
    )
    result.update(read_authenticated_core_evidence_refs(
        result, base_url=core_evidence_base_url,
        bearer_token=core_evidence_token, opener=core_evidence_opener,
    ))
    # Core's authenticated evidence-refs GET confirms only synthetic database
    # and run-event references. It cannot verify a real capture or tenant ACL.
    result["verified_evidence_id"] = None
    result["verified_evidence_ids"] = []
    result["evidence_verification"] = "UNKNOWN_NO_AUTHENTICATED_EVIDENCE_API_READ"
    return result
