#!/usr/bin/env python3
"""Diagnose existing Core↔GLPI linkage, read-only and fail-closed.

Input: live run_linkage_gate JSON. Optional GLPI REST readback JSON.
Never creates, modifies, or reconciles tickets automatically.
"""
import argparse
import json
from pathlib import Path

def diagnose(linkage, readback=None):
    db=linkage.get("database") or {}
    checks=linkage.get("checks") or {}
    run=db.get("run") or {}
    observed=(linkage.get("external_glpi_observation") or {}).get("ticket_id")
    links=db.get("glpi_links") or []
    xrefs=db.get("itsm_xref") or []
    matched=[x for x in links if observed is not None and str(x.get("glpi_ticket_id"))==str(observed)]
    other=[x for x in links if observed is not None and str(x.get("glpi_ticket_id"))!=str(observed)]
    matching_xref=[x for x in xrefs if observed is not None and str(x.get("ticket_id"))==str(observed)]
    glpi=(readback or {}).get("ticket") or {}
    incident_id=run.get("incident_id")
    identity_ok=(bool(linkage.get("run_id")) and bool(incident_id)
                 and run.get("run_id")==linkage.get("run_id"))
    rows_identity_ok=all(x.get("incident_id")==incident_id for x in links+xrefs)
    readback_identity_ok=(readback is None or (
        readback.get("run_id")==linkage.get("run_id")
        and readback.get("incident_id")==incident_id
        and str(glpi.get("ticket_id"))==str(observed)))
    marker_verified=(readback_identity_ok and glpi.get("readback")=="MATCHED_MARKER"
                     and all(glpi.get(k) is True for k in (
                         "ticket_id_verified", "ticket_active", "run_marker_present", "incident_marker_present")))
    if not run:
        cause="CORE_RUN_MISSING"
        action="Repair run persistence/identity before ITSM reconciliation"
    elif not identity_ok or not rows_identity_ok or not readback_identity_ok:
        cause="IDENTITY_MISMATCH"
        action="Verify exact Run/Incident/ticket identity; do not reconcile"
    elif observed is None:
        cause="TICKET_ID_NOT_PROVIDED"
        action="Supply the existing observed ticket ID; do not create a ticket"
    elif other or len(matched)>1:
        cause="DIFFERENT_TICKET_LINKED" if other and not matched else "AMBIGUOUS_TICKET_LINKS"
        action="Review conflicting or duplicate links; preserve confirmed links"
    elif readback is not None and not marker_verified:
        cause="GLPI_READBACK_AUTH_REQUIRED" if glpi.get("readback")=="AUTH_REQUIRED" else "GLPI_TICKET_IDENTITY_MISMATCH"
        action="Verify existing ticket through native GLPI GET before reconciliation"
    elif matched and any(x.get("state")=="CONFIRMED" for x in matched) and any(x.get("glpi_ticket_readback_verified") is True for x in matching_xref):
        cause="LINK_VERIFIED"
        action=None
    elif matched:
        cause="LINK_PRESENT_NOT_CONFIRMED"
        action="Inspect existing link state and readback reconciliation, without inserting duplicates"
    elif matching_xref:
        cause="XREF_WITHOUT_CORE_LINK"
        action="Repair link projection from existing xref event; preserve original ticket identity"
    elif marker_verified:
        cause="GLPI_MARKERS_MATCH_CORE_LINK_ABSENT"
        action="Inspect ITSM event consumer/outbox and idempotent Core link persistence"
    else:
        cause="CORE_LINK_ABSENT_GLPI_UNVERIFIED"
        action="Read existing GLPI ticket identity, then inspect ITSM outbox and Core link consumer"
    return {"schema":"aiops2-itsm-link-diagnosis-v1",
            "run_id":linkage.get("run_id"),"incident_id":run.get("incident_id"),
            "observed_ticket_id":observed,"read_only":True,"cause":cause,
            "link_count":len(links),"xref_count":len(xrefs),
            "matching_link_count":len(matched),"matching_xref_count":len(matching_xref),
            "glpi_readback":glpi.get("readback","NOT_CHECKED"),
            "core_link_check":checks.get("glpi_core_link"),
            "next_action":action,
            "verdict":"PASS" if cause=="LINK_VERIFIED" else "HOLD"}
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
