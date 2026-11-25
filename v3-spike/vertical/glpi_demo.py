"""Synthetic GLPI followup preview; no network writes."""
import re
import html
from copilot_context import answer

def preview(ticket, followup, core, context):
    if ticket.get("synthetic") is not True or ticket.get("run_id") != core["run"]["run_id"]:
        raise ValueError("unverified synthetic ticket binding")
    tid, fid = ticket.get("id"), followup.get("id")
    if any(type(x) is not int or x <= 0 for x in (tid,fid)):
        raise ValueError("invalid identifiers")
    if followup.get("items_id") != tid or followup.get("itemtype") != "Ticket":
        raise ValueError("followup binding mismatch")
    question=followup.get("content")
    if not isinstance(question,str) or len(question)>1500 or not re.match(r"^@copilot\b",question,re.I):
        raise ValueError("unsupported followup")
    result=answer(core,context)
    sources="; ".join(e["evidence_id"]+" "+e["payload_hash"] for e in result["sources"])
    marker=f"AIOPS-V3-SYNTHETIC:{tid}:{fid}"
    return {"classification":"SYNTHETIC_GLPI_PREVIEW","input":{"itemtype":"Ticket","items_id":tid,"is_private":1,"content":html.escape(result["answer"]+"\n"+sources+"\n"+marker)},"marker":marker,"posted":False,"operational_decision":"DENY","production_authorized":False}
