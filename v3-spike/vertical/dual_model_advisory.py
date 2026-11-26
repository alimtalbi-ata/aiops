"""E20 experimental dual-model advisory boundary, synthetic loopback only.
No automatic provider discovery, credentials, tools, retry, fallback or host actions.
E18 is the trusted deterministic baseline; a model cannot establish causation.
"""
import json
import re
import time
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from enterprise_context import digest
from historical_analyst_critic import assess

MAX_REQUEST_BYTES=65536
MAX_RESPONSE_BYTES=65536
MAX_OUTPUT_TOKENS=1024
PROMPT_VERSION="E21_V3"
class AdvisoryRejection(ValueError):
    """Fixed diagnostic codes only; never raw provider output."""
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def config(value):
    if not isinstance(value,dict) or set(value)!={"endpoint","model"}:
        raise ValueError("explicit provider configuration required")
    endpoint=value["endpoint"]
    model=value["model"]
    match=re.fullmatch(r"http://127\.0\.0\.1:(\d{1,5})/v1/chat/completions",endpoint) if isinstance(endpoint,str) else None
    if not match or not 1024<=int(match[1])<=65535 or int(match[1]) in (7770,7777,7790):
        raise ValueError("isolated loopback model endpoint required")
    if not isinstance(model,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}",model):
        raise ValueError("invalid configured model")
    return {"endpoint":endpoint,"model":model}

def strict_json(value):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError("duplicate JSON key")
            result[k]=v
        return result
    def reject(_):raise ValueError("invalid JSON constant")
    return json.loads(value,object_pairs_hook=pairs,parse_constant=reject)

def usage(payload):
    item=payload.get("usage")
    keys=("prompt_tokens","completion_tokens","total_tokens")
    if isinstance(item,dict) and all(type(item.get(k)) is int and item[k]>=0 for k in keys) and item["total_tokens"]==item["prompt_tokens"]+item["completion_tokens"]:
        return {"usage_source":"provider_reported",**{k:item[k] for k in keys}}
    return {"usage_source":"unavailable",**{k:None for k in keys}}

def call(role,provider,context,timeout_seconds=10):
    candidates=context["candidates"]
    selected=context.get("analyst_selection")
    eligible=[c for c in candidates if role=="ANALYST" or c["candidate_id"]==selected["candidate_id"]]
    verdicts=["SELECT_CANDIDATE"] if role=="ANALYST" else ["AGREE_CANDIDATE","CHALLENGE_CANDIDATE"]
    def decision_schema(candidate,refs,verdict_values):
        return {"type":"object","properties":{
            "candidate_id":{"type":"null"} if candidate is None else {"type":"string","enum":[candidate]},
            "evidence_ids":{"type":"array","items":{"type":"string","enum":refs} if refs else {"type":"string"},
                            "minItems":len(refs),"maxItems":len(refs)},
            "verdict":{"type":"string","enum":verdict_values}},
            "required":["candidate_id","evidence_ids","verdict"],"additionalProperties":False}
    # Abstention and selection are mutually exclusive schema branches. Keep
    # every eligible candidate and abstention available; no answer is filled in.
    schema={"anyOf":[decision_schema(c["candidate_id"],c["evidence_ids"],verdicts) for c in eligible]
                    +[decision_schema(None,[],["ABSTAIN"])]}
    system=("Review synthetic dependency candidates, never establish cause or authorize action. "
            "Return JSON only. Choose exactly one of two forms. SELECT: copy candidate_id and ALL evidence_ids exactly; "
            + ("set verdict to SELECT_CANDIDATE. " if role=="ANALYST" else
               "review the analyst selection only; set verdict to AGREE_CANDIDATE or CHALLENGE_CANDIDATE. ")
            + 'ABSTAIN: {"candidate_id":null,"evidence_ids":[],"verdict":"ABSTAIN"}. '
            "Never combine a non-null candidate with ABSTAIN. Do not invent, shorten or repeat IDs. "
            + ("Temporal uncertainty may be passed as a candidate for the Critic to challenge." if role=="ANALYST" else
               "Challenge reverse or unresolved temporal ordering; abstain if unable to review."))
    body=json.dumps({"model":provider["model"],"temperature":0,"max_tokens":MAX_OUTPUT_TOKENS,
                     "response_format":{"type":"json_schema","json_schema":{"name":"advisory","strict":True,"schema":schema}},
                     "messages":[{"role":"system","content":system},
                     {"role":"user","content":json.dumps(context,separators=(",",":"),sort_keys=True)}]},separators=(",",":")).encode()
    if len(body)>MAX_REQUEST_BYTES:raise ValueError("request exceeds bounded context")
    receipt={"role":role,"model":provider["model"],"prompt_version":PROMPT_VERSION,"request_bytes":len(body),
             "request_count":1,"retry_count":0,"cost":None,"ttft_ms":None,"provider_identity_attested":False,
             "usage_source":"unavailable","prompt_tokens":None,"completion_tokens":None,"total_tokens":None}
    start=time.monotonic_ns()
    try:
        req=Request(provider["endpoint"],data=body,headers={"Content-Type":"application/json"})
        with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=timeout_seconds) as response:
            raw=response.read(MAX_RESPONSE_BYTES+1)
            if len(raw)>MAX_RESPONSE_BYTES:raise ValueError("response too large")
        payload=strict_json(raw)
        if payload.get("model")!=provider["model"]:raise ValueError("response model mismatch")
        receipt.update(usage(payload))
        choices=payload["choices"]
        if not isinstance(choices,list) or len(choices)!=1 or choices[0].get("finish_reason")!="stop":
            raise ValueError("incomplete model output")
        message=choices[0]["message"]
        if message.get("tool_calls") or message.get("function_call") or message.get("refusal"):
            raise ValueError("non-advisory response")
        raw_content=message["content"]
        if not isinstance(raw_content,str):raise ValueError("JSON text required")
        result=strict_json(raw_content)
        receipt["status"]="RECEIVED"
    except Exception:
        result=None
        receipt["status"]="UNAVAILABLE_OR_INVALID"
        receipt["rejection_code"]="TRANSPORT_OR_ENVELOPE_INVALID"
    receipt["latency_ms"]=round((time.monotonic_ns()-start)/1e6,3)
    return result,receipt

