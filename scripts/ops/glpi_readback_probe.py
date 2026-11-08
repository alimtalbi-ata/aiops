#!/usr/bin/env python3
"""Read-only GLPI ticket identity probe for AIOps2.

Runs on Debian, from the existing GLPI container's network namespace.
Uses the GLPI database *only if* configured, and never mutates it.
Default mode uses GLPI REST with explicit API credentials supplied through
environment variables (not CLI arguments). Do not write credentials to output.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

def glpi_get(base, path, token, app_token=None):
    headers={"Session-Token":token, "Accept":"application/json"}
    if app_token: headers["App-Token"]=app_token
    req=urllib.request.Request(base.rstrip("/")+"/apirest.php/"+path.lstrip("/"),headers=headers,method="GET")
    try:
        with urllib.request.urlopen(req,timeout=12) as response:
            return response.status,json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code,{"error":"HTTP_"+str(exc.code)}

def exact_marker(text, marker):
    """Reject prefixes/suffixes of another canonical identifier."""
    return bool(marker and re.search(r"(?<![\w-])" + re.escape(marker) + r"(?![\w-])", text))


def inspect_ticket(ticket, run_id, incident_id, base, token, app_token=None):
    status,payload=glpi_get(base,f"Ticket/{ticket}",token,app_token)
    if status in (401,403):
        return {"ticket_id":ticket,"readback":"AUTH_REQUIRED","http":status}
    if status!=200 or not isinstance(payload,dict):
        return {"ticket_id":ticket,"readback":"UNVERIFIED","http":status}
    title=str(payload.get("name") or "")
    content=str(payload.get("content") or "")
    # Exact run marker is necessary but not sufficient for a durable Core link.
    match=exact_marker(title, run_id) or exact_marker(content, run_id)
    incident_match=exact_marker(title, incident_id) or exact_marker(content, incident_id)
    ticket_match=(type(payload.get("id")) is int and payload["id"] == ticket)
    active=payload.get("is_deleted") in (0, "0") and type(payload.get("is_deleted")) is not bool
    identity_match=ticket_match and match and incident_match and active
    return {"ticket_id":ticket,"http":status,"readback":"MATCHED_MARKER" if identity_match else "MISMATCH",
            "ticket_id_verified":ticket_match,"ticket_active":active,
            "run_marker_present":match,"incident_marker_present":incident_match,
            "title_excerpt":title[:180],"glpi_status":payload.get("status"),
            "glpi_date":payload.get("date")}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run-id",default="RUN-8CA56A39E58944F1")
    p.add_argument("--incident-id",default="INC-FS1250-AUTOGLPI-625916362ACD42C9")
    p.add_argument("--ticket-id",type=int,default=201)
    p.add_argument("--base-url",default=os.environ.get("AIOPS2_GLPI_BASE_URL","http://127.0.0.1:8080"))
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    token=os.environ.get("AIOPS2_GLPI_SESSION_TOKEN")
    app_token=os.environ.get("AIOPS2_GLPI_APP_TOKEN")
    if not token:
        report={"readback":"AUTH_REQUIRED","reason":"AIOPS2_GLPI_SESSION_TOKEN not configured"}
    else:
        report=inspect_ticket(a.ticket_id,a.run_id,a.incident_id,a.base_url,token,app_token)
    result={"schema":"aiops2-glpi-readback-v1",
            "collected_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "read_only":True,"run_id":a.run_id,"incident_id":a.incident_id,
            "ticket":report,
            "core_xref_state":"NOT_CHECKED_BY_THIS_PROBE",
            "interpretation":"GLPI marker matching is evidence, not a Core xref or authorization to create/modify tickets"}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"report":str(a.output),"readback":report.get("readback"),
                      "http":report.get("http")}))
    return 0 if report.get("readback")=="MATCHED_MARKER" else 2

if __name__=="__main__":
    sys.exit(main())
