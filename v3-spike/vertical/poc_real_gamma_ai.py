"""E28 actual synthetic Core/Evidence/Twin -> local Ollama -> GAMMA.
CI only, fresh dedicated root, no fixture provider or mocked history.
Never upload configuration, tokens, raw prompts or database dumps.
"""
import argparse,json,os,re,subprocess,sys,tempfile,time
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from contextlib import contextmanager,closing
from playwright.sync_api import sync_playwright,expect
from dual_model_advisory import NoRedirect,config
from poc_real_dual_model import SPECS,IMAGE,attest
from poc_real_rag import qualify
from rag_model_advisory import prepare
from enterprise_context import digest
from ai_invocation_ledger import InvocationLedger

KIT=Path(__file__).resolve().parent.parent/"kit"
def call(origin,path,data=None):
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin):raise ValueError("non-local origin")
    req=Request(origin+path,data=None if data is None else json.dumps(data).encode(),
        headers={"Origin":origin,"Content-Type":"application/json"})
    with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=30) as resp:
        return json.load(resp)

@contextmanager
def gamma():
    with tempfile.TemporaryFile(mode="w+b") as output:
        p=subprocess.Popen([sys.executable,str(KIT/"poc-gamma.py")],stdout=output,stderr=output)
        try:
            origin=None
            for _ in range(60):
                if p.poll() is not None:raise ValueError("launcher exited")
                output.seek(0)
                data=output.read(65536).decode(errors="replace")
                found=re.search(r"^POC GAMMA: (http://127\.0\.0\.1:[0-9]{4,5})$",data,re.M)
                if found:origin=found[1];break
                time.sleep(1)
            if origin is None or int(origin.rsplit(":",1)[1]) in (7770,7777,7790):raise ValueError("launcher unavailable")
            yield origin
        finally:
            p.terminate()
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=10)

def snapshot(root):
    import hashlib
    project="aiops-v3-poc-"+hashlib.sha256(str(root).encode()).hexdigest()[:12]
    compose=["docker","compose","--project-name",project,"--env-file",str(root/"poc.env"),"-f",str(KIT/"compose.poc-source.yml")]
    out={}
    for table in ("runs","run_events","evidence","gates","twin_nodes","twin_edges","command_receipts","execution_receipts"):
        query="select count(*), md5(coalesce(string_agg(to_jsonb(t)::text, '|' order by to_jsonb(t)::text), '')) from aiops."+table+" t"
        value=subprocess.check_output(compose+["exec","-T","postgres","psql","-v","ON_ERROR_STOP=1","-U","aiops","-d","aiops","-Atc",query],text=True,timeout=30).strip()
        if not re.fullmatch(r"[0-9]+\|[a-f0-9]{32}",value):raise ValueError("snapshot invalid")
        out[table]=value
    return out

