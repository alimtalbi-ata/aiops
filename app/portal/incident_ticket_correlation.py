"""Offline, read-only correlation contract for an AIOps incident/Run/GLPI ticket.

This function does not fetch services or authorize a caller. Its output is never
runtime attestation or permission to act. The caller must independently enforce
server-derived actor/tenant/entity ACLs before supplying authoritative records.
"""
from __future__ import annotations

import re

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)
SCHEMA = "aiops.incident-run-ticket-correlation.v1"


def _identifier(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None


def correlate_incident_run_ticket(incident, run, ticket, *, actor_acl_qualified=False):
    """Return a conservative identity-only join; never expose source records."""
    result = {
        "schema": SCHEMA,
        "state": "UNKNOWN",
        "reason": "UNQUALIFIED_INPUT",
        "incident_run_match": False,
        "ticket_run_match": False,
        "tenant_acl_qualified": False,
        "runtime_attested": False,
        "live_remediation_authorized": False,
    }
    # A caller-controlled boolean is not sufficient proof of ACL enforcement:
    # this contract can describe matches, but never mark ACL qualified.
    if actor_acl_qualified is not True:
        result["reason"] = "ACTOR_TENANT_ACL_REQUIRED"
        return result
    if not all(isinstance(item, dict) for item in (incident, run, ticket)):
        return result
    # Reject unknown identity shapes rather than silently choosing aliases.
    keys = (
        (incident, ("incident_id", "tenant_id")),
        (run, ("run_id", "incident_id", "tenant_id", "mode")),
        (ticket, ("ticket_id", "incident_id", "run_id", "tenant_id")),
    )
    if not all(_identifier(record.get(key)) for record, fields in keys
               for key in fields if key != "mode"):
        result["reason"] = "INVALID_OR_MISSING_IDENTITY"
        return result
    if run.get("mode") not in ("DEMO", "REPLAY", "STORY"):
        result["reason"] = "LIVE_OR_UNKNOWN_MODE_REFUSED"
        return result
    if not (incident["tenant_id"] == run["tenant_id"] == ticket["tenant_id"]):
        result["reason"] = "TENANT_MISMATCH"
        return result
    result["incident_run_match"] = incident["incident_id"] == run["incident_id"]
    result["ticket_run_match"] = (ticket["run_id"] == run["run_id"] and
                                  ticket["incident_id"] == incident["incident_id"])
    if result["incident_run_match"] and result["ticket_run_match"]:
        result["state"] = "MATCHED_UNATTESTED"
        result["reason"] = "IDENTITIES_MATCH_NOT_RUNTIME_ATTESTATION"
    else:
        result["reason"] = "IDENTITY_MISMATCH"
    return result
