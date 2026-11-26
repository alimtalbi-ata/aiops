"""E25 real Ollama RAG experiment over persisted synthetic campaign fixtures.
Publication is a local synthetic adapter, not actual Core/Evidence service proof.
No arbitrary documents, credentials, deployment or production authority.
"""
import argparse,json,os,sys,tempfile,time
from pathlib import Path
from contextlib import closing
from enterprise_context import digest
from enterprise_historical_correlation import historical_preview
from historical_analyst_critic import assess
from ingestion_demo import ingest
from rag_model_advisory import prepare,wire_projection
from ai_invocation_ledger import InvocationLedger
from dual_model_advisory import config
from poc_real_dual_model import SPECS,IMAGE,attest
from test_enterprise_context import graph

def seed(ledger):
    runs={}
    def publish(rows):
        normalized=ingest(rows)["incidents"]
        if len(normalized)!=1:raise ValueError("fixture incident ambiguous")
        item=normalized[0]
        rid="RUN-"+digest(rows)[:16].upper()
        run={"run_id":rid,"mode":"DEMO","incident_id":"INC-CI-INGEST-"+digest(rows)[16:48]}
        signals=item["evidence"]
        refs=[{"evidence_id":"E25-%s-%d"%(rid[-8:],i),"payload_hash":digest(sig)} for i,sig in enumerate(signals)]
        runs[rid]=({"run":run},{"run_id":rid,"root":rows[0]["resource"],"classification":"SYNTHETIC_LAB_CONTEXT",
            "production_authorized":False,"evidence":refs,"verified_signals":[{**r,"signal":s} for r,s in zip(refs,signals)]})
        return {"production_authorized":False,"core":{"run":run},"stored_evidence":refs}
    selected={}
    for tick in range(1,4):
        ledger.clock.advance(tick,publish)
        capture=ledger.clock.capture_scenarios(tick,publish)
        for row in capture["incidents"]:
            if row["scenario_id"] in ("WAN_LOSS","CPU_SATURATION"):
                selected[row["scenario_id"]]=row["run_id"]
    history=historical_preview(list(selected.values()),240,graph(),runs.__getitem__)
    h=assess(history)["analyst"]["hypotheses"]
    if len(h)!=1 or h[0]["temporal_order"]!="DEPENDENCY_OBSERVED_FIRST" or history["verified_evidence_count"]!=8:
        raise ValueError("unexpected campaign fixture")
    context=prepare(history,ledger.clock)
    candidates=context["candidates"]
    if len(candidates)!=1 or not candidates[0]["reference_context"]:raise ValueError("missing approved historical excerpts")
    return history,context

def qualify(out,context):
    c=context["candidates"][0]
    allowed={r["citation_id"] for r in c["reference_context"]}
    safe=(out["root_cause"]=="UNKNOWN" and out["confidence"] is None and out["causality_established"] is False
          and out["production_authorized"] is False and out["operational_decision"]=="DENY")
    calls=out["invocations"]
    citation_use=all(o is not None and o["candidate_id"]==c["candidate_id"] and o["evidence_ids"]==c["evidence_ids"]
        and bool(o["reference_ids"]) and set(o["reference_ids"])<=allowed for o in (out["analyst"],out["critic"]))
    return {"safe":safe,"reference_use":citation_use,"pass":safe and citation_use
        and out["state"]=="CANDIDATE_ONLY" and (out["critic"] or {}).get("verdict")=="AGREE_CANDIDATE"
        and len(calls)==2 and all(x["status"]=="VALIDATED" and x["usage_source"]=="provider_reported" for x in calls)}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--analyst-port",type=int,required=True)
    parser.add_argument("--critic-port",type=int,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    ports=(args.analyst_port,args.critic_port)
    providers=[config({"endpoint":"http://127.0.0.1:%d/v1/chat/completions"%port,"model":spec[0]}) for port,spec in zip(ports,SPECS)]
    if len(set(ports))!=2:raise ValueError("distinct endpoints")
    report={"classification":"E25_REAL_RAG_LEDGER_EXPERIMENT","result":"FAIL","source_sha":os.environ.get("E25_SOURCE_SHA"),
            "image":IMAGE,"production_authorized":False,"model_independence_attested":False,
            "scope":"synthetic campaign publication adapter; actual historical SQLite retrieval and actual local inference"}
    def save():
        args.report.parent.mkdir(parents=True,exist_ok=True)
        tmp=args.report.with_suffix(".tmp")
        tmp.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
        tmp.replace(args.report)
    save()
    try:
        report["models"]=[attest(port,*spec) for port,spec in zip(ports,SPECS)]
        save()
        root=args.report.parent/"ledger"
        root.mkdir(mode=0o700,exist_ok=False)
        ledger=InvocationLedger(root)
        history,context=seed(ledger)
        report["context_sha256"]=digest(context)
        report["wire_context_sha256"]=digest(wire_projection(context)[0])
        report["experiment_variant"]="V3_RESOURCE_BOUND_REFERENCE_RELEVANCE"
        report["rag_sha256"]=context["rag_sha256"]
        report["verified_evidence_count"]=history["verified_evidence_count"]
        report["approved_references"]=[{k:v for k,v in x.items() if k!="excerpt"} for x in context["candidates"][0]["reference_context"]]
        save()
        start=time.monotonic()
        persisted=ledger.execute_rag(history,*providers,timeout_seconds=120)
        out=persisted["assessment"]
        report["assessment"]=out
        report["quality"]=qualify(out,context)
        report["wall_ms"]=round((time.monotonic()-start)*1000,3)
        rid=persisted["review_id"]
        report["review_id"]=rid
        report["receipt_sha256"]=persisted["receipt_sha256"]
        reopened=InvocationLedger(root)
        stored=reopened.read(rid)
        summary=reopened.summary([rid])
        with tempfile.TemporaryDirectory() as restored:
            backup=InvocationLedger(restored)
            with closing(reopened.clock.connect()) as src,closing(backup.clock.connect()) as dest:src.backup(dest)
            restored_ok=backup.read(rid)==stored and backup.summary([rid])==summary and prepare(history,backup.clock)==context
        report["ledger"]={"reopen_and_backup_restore_match":restored_ok,"summary":summary,
            "invocations_match":stored["record"]["invocations"]==out["invocations"] and stored["receipt_sha256"]==persisted["receipt_sha256"],
            "context_match":stored["record"]["context_sha256"]==digest(context)==out["context_sha256"]}
        report["model_digests_unchanged"]=[attest(port,*spec) for port,spec in zip(ports,SPECS)]==report["models"]
        if report["quality"]["pass"] and restored_ok and report["ledger"]["invocations_match"] and report["ledger"]["context_match"] and report["model_digests_unchanged"]:
            report["result"]="PASS"
    except Exception as exc:
        report["error_class"]=type(exc).__name__
    finally:
        save()
        print(json.dumps(report,sort_keys=True))
    return 0 if report["result"]=="PASS" else 1

if __name__=="__main__":sys.exit(main())
