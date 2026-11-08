#!/usr/bin/env python3
"""Diagnose existing Core↔GLPI linkage, read-only and fail-closed.

Input: live run_linkage_gate JSON. Optional GLPI REST readback JSON.
Never creates, modifies, or reconciles tickets automatically.
"""
import argparse
import json
from pathlib import Path

def _identity(value):
    return type(value) is str and bool(value) and value.strip() == value


def _ticket(value):
    # Do not coerce booleans, floats, null or zero into a ticket identity.
    if type(value) is int:
        return str(value) if value > 0 else None
    if type(value) is str and value.isascii() and value.isdecimal():
        return value if value and value[0] != "0" else None
    return None


def diagnose(linkage, readback=None):
    """Offline claims classifier, never an authenticated API verifier.

    Even mutually consistent JSON receipts are not independent GLPI proof.
    LINK_VERIFIED/PASS are deliberately unavailable here. Reuse the scoped Core
    xref verifier after its deployment/provenance is qualified; do not trust a
    caller-controlled authenticated=true or database verified=true instead.
    """
    linkage = linkage if isinstance(linkage, dict) else {}
    db = linkage.get("database")
    db = db if isinstance(db, dict) else {}
    run = db.get("run")
    run = run if isinstance(run, dict) else {}
    observation = linkage.get("external_glpi_observation")
    observation = observation if isinstance(observation, dict) else {}
    observed = observation.get("ticket_id")
    ticket = _ticket(observed)
    links, xrefs = db.get("glpi_links", []), db.get("itsm_xref", [])
    rows_valid = (isinstance(links, list) and isinstance(xrefs, list)
                  and all(isinstance(x, dict) for x in links + xrefs))
    links = links if isinstance(links, list) else []
    xrefs = xrefs if isinstance(xrefs, list) else []
    rb_valid = readback is None or isinstance(readback, dict)
    rb = readback if isinstance(readback, dict) else {}
    glpi = rb.get("ticket", {})
    rb_valid = rb_valid and isinstance(glpi, dict)
    glpi = glpi if isinstance(glpi, dict) else {}
    matched = [x for x in links if isinstance(x, dict) and ticket is not None
               and _ticket(x.get("glpi_ticket_id")) == ticket]
    matching_xref = [x for x in xrefs if isinstance(x, dict) and ticket is not None
                     and _ticket(x.get("ticket_id")) == ticket]
    incident = run.get("incident_id")
    rid = linkage.get("run_id")
    conflicts, missing = [], []
    if not _identity(rid) or not _identity(incident) or run.get("run_id") != rid:
        conflicts.append("core_run_identity")
    if rows_valid and rb_valid:
        identity_rows = [run] + links + xrefs + ([rb] if readback is not None else [])
        for field in ("tenant_id", "glpi_instance_id"):
            claims = [linkage.get(field)] + [x.get(field) for x in identity_rows]
            present = [x for x in claims if x is not None]
            if any(not _identity(x) for x in present) or len(set(x for x in present if _identity(x))) > 1:
                conflicts.append(field)
            if not _identity(linkage.get(field)) or any(x.get(field) is None for x in identity_rows):
                missing.append(field)
        for row in links + xrefs:
            if row.get("incident_id") != incident:
                conflicts.append("incident_id")
            if row.get("run_id") is not None and row["run_id"] != rid:
                conflicts.append("run_id")
        # Incident-scoped rows alone cannot establish the requested Run's xref.
        if any(x.get("run_id") is None for x in xrefs):
            missing.append("xref_run_id")
        if any(_ticket(x.get("ticket_id")) != ticket for x in xrefs):
            conflicts.append("xref_ticket_id")
        if readback is not None:
            if rb.get("run_id") != rid or rb.get("incident_id") != incident or _ticket(glpi.get("ticket_id")) != ticket:
                conflicts.append("readback_identity")
            # Also refuse contradictory identity claims inside the ticket body.
            for field, expected in (("run_id", rid), ("incident_id", incident),
                                    ("tenant_id", linkage.get("tenant_id")),
                                    ("glpi_instance_id", linkage.get("glpi_instance_id"))):
                if field in glpi and glpi[field] != expected:
                    conflicts.append("ticket_" + field)
    marker_claim = (glpi.get("http") == 200 and glpi.get("readback") == "MATCHED_MARKER"
                    and all(glpi.get(k) is True for k in (
                        "ticket_id_verified", "ticket_active", "run_marker_present", "incident_marker_present")))
    if not rows_valid or not rb_valid:
        cause = "MALFORMED_REPORT"
    elif not run:
        cause = "CORE_RUN_MISSING"
    elif ticket is None:
        cause = "TICKET_ID_NOT_PROVIDED"
    elif len(xrefs) > 1:
        # No collapsing duplicates or selecting any verified row from history.
        # Supersession/version validation belongs to the authoritative Core path.
        cause = "AMBIGUOUS_XREFS"
    elif conflicts:
        cause = "IDENTITY_MISMATCH"
    elif any(x.get("event_type") == "REVOKED"
             or x.get("glpi_ticket_readback_verified") is False
             or x.get("core_run_readback_verified") is False for x in xrefs):
        cause = "XREF_CONTRADICTORY"
    elif len(links) > 1:
        cause = "AMBIGUOUS_TICKET_LINKS"
    elif links and not matched:
        cause = "DIFFERENT_TICKET_LINKED"
    elif glpi.get("readback") == "AUTH_REQUIRED":
        cause = "GLPI_READBACK_AUTH_REQUIRED"
    elif readback is not None and not marker_claim:
        cause = "GLPI_TICKET_IDENTITY_MISMATCH"
    elif missing and (links or xrefs):
        cause = "IDENTITY_UNVERIFIED"
    elif matched and matched[0].get("state") == "CONFIRMED" and matching_xref:
        cause = "LINK_CONSISTENT_UNATTESTED"
    elif matched:
        cause = "LINK_PRESENT_NOT_CONFIRMED"
    elif matching_xref:
        cause = "XREF_WITHOUT_CORE_LINK"
    elif marker_claim:
        cause = "GLPI_MARKERS_MATCH_CORE_LINK_ABSENT"
    else:
        cause = "CORE_LINK_ABSENT_GLPI_UNVERIFIED"
    checks = linkage.get("checks")
    checks = checks if isinstance(checks, dict) else {}
    return {"schema": "aiops2-itsm-link-diagnosis-v2",
            "run_id": rid, "incident_id": incident,
            "observed_ticket_id": observed, "read_only": True, "cause": cause,
            "link_count": len(links), "xref_count": len(xrefs),
            "matching_link_count": len(matched), "matching_xref_count": len(matching_xref),
            "identity_conflicts": sorted(set(conflicts)), "missing_identity": sorted(set(missing)),
            "glpi_readback": glpi.get("readback", "NOT_CHECKED"),
            "independent_verification": "NOT_PERFORMED_BY_OFFLINE_DIAGNOSIS",
            "core_link_check": checks.get("glpi_core_link"),
            "next_action": "Verify scoped identities through the existing authenticated Core/GLPI read path; preserve links and Policy denial",
            "verdict": "HOLD"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--linkage",required=True,type=Path)
    p.add_argument("--glpi-readback",type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    linkage=json.loads(a.linkage.read_text())
    readback=json.loads(a.glpi_readback.read_text()) if a.glpi_readback else None
    result=diagnose(linkage,readback)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result["verdict"]=="PASS" else 2
if __name__=="__main__":
    raise SystemExit(main())
