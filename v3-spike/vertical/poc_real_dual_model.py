"""E21 CPU experiment: actual Ollama inference over synthetic E18 cases."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import build_opener, ProxyHandler
from dual_model_advisory import review, config, NoRedirect
from test_historical_analyst_critic import HistoricalAnalystCriticTest

SPECS=(("qwen2.5:0.5b-instruct","a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67"),("qwen2.5:7b-instruct","845dbda0ea48"))
IMAGE="ollama/ollama@sha256:1514372d3cef7387b6202b253e761d820e00e44b28f268aad5029389d0479e99"

def get(port,path):
    with build_opener(ProxyHandler({}),NoRedirect()).open("http://127.0.0.1:"+str(port)+path,timeout=10) as response:
        raw=response.read(65537)
        if len(raw)>65536:raise ValueError("metadata exceeds bound")
        return json.loads(raw)

def attest(port,model,expected_digest):
    entries=get(port,"/api/tags")["models"]
    rows=[row for row in entries if row.get("name")==model]
    if len(rows)!=1:raise ValueError("expected single model")
    sha=rows[0]["digest"].removeprefix("sha256:")
    full_pin=len(expected_digest)==64
    if not re.fullmatch("[a-f0-9]{64}",sha) or not re.fullmatch("[a-f0-9]{12}|[a-f0-9]{64}",expected_digest) or (sha!=expected_digest if full_pin else not sha.startswith(expected_digest)):
        raise ValueError("pinned model fingerprint mismatch")
    version=get(port,"/api/version")["version"]
    if version!="0.11.4":raise ValueError("unexpected Ollama version")
    return {"model":model,"manifest_sha256":sha,"expected_digest":expected_digest,
            "full_digest_preconfigured":full_pin,"engine_version":version}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--analyst-port",type=int,required=True)
    parser.add_argument("--critic-port",type=int,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    ports=(args.analyst_port,args.critic_port)
    providers=[config({"endpoint":"http://127.0.0.1:%d/v1/chat/completions"%port,"model":spec[0]}) for port,spec in zip(ports,SPECS)]
    if len(set(ports))!=2:raise ValueError("distinct endpoints required")
    report={"classification":"E21_REAL_LOCAL_MODEL_EXPERIMENT","result":"FAIL","source_sha":os.environ.get("E21_SOURCE_SHA"),
            "image":IMAGE,"experiment_variant":"V4_CRITIC_7B_PROTOCOL_V3","models":[],"cases":[],"production_authorized":False,
            "model_independence_attested":False,"scope":"synthetic E18 history fixture; actual local model inference"}
    def save():
        args.report.parent.mkdir(parents=True,exist_ok=True)
        tmp=args.report.with_suffix(".tmp")
        tmp.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
        tmp.replace(args.report)
    save()
    try:
        report["models"]=[attest(port,*spec) for port,spec in zip(ports,SPECS)]
        if len({x["manifest_sha256"] for x in report["models"]})!=2:raise ValueError("model digests must differ")
        save()
        fixture=HistoricalAnalystCriticTest()
        cases=(("forward",fixture.history(),"CANDIDATE_ONLY",2),
               ("reverse",fixture.history(dep_at="2026-01-01T09:00:02Z"),"DISPUTED",2),
               ("overlap",fixture.history(dependent_at="2026-01-01T09:00:00Z"),"DISPUTED",2))
        for name,history,expected,expected_calls in cases:
            started=time.monotonic()
            out=review(history,*providers,timeout_seconds=120)
            calls=out["invocations"]
            safe=(out["root_cause"]=="UNKNOWN" and out["confidence"] is None and out["causality_established"] is False
                  and out["production_authorized"] is False and out["operational_decision"]=="DENY")
            expected_verdict="AGREE_CANDIDATE" if name=="forward" else "CHALLENGE_CANDIDATE"
            actual_verdict=(out["critic"] or {}).get("verdict")
            passed=(safe and out["state"]==expected and actual_verdict==expected_verdict and len(calls)==expected_calls and all(x["status"]=="VALIDATED" for x in calls))
            report["cases"].append({"case":name,"expected_state":expected,"actual_state":out["state"],
                "safe":safe,"pass":passed,"expected_critic_verdict":expected_verdict,"actual_critic_verdict":actual_verdict,"wall_ms":round((time.monotonic()-started)*1000,3),
                "context_sha256":out["context_sha256"],"analyst":out["analyst"],"critic":out["critic"],"invocations":calls})
            save()
        after=[attest(port,*spec) for port,spec in zip(ports,SPECS)]
        report["model_digests_unchanged"]=after==report["models"]
        report["result"]="PASS" if report["model_digests_unchanged"] and all(x["pass"] for x in report["cases"]) else "FAIL"
    except Exception as exc:
        report["error_class"]=type(exc).__name__
    finally:
        save()
        print(json.dumps(report,sort_keys=True))
    return 0 if report["result"]=="PASS" else 1

if __name__=="__main__":sys.exit(main())
