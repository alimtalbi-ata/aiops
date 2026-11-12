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
    if not run:
        cause="CORE_RUN_MISSING"
        action="Repair run persistence/identity before ITSM reconciliation"
    elif observed is None:
        cause="TICKET_ID_NOT_PROVIDED"
        action="Supply the existing observed ticket ID; do not create a ticket"
    elif matched and any(x.get("state")=="CONFIRMED" for x in matched) and any(x.get("glpi_ticket_readback_verified") is True for x in matching_xref):
        cause="LINK_VERIFIED"
        action=None
    elif matched:
        cause="LINK_PRESENT_NOT_CONFIRMED"
        action="Inspect existing link state and readback reconciliation, without inserting duplicates"
    elif other:
        cause="DIFFERENT_TICKET_LINKED"
        action="Investigate ticket identity mismatch; never overwrite or create a duplicate"
    elif matching_xref:
        cause="XREF_WITHOUT_CORE_LINK"
        action="Repair link projection from existing xref event; preserve original ticket identity"
    elif glpi.get("readback")=="MATCHED_MARKER":
        cause="GLPI_MARKERS_MATCH_CORE_LINK_ABSENT"
        action="Inspect ITSM event consumer/outbox and idempotent Core link persistence"
    elif glpi.get("readback")=="MISMATCH":
        cause="GLPI_TICKET_IDENTITY_MISMATCH"
        action="Do not reconcile until ticket identity is verified"
    elif glpi.get("readback")=="AUTH_REQUIRED":
        cause="GLPI_READBACK_AUTH_REQUIRED"
        action="Configure existing read-only GLPI API access; do not expose tokens"
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
