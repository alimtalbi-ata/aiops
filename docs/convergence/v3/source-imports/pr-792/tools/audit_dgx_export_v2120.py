#!/usr/bin/env python3
"""Offline, fail-closed DGX provenance audit for user-provided run evidence JSON.
Never fetches Core, DGX or live endpoints. Does not attest cryptographic provenance.
"""
import argparse,hashlib,json
from pathlib import Path
RUN_ID="RUN-A4449145A6E377FF"
STATES={"ABSENT","STAGE_MARKER","SYNTHETIC","UNKNOWN","RECORDED"}
def assess(record):
    if not isinstance(record,dict):raise ValueError("JSON object required")
    run=record.get("run_id")
    if not isinstance(run,str) or not run.startswith("RUN-"):raise ValueError("run_id required")
    claims=record.get("claims",[])
    evidence=record.get("evidence",[])
    if not isinstance(claims,list) or not isinstance(evidence,list):raise ValueError("arrays required")
    evidence_by_id={}
    for e in evidence:
        if not isinstance(e,dict) or not isinstance(e.get("id"),str) or not e["id"]:raise ValueError("invalid evidence record")
        if e["id"] in evidence_by_id:raise ValueError("duplicate evidence id")
        evidence_by_id[e["id"]]=e
    results=[]
    for c in claims:
        if not isinstance(c,dict) or not isinstance(c.get("role"),str):raise ValueError("invalid claim")
        refs=c.get("supporting_evidence_ids",[])
        if not isinstance(refs,list) or any(not isinstance(ref,str) for ref in refs):raise ValueError("invalid evidence references")
        linked=[]
        for ref in refs:
            e=evidence_by_id.get(ref)
            if e is None:state="ABSENT"
            elif e.get("synthetic") is True:state="SYNTHETIC"
            elif e.get("stage_marker") is True:state="STAGE_MARKER"
            elif e.get("origin") not in ("agent_log","telemetry","cmdb","model_response"):state="UNKNOWN"
            else:state="RECORDED"
            linked.append({"id":ref,"status":state})
        verdict=c.get("validated")
        if verdict is True:validation="DECLARED_TRUE"
        elif verdict is False:validation="DECLARED_FALSE"
        else:validation="UNKNOWN"
        results.append({"role":c["role"],"model_declared":c.get("model"),
            "validation":validation,"evidence":linked,
            "evidence_verified":False,"model_execution_independently_verified":False})
    return {"run_id":run,"scope":"OFFLINE_USER_SUPPLIED_EXPORT",
        "source_authenticated":False,"dgx_execution_verified":False,
        "live_remediation_verified":False,"claims":results,
        "warning":"Recorded evidence and model identifiers do not prove genuine DGX inference, causality or a LIVE effect."}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True,help="Existing exported JSON; no network access")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.input.resolve()==args.output.resolve():parser.error("input and output must differ")
    report=assess(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(args.output),"sha256":hashlib.sha256(args.output.read_bytes()).hexdigest(),"claims":len(report["claims"]),"dgx_execution_verified":False},ensure_ascii=False))
if __name__=="__main__":main()
