"""E26 read-only local synthetic telemetry projection. No inference or mutation."""
from contextlib import closing
import json,re,sqlite3
from enterprise_context import digest
from ai_invocation_ledger import validate_record

def snapshot(clock,run_ids):
    if (not isinstance(run_ids,list) or not 1<=len(run_ids)<=5 or any(not isinstance(x,str) or not re.fullmatch(r"RUN-[A-F0-9]{16}",x) for x in run_ids)
        or len(set(run_ids))!=len(run_ids)):raise ValueError("1–5 distinct synthetic run IDs required")
    # Use SQLite read-only URI: never create a ledger or modify the clock.
    with closing(sqlite3.connect(clock.path.as_uri()+"?mode=ro",uri=True,timeout=10)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_invocation_reviews'").fetchone()
        rows=db.execute("SELECT review_id,payload,payload_hash FROM ai_invocation_reviews ORDER BY review_id LIMIT 10001").fetchall() if exists else []
    if len(rows)>10000:raise ValueError("ledger exceeds bounded capacity")
    selected=[]
    for ident,raw,sha in rows:
        rec=json.loads(raw)
        if rec["review_id"]!=ident or digest(rec)!=sha:raise ValueError("corrupt ledger")
        validate_record(rec)
        # Entire review must be within explicitly requested run scope.
        if set(rec["run_ids"])<=set(run_ids):
            selected.append({"record":rec,"receipt_sha256":sha})
    if len(selected)>100:raise ValueError("too many scoped reviews")
    selected.sort(key=lambda r:(r["record"]["recorded_at"],r["record"]["review_id"]))
    calls=[c for r in selected for c in r["record"]["invocations"]]
    groups=[]
    import math
    for role,model,prompt in sorted({(x["role"],x["model"],x["prompt_version"]) for x in calls}):
        sub=[x for x in calls if (x["role"],x["model"],x["prompt_version"])==(role,model,prompt)]
        reported=[x for x in sub if x["usage_source"]=="provider_reported"]
        lat=sorted(x["latency_ms"] for x in sub)
        groups.append({"role":role,"model":model,"prompt_version":prompt,"invocations":len(sub),
            "validated":sum(x["status"]=="VALIDATED" for x in sub),"usage_reported_count":len(reported),
            "latency_p50_ms":lat[math.ceil(.5*len(lat))-1],"latency_p95_ms":lat[math.ceil(.95*len(lat))-1],
            **{k:sum(x[k] for x in reported) if len(reported)==len(sub) else None for k in ("prompt_tokens","completion_tokens","total_tokens")},
            "reported_partial_total_tokens":sum(x["total_tokens"] for x in reported) if reported else None,"cost":None,"ttft_ms":None})
    return {"classification":"SYNTHETIC_GAMMA_AI_TELEMETRY_E26","state":"AVAILABLE" if selected else "NO_RECEIPTS",
        "run_ids":sorted(run_ids),"review_count":len(selected),"invocation_count":len(calls),"groups":groups,
        "reviews":[{"review_id":r["record"]["review_id"],"run_ids":r["record"]["run_ids"],"state":r["record"]["state"],
          "recorded_at":r["record"]["recorded_at"],"context_sha256":r["record"]["context_sha256"],"receipt_sha256":r["receipt_sha256"]} for r in selected],
        "tenant_acl_qualified":False,"production_authorized":False,"operational_decision":"DENY"}
