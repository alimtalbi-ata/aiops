"""Read-only composition of existing Core AI Ledger, NOC and GLPI adapters.

The caller must obtain ``core_detail`` and ``ledger`` through existing
server-side authorized Core readers. This module does not authenticate Core,
verify evidence payloads or authorize tenant access. An internal ledger
reference is never an independently verified evidence capture.

Only the existing GLPI adapter may perform I/O: one bounded HTTPS GET using
server-supplied credentials. A signed NOC ticket is a *claim*, never a
verified GLPI ticket. No writes, no LIVE or remediation actions.
"""
from shared.acme_itsm_evidence_link import project_itsm_evidence
from shared.acme_glpi_ticket_read import read_verified_glpi_link


def join_incident_run_ticket_evidence(core_detail, ledger, signed_noc=None, *,
                                      glpi_base_url=None, glpi_session_token=None,
                                      glpi_app_token=None, glpi_opener=None):
    """Compose qualified Core references and optional authenticated GLPI GET.

    Returns the existing ``aiops.acme-itsm-evidence-link.v1`` projection.
    ``ticket_id`` is non-null only after GLPI explicitly matches both IDs;
    ``evidence_refs`` remain SYNTHETIC_ONLY, not authenticated evidence.
    ``verified_evidence_ids`` stays empty: this join does not perform an
    independent authenticated Evidence API read. Do not render ledger refs
    as verified captures, even when GLPI confirms a ticket.
    Any invalid input yields UNKNOWN/null; no GLPI call is made for an
    unqualified Core projection or an absent signed NOC ticket claim.

    The injectable opener is for tests. Never forward user/browser-supplied
    GLPI credentials or treat this pure join as an authorization boundary.
    """
    projection = project_itsm_evidence(core_detail, ledger, signed_noc)
    result = read_verified_glpi_link(
        projection, base_url=glpi_base_url,
        session_token=glpi_session_token, app_token=glpi_app_token,
        opener=glpi_opener,
    )
    # Internal Core AI Ledger references (even hashed and timestamped) are
    # not authenticated Evidence API records. A confirmed GLPI ticket does
    # not upgrade them. Keep source references distinct from verified IDs.
    result["verified_evidence_id"] = None
    result["verified_evidence_ids"] = []
    result["evidence_verification"] = "UNKNOWN_NO_AUTHENTICATED_EVIDENCE_API_READ"
    return result