def _validate(output,candidates,role,selected=None):
    if not isinstance(output,dict) or set(output)!={"candidate_id","evidence_ids","verdict"}:
        raise AdvisoryRejection("SCHEMA_FIELDS_INVALID")
    cid,refs,verdict=output["candidate_id"],output["evidence_ids"],output["verdict"]
    if cid is None and refs==[] and verdict=="ABSTAIN":return output
    if verdict=="ABSTAIN":raise AdvisoryRejection("ABSTAIN_WITH_SELECTION")
    if not isinstance(cid,str) or cid not in candidates or not isinstance(refs,list) or not all(isinstance(x,str) for x in refs):
        raise AdvisoryRejection("CANDIDATE_OR_CITATION_TYPE_INVALID")
    if len(set(refs))!=len(refs) or sorted(refs)!=candidates[cid]["evidence_ids"]:
        raise AdvisoryRejection("CITATION_SET_MISMATCH")
    if role=="ANALYST" and verdict!="SELECT_CANDIDATE":raise AdvisoryRejection("ANALYST_VERDICT_INVALID")
    if role=="CRITIC" and (cid!=selected or verdict not in ("AGREE_CANDIDATE","CHALLENGE_CANDIDATE")):
        raise AdvisoryRejection("CRITIC_SELECTION_OR_VERDICT_INVALID")
    return {"candidate_id":cid,"evidence_ids":sorted(refs),"verdict":verdict}

def review(history,analyst_provider,critic_provider,*,timeout_seconds=10):
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=120:
        raise ValueError("invalid socket timeout")
    a,c=config(analyst_provider),config(critic_provider)
    if a["endpoint"]==c["endpoint"] or a["model"]==c["model"]:
        raise ValueError("distinct configured endpoints and models required")
    baseline=assess(history)
    candidates={}
    for h in baseline["analyst"]["hypotheses"]:
        # Minimal structured allowlist; no raw logs, documents or credentials.
        refs=h["dependent_evidence"]+h["dependency_evidence"]
        candidates[h["hypothesis_id"]]={"candidate_id":h["hypothesis_id"],
          "dependent_resource":h["candidate"]["dependent_resource"],"dependency_resource":h["candidate"]["dependency_resource"],
          "path":h["candidate"]["path"],"temporal_order":h["temporal_order"],
          "evidence_ids":sorted(r["evidence_id"] for r in refs)}
    context={"classification":"SYNTHETIC_LAB_ONLY","candidates":list(candidates.values()),
             "correlation_sha256":baseline["analyst"]["correlation_sha256"]}
    result={"classification":"SYNTHETIC_DUAL_MODEL_ADVISORY_E20","state":"UNKNOWN","analyst":None,"critic":None,
            "invocations":[],"context_sha256":digest(context),"root_cause":"UNKNOWN","confidence":None,
            "causality_established":False,"production_authorized":False,"operational_decision":"DENY",
            "model_independence_attested":False,"tenant_acl_qualified":False}
    if not candidates or baseline["analyst"]["candidates_truncated"]:return result
    for role,provider in (("ANALYST",a),("CRITIC",c)):
        payload=context if role=="ANALYST" else {**context,"analyst_selection":result["analyst"]}
        output,receipt=call(role,provider,payload,timeout_seconds)
        result["invocations"].append(receipt)
        try:
            checked=_validate(output,candidates,role,result["analyst"]["candidate_id"] if role=="CRITIC" else None)
        except AdvisoryRejection as exc:
            if receipt["status"]=="RECEIVED":
                receipt["status"]="REJECTED"
                receipt["rejection_code"]=str(exc)
            return result
        receipt["status"]="VALIDATED"
        result[role.lower()]=checked
        if checked["verdict"]=="ABSTAIN":return result
    chosen=candidates[result["analyst"]["candidate_id"]]
    result["state"]=("DISPUTED" if result["critic"]["verdict"]=="CHALLENGE_CANDIDATE"
        or chosen["temporal_order"]!="DEPENDENCY_OBSERVED_FIRST" else "CANDIDATE_ONLY")
    return result
