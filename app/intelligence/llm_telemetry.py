"""Bounded, provider-reported LLM usage and wall-clock telemetry.

No prompts, model outputs, API keys or incident payloads are retained.
Missing provider usage is represented as None, never inferred.
"""
from contextvars import ContextVar
from time import perf_counter

_CALLS = ContextVar("aiops_llm_calls", default=None)

def reset():
    _CALLS.set([])

def record(started, response=None, status="ok"):
    calls=_CALLS.get()
    if calls is None:
        calls=[]
        _CALLS.set(calls)
    usage={}
    if response is not None:
        try:
            data=response.json()
            raw=data.get("usage")
            if isinstance(raw,dict):
                for key in ("prompt_tokens","completion_tokens","total_tokens"):
                    val=raw.get(key)
                    usage[key]=val if type(val) is int and val>=0 else None
        except (ValueError,TypeError,AttributeError):
            pass
    calls.append({"attempt":len(calls)+1,"duration_ms":round((perf_counter()-started)*1000,2),
                  "status":status,**{k:usage.get(k) for k in ("prompt_tokens","completion_tokens","total_tokens")}})

def snapshot():
    calls=list(_CALLS.get() or [])
    totals={}
    for key in ("prompt_tokens","completion_tokens","total_tokens"):
        vals=[c[key] for c in calls if c[key] is not None]
        totals[key]=sum(vals) if vals and len(vals)==len(calls) else None
    return {"attempts":len(calls),"duration_ms":round(sum(c["duration_ms"] for c in calls),2),
            "calls":calls,**totals}
