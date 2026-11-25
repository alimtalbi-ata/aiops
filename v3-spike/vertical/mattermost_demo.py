"""Mattermost slash-command response contract; isolated synthetic POC."""
import hmac
import json
from urllib.parse import parse_qs
from copilot_context import answer

def authenticate(body, token, channel):
    if not isinstance(body, bytes) or len(body)>4096 or not isinstance(token,str) or len(token)<32:
        raise ValueError("invalid request")
    fields=parse_qs(body.decode("utf-8"), strict_parsing=True, max_num_fields=20)
    def one(key):
        values=fields.get(key,[])
        if len(values)!=1:
            raise ValueError("invalid field")
        return values[0]
    if not hmac.compare_digest(one("token").encode(),token.encode()) or one("channel_id")!=channel or one("command")!="/aiops":
        raise ValueError("unauthorized")
    return one("text").strip()

def command(body, token, channel, core, context):
    if authenticate(body,token,channel) not in ("status","incident","rca","evidence"):
        return {"response_type":"ephemeral","text":"Synthetic POC: use status, incident, rca or evidence. Operational DENY."}
    result=answer(core,context)
    sources="\n".join("- "+e["evidence_id"]+" | "+e["payload_hash"] for e in result["sources"])
    return {"response_type":"ephemeral","text":"**AIOPS V3 — SYNTHETIC**\n"+result["answer"]+"\nRun: "+result["run_id"]+"\n"+sources}