def seed(origin):
    if call(origin,"/api/v1/enterprise-clock")["current_tick"]!=0:raise ValueError("fresh clock required")
    selected={}
    for tick in range(1,4):
        call(origin,"/api/v1/enterprise-clock/advance",{"expected_tick":tick})
        capture=call(origin,"/api/v1/enterprise-clock/capture-scenarios",{"expected_tick":tick})
        if capture["state"]!="PUBLISHED":raise ValueError("publication failed")
        for r in capture["incidents"]:
            if r["scenario_id"] in ("WAN_LOSS","CPU_SATURATION"):selected[r["scenario_id"]]=r
    if set(selected)!={"WAN_LOSS","CPU_SATURATION"}:raise ValueError("campaign incomplete")
    ids=sorted(r["run_id"] for r in selected.values())
    payload={"run_ids":ids,"window_seconds":240}
    history=call(origin,"/api/v1/enterprise-correlation/historical",payload)
    actual={(r["run_id"],r["evidence_id"],r["payload_hash"]) for g in history["groups"] for signal in g["signals"] for r in signal["evidence_refs"]}
    expected={(r["run_id"],e["evidence_id"],e["payload_hash"]) for r in selected.values() for e in r["evidence"]}
    if len(actual)!=8 or actual!=expected or history["verified_evidence_count"]!=8:raise ValueError("Evidence mismatch")
    return payload,history

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--analyst-port",type=int,required=True)
    parser.add_argument("--critic-port",type=int,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    root=Path(os.environ["V3_ROOT"])
    if os.environ.get("GITHUB_ACTIONS")!="true" or root!=Path("/tmp/aiops-v3-e28-ci") or root.resolve()!=root:raise ValueError("dedicated CI only")
    ports=(args.analyst_port,args.critic_port)
    providers=[config({"endpoint":"http://127.0.0.1:%d/v1/chat/completions"%p,"model":s[0]}) for p,s in zip(ports,SPECS)]
    if len(set(ports))!=2:raise ValueError("distinct providers required")
    report={"classification":"E28_REAL_GAMMA_CORE_EVIDENCE_RAG_EXPERIMENT","result":"FAIL","source_sha":os.environ.get("E28_SOURCE_SHA"),
            "image":IMAGE,"production_authorized":False,"model_independence_attested":False,"tenant_acl_qualified":False}
    def save():
        args.report.parent.mkdir(parents=True,exist_ok=True)
        tmp=args.report.with_suffix(".tmp");tmp.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");tmp.replace(args.report)
    save()
    config_path=root/"ai-runtime.json"
    created=False
    try:
        report["models"]=[attest(p,*s) for p,s in zip(ports,SPECS)]
        with os.fdopen(os.open(config_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),"w") as f:
            created=True;json.dump(dict(zip(("analyst","critic"),providers)),f)
        with gamma() as origin:
            payload,history=seed(origin)
            ids=payload["run_ids"]
            ledger=InvocationLedger(root)
            context=prepare(history,ledger.clock)
            if len(context["candidates"])!=1 or not context["candidates"][0]["reference_context"]:raise ValueError("missing candidate or approved reference")
            report.update(run_ids=ids,verified_evidence_count=8,context_sha256=digest(context))
            before=snapshot(root)
            if call(origin,"/api/v1/ai-telemetry",{"run_ids":ids})["state"]!="NO_RECEIPTS":raise ValueError("unexpected prior review")
            save()
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                try:
                    page=browser.new_page()
                    page.goto(origin)
                    expect(page.locator("#ai-runtime-review")).to_be_enabled(timeout=10000)
                    page.locator("#assessment-runs").fill(" ".join(ids))
                    page.locator("#assessment-window").fill("240")
                    with page.expect_response(lambda r:r.url==origin+"/api/v1/enterprise-correlation/ai-review",timeout=280000) as event:
                        page.locator("#ai-runtime-review").click()
                    response=event.value
                    if not response.ok:raise ValueError("review HTTP failure")
                    result=response.json()
                    out=result["assessment"]
                    report["assessment"]=out
                    report["quality"]=qualify(out,context)
                    report["review_id"]=result["review_id"]
                    report["receipt_sha256"]=result["receipt_sha256"]
                    save()
                    expect(page.locator("#ai-runtime-result")).to_contain_text("Persisted receipt verified",timeout=30000)
                    page.locator("#ai-runtime-measures").click()
                    expect(page.locator("#ai-telemetry-result")).to_contain_text(result["review_id"],timeout=30000)
                    report["browser_receipt_verified"]=True
                finally:browser.close()
            telemetry=call(origin,"/api/v1/ai-telemetry",{"run_ids":ids})
            stored=ledger.read(result["review_id"])
            report["ledger_match"]=(stored["receipt_sha256"]==result["receipt_sha256"] and stored["record"]["invocations"]==out["invocations"]
                and stored["record"]["context_sha256"]==digest(context)==out["context_sha256"] and telemetry["review_count"]==1
                and telemetry["invocation_count"]==len(out["invocations"]) and telemetry["reviews"][0]["receipt_sha256"]==result["receipt_sha256"])
            report["core_evidence_unchanged"]=before==snapshot(root)
            save()
        with gamma() as origin:
            report["restart_readback_match"]=(call(origin,"/api/v1/ai-telemetry",{"run_ids":ids})==telemetry
                and call(origin,"/api/v1/enterprise-correlation/historical",payload)==history
                and InvocationLedger(root).read(result["review_id"])==stored)
        report["model_digests_unchanged"]=[attest(p,*s) for p,s in zip(ports,SPECS)]==report["models"]
        if report["quality"]["pass"] and all(report[k] for k in ("browser_receipt_verified","ledger_match","core_evidence_unchanged","restart_readback_match","model_digests_unchanged")):report["result"]="PASS"
    except Exception as exc:
        report["error_class"]=type(exc).__name__
    finally:
        if created:config_path.unlink()
        save();print(json.dumps(report,sort_keys=True))
    return 0 if report["result"]=="PASS" else 1

if __name__=="__main__":sys.exit(main())
