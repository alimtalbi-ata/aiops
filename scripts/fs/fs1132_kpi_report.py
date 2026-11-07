#!/usr/bin/env python3
"""FS1132: offline, read-only campaign KPI analysis of completed FS1130 JSONL reports."""
import collections
import json
import pathlib
import statistics
import sys

def percentile(values, fraction):
    if not values: return None
    v=sorted(values); pos=(len(v)-1)*fraction; lo=int(pos); hi=min(lo+1,len(v)-1)
    return round(v[lo]+(v[hi]-v[lo])*(pos-lo),2)

def analyze(path):
    records=[json.loads(line) for line in pathlib.Path(path).read_text().splitlines() if line.strip()]
    starts=[r for r in records if r.get("type")=="start"]
    summaries=[r for r in records if r.get("type")=="summary"]
    if len(starts)!=1 or len(summaries)!=1:
        raise ValueError("campaign_incomplete_or_invalid: one start and one summary required")
    summary=summaries[0]
    results=[r for r in records if r.get("type")=="result"]
    if len(results)!=summary.get("completed"):
        raise ValueError("campaign_incomplete_or_invalid: result count differs from summary")
    status=collections.Counter(r.get("status","UNKNOWN") for r in results)
    durations=[float(r["elapsed_seconds"]) for r in results if isinstance(r.get("elapsed_seconds"),(int,float)) and r["elapsed_seconds"]>=0]
    errors=collections.Counter((r.get("error") or "unspecified")[:150] for r in results if r.get("error"))
    counts={k:sum(bool(r.get(k,0)) for r in results) for k in ("analysis","critique","policy","evidence")}
    return {
        "campaign":summary.get("campaign"),"source":str(path),"mode":"DEMO_SYNTHETIC",
        "target":starts[0].get("target"),"submitted":summary.get("submitted"),
        "completed":len(results),"status_counts":dict(status),
        "resolved":status.get("RESOLVED",0),"blocked":status.get("BLOCKED",0),
        "failed":status.get("FAILED",0),"timeout":status.get("TIMEOUT",0)+status.get("QUERY_TIMEOUT",0),
        "submission_failed":status.get("SUBMISSION_FAILED",0),
        "success_rate_resolved":round(status.get("RESOLVED",0)/len(results),4) if results else None,
        "median_elapsed_seconds":round(statistics.median(durations),2) if durations else None,
        "p95_elapsed_seconds":percentile(durations,.95),
        "max_elapsed_seconds":round(max(durations),2) if durations else None,
        "duration_samples":len(durations),
        "with_analysis":counts["analysis"],"with_critique":counts["critique"],
        "with_policy":counts["policy"],"with_evidence":counts["evidence"],
        "effect_receipts":sum(int(r.get("effects",0)) for r in results),
        "error_samples":[{"error":key,"count":value} for key,value in errors.most_common(10)],
        "analyst_model_latency_ms":None,"critic_model_latency_ms":None,
        "prompt_tokens":None,"completion_tokens":None,"total_tokens":None,
        "tokens_reason":"FS1130 did not capture provider usage or exact LLM call latency",
        "safety_note":"BLOCKED may be a correct fail-closed policy decision; not automatically a technical failure",
        "comparability_note":"50 distinct incident labels reuse common synthetic SAN evidence in current Worker",
    }

def main(argv):
    if len(argv)>2:raise SystemExit("usage: fs1132_kpi_report.py [FS1130-report.jsonl]")
    if len(argv)==2:paths=[pathlib.Path(argv[1])]
    else:
        paths=sorted((pathlib.Path.home()/"aiops2-qualification-reports").glob("FS1130-*.jsonl"))
        if not paths:raise SystemExit("No FS1130 report found; pass an explicit report path")
        paths=[paths[-1]]
    result=analyze(paths[0])
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if result["effect_receipts"]:raise SystemExit(3)
    if result["completed"]!=result["target"] or result["submitted"]!=result["target"]:raise SystemExit(2)

if __name__=="__main__":
    main(sys.argv)
