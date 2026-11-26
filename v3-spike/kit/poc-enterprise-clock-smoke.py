"""Exercise E2 against the real isolated GAMMA launcher before and after restart."""
import json
import re
import sys
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def smoke(origin, restart):
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin) or int(origin.rsplit(":",1)[1]) in (7770,7777,7790):
        raise ValueError("isolated origin required")
    opener=build_opener(ProxyHandler({}),NoRedirect())
    def call(path,data=None):
        req=Request(origin+path,data=None if data is None else json.dumps(data).encode(),
                    headers={"Origin":origin,"Content-Type":"application/json"})
        with opener.open(req,timeout=30) as response:
            return json.load(response)
    status=lambda:call("/api/v1/enterprise-clock")
    advance=lambda n:call("/api/v1/enterprise-clock/advance",{"expected_tick":n})
    capture=lambda n:call("/api/v1/enterprise-clock/capture",{"expected_tick":n})
    technical=lambda n:call("/api/v1/enterprise-clock/capture-technical",{"expected_tick":n})
    activity=lambda:call("/api/v1/enterprise-activity")
    campaign=lambda n:call("/api/v1/enterprise-clock/capture-scenarios",{"expected_tick":n})
    catalog=call("/api/v1/enterprise-scenarios")
    assert len(catalog["scenarios"])==16 and len({x["family"] for x in catalog["scenarios"]})==7
    by_id={x["scenario_id"]:x for x in catalog["scenarios"]}
    initial=status()
    initial_episodes=call("/api/v1/enterprise-episodes")
    initial_activity=activity()
    assert initial["current_tick"]==(4 if restart else 0)
    assert initial["pending"] is False and initial["production_authorized"] is False
    first=initial["recent"][2]["publication"]["run_id"] if restart else None
    old_capture=initial["recent"][2]["measured_capture"] if restart else None
    old_technical=initial["recent"][2]["technical_capture"] if restart else None
    for n in (range(5,9) if restart else range(1,5)):
        step=advance(n)
        assert step==advance(n) and step["tick"]==n
        assert step["measurement_kind"]=="MODEL_GENERATED"
        assert step["production_authorized"] is False and step["operational_decision"]=="DENY"
        reports=call("/api/v1/enterprise-case-knowledge")
        assert reports["total_documents"]==2*(n-1)
        assert all(d["valid_from_tick"]<=n and d["source"]["logical_tick"]==d["valid_from_tick"]-1 and not d["observed_evidence"] for d in reports["documents"])
        diverse=campaign(n)
        assert diverse==campaign(n) and diverse["state"]=="PUBLISHED" and len(diverse["incidents"])==2
        for item in diverse["incidents"]:
            ctx_case=call("/api/v1/enterprise-context?run_id="+item["run_id"])
            definition=by_id[item["scenario_id"]]
            assert ctx_case["root"]==definition["resource"] and not ctx_case["observed_outage_established"]
            assert ctx_case["document_history"]["logical_tick"]==n
            assert ctx_case["document_references"]
            assert all(d["source"]["run_id"]!=item["run_id"] for d in ctx_case["case_retrieval"]["citations"])
            combined_case=call("/api/v1/incident-context/dynamic?run_id="+item["run_id"])
            assert combined_case["copilot"]["enterprise_document_retrieval"]["case_retrieval"]==ctx_case["case_retrieval"]
            assert {x["evidence_id"]:x["payload_hash"] for x in ctx_case["timeline"]}=={x["evidence_id"]:x["payload_hash"] for x in item["evidence"]}
            meta=[x["scenario"] for x in ctx_case["timeline"]]
            assert {m["scenario_id"] for m in meta}=={item["scenario_id"]}
            assert all(m["classification"]=="MODEL_GENERATED" and m["metric"]==definition["metric"] and m["unit"]==definition["unit"] for m in meta)
            assert {m["phase"]:m["value"] for m in meta if m["phase"] in ("baseline","incident")}=={"baseline":definition["baseline"],"incident":definition["incident"]}
            if definition["family"]=="endpoint":
                assert ctx_case["exposure_semantics"]=="INDIVIDUAL_ACCESS_ONLY"
                assert len(ctx_case["reported_user_ids"])==1 and len(ctx_case["potential_exposure"]["users"])==1
        if n%4==3:
            pub=step["publication"]
            assert pub["state"]=="PUBLISHED" and len(pub["evidence"])==4
            if restart: assert pub["run_id"]!=first
            else: first=pub["run_id"]
            ctx=call("/api/v1/enterprise-context?run_id="+pub["run_id"])
            assert ctx["reported_user_ids"]==["NODE-CI-ENT-USER-FIN-01"]
            assert {x["evidence_id"]:x["payload_hash"] for x in ctx["timeline"]}=={x["evidence_id"]:x["payload_hash"] for x in pub["evidence"]}
            assert all(x["source"].endswith(":enterprise-clock-e2") for x in ctx["timeline"])
            assert ctx["causality_established"] is False
            assert ctx["document_history"]["state"]=="HISTORICAL_LOGICAL_VERSION"
            assert ctx["document_history"]["logical_tick"]==n
            pay=next(d for d in ctx["document_references"] if d["id"]=="ENT-DOC-001")
            assert pay["version"]==(3 if restart else 2) and pay["valid_from_tick"]==n-1
            assert all(not d["observed_evidence"] for d in ctx["document_references"])
            combined=call("/api/v1/incident-context/dynamic?run_id="+pub["run_id"])
            assert combined["enterprise_context"]==ctx
            assert combined["copilot"]["enterprise_document_retrieval"]["citations"]==ctx["document_references"]
            assert combined["copilot"]["enterprise_document_retrieval"]["document_history"]==ctx["document_history"]
            lifecycle=ctx["lifecycle_references"]
            assert len(lifecycle)==(4 if restart else 1)
            assert all(d["valid_from_tick"]<n and d["observed_evidence"] is False for d in lifecycle)
            assert combined["copilot"]["enterprise_document_retrieval"]["lifecycle_citations"]==lifecycle
            assert combined["copilot"]["enterprise_document_retrieval"]["hybrid_retrieval"]==ctx["hybrid_retrieval"]
            search=lambda run,q:call("/api/v1/enterprise-search",{"run_id":run,"query":q})
            ranked=search(pub["run_id"],"Payments latency runbook")
            assert ranked["logical_tick"]==n and ranked["state"]=="MATCHED"
            assert ranked["citations"][0]["id"]=="ENT-DOC-001" and ranked["citations"][0]["version"]==(3 if restart else 2)
            assert all(d["valid_from_tick"]<=n and not d["observed_evidence"] for d in ranked["citations"])
            assert search(pub["run_id"],"zzzzzzzz")["state"]=="NO_MATCH"
            if restart:
                historical=search(first,"Payments latency runbook")
                assert historical["logical_tick"]==3 and historical["citations"][0]["version"]==2
                recovery=search(pub["run_id"],"recovery remediation measured")
                assert recovery["citations"][0]["kind"]=="RECOVERY" and recovery["citations"][0]["source"]["run_id"]==first
            print(json.dumps({"classification":"E9_HYBRID_RETRIEVAL","result":"PASS","tick":n,"top_document":ranked["citations"][0]["id"],"version":ranked["citations"][0]["version"],"bm25":ranked["citations"][0]["bm25_score"],"cosine":ranked["citations"][0]["vector_cosine"],"no_match":True,"production_authorized":False}),file=sys.stderr)
            if restart:
                assert {d["source"]["run_id"] for d in lifecycle if d["kind"]!="CHANGE"}=={first}
                prior=call("/api/v1/enterprise-context?run_id="+first)
                refs={x["evidence_id"]:x["payload_hash"] for x in prior["timeline"]}
                for d in lifecycle:
                    if d["kind"]!="CHANGE":
                        assert {x["evidence_id"]:x["payload_hash"] for x in d["source"]["evidence_refs"]}==refs
            measured=capture(n)
            assert measured==capture(n) and measured["state"]=="PUBLISHED"
            assert re.fullmatch(r"[a-f0-9]{64}",measured["batch_sha256"])
            assert {x["resource"] for x in measured["incidents"]}=={"NODE-CI-ROOT","NODE-CI-ENT-ASSET-LYO"}
            assert len({x["run_id"] for x in measured["incidents"]}|{pub["run_id"]})==3
            for item in measured["incidents"]:
                observed=call("/api/v1/enterprise-context?run_id="+item["run_id"])
                assert observed["root"]==item["resource"]
                if item["resource"]=="NODE-CI-ENT-ASSET-LYO":
                    hr=search(item["run_id"],"HR portal")
                    assert [d["id"] for d in hr["citations"]]==["ENT-DOC-004"]
                    assert search(item["run_id"],"Payments latency runbook")["state"]=="NO_MATCH"
                assert len([x for x in observed["timeline"] if x.get("measurement",{}).get("classification")=="MEASURED_SYNTHETIC_LAB"])==2
            if restart:
                assert not {x["run_id"] for x in measured["incidents"]}&{x["run_id"] for x in old_capture["incidents"]}
            assert status()["latest"]["measured_capture"]==measured
            tech=technical(n)
            assert tech==technical(n) and tech["state"]=="PUBLISHED"
            assert re.fullmatch(r"[a-f0-9]{64}",tech["batch_sha256"])
            expected={"LINUX-PAR":("ENT-DOC-006",{"process_cpu_ms","process_peak_rss_kib"}),
                      "STORAGE-PAR":("ENT-DOC-008",{"fsync_write_ms","fsync_write_bytes"}),
                      "DB-PAY":("ENT-DOC-007",{"sqlite_query_ms","sqlite_result_rows"}),
                      "NET-PAR":("ENT-DOC-005",{"loopback_rtt_ms","loopback_echo_bytes"})}
            assert {x["resource"] for x in tech["incidents"]}=={"NODE-CI-ENT-"+x for x in expected}
            measurements=[]
            for item in tech["incidents"]:
                doc,metrics=expected[item["resource"].removeprefix("NODE-CI-ENT-")]
                combined=call("/api/v1/incident-context/dynamic?run_id="+item["run_id"])
                observed=combined["enterprise_context"]
                assert observed["root"]==item["resource"] and not observed["observed_outage_established"]
                assert {x["evidence_id"]:x["payload_hash"] for x in observed["timeline"]}=={x["evidence_id"]:x["payload_hash"] for x in item["evidence"]}
                values=[x["telemetry"] for x in observed["timeline"] if "telemetry" in x]
                assert {x["metric"] for x in values}==metrics and len(values)==2
                assert all(x["classification"]=="MEASURED_ISOLATED_WORKLOAD" for x in values)
                assert doc in {x["id"] for x in observed["document_references"]}
                assert combined["copilot"]["root_cause"]=="UNKNOWN" and combined["copilot"]["operational_decision"]=="DENY"
                measurements.append({"resource":item["resource"],"run_id":item["run_id"],"metrics":values})
            if restart:
                assert not {x["run_id"] for x in tech["incidents"]}&{x["run_id"] for x in old_technical["incidents"]}
            assert status()["latest"]["technical_capture"]==tech
            print(json.dumps({"classification":"E5_TECHNICAL_CAPTURE","tick":n,"result":"PASS","measurements":measurements,"production_authorized":False}),file=sys.stderr)
        else:
            assert step["publication"]["state"]=="MODEL_ONLY"
    recent=activity()
    assert recent["current_tick"]==(8 if restart else 4)
    assert not recent["unavailable_pre_e6_ticks"]
    records=recent["records"]
    assert len(records)==(24 if restart else 12)
    assert len({r["activity_id"] for r in records})==len(records)
    assert sum(r["disposition"]=="INCIDENT_LINKED" for r in records)==(2 if restart else 1)
    assert sum(r["disposition"]=="ALERT_ONLY" for r in records)==(2 if restart else 1)
    assert sum(r["disposition"]=="OBSERVATION_ONLY" for r in records)==(20 if restart else 10)
    assert all(r["classification"]=="MODEL_GENERATED" and not r["observed_outage_established"] for r in records)
    assert all(r["run_id"] is None for r in records if r["disposition"]!="INCIDENT_LINKED")
    if restart: assert records[:12]==initial_activity["records"]
    for r in records:
        if r["run_id"]:
            ctx=call("/api/v1/enterprise-context?run_id="+r["run_id"])
            assert ctx["incident_id"]==r["incident_id"] and ctx["root"]==r["resource"]
    print(json.dumps({"classification":"E6_ACTIVITY_JOURNAL","result":"PASS","ticks":recent["current_tick"],"activity_records":len(records),"signals":len(records)*3,"alerts_only":sum(r["disposition"]=="ALERT_ONLY" for r in records),"linked_incidents":sum(r["disposition"]=="INCIDENT_LINKED" for r in records),"production_authorized":False}),file=sys.stderr)
    end=status()
    cases=[r for x in end["recent"] for r in x["scenario_capture"]["incidents"]]
    episode_data=call("/api/v1/enterprise-episodes")
    assert len(episode_data["records"])==end["current_tick"]*4 and not episode_data["unavailable_pre_e12_ticks"]
    assert len({r["episode_id"] for r in episode_data["records"]})==4
    assert all(not r["causality_established"] and not r["observed_recovery_established"] for r in episode_data["records"])
    if restart: assert episode_data["records"][:16]==initial_episodes["records"]
    refs={r["run_id"]:r for r in cases}
    related=[ref for r in episode_data["records"] for ref in r["related_cases"]]
    assert len(related)==(8 if restart else 6)
    for ref in related:
        assert ref["evidence_refs"]==refs[ref["run_id"]]["evidence"]
        ctx=call("/api/v1/enterprise-context?run_id="+ref["run_id"])
        assert ctx["root"]==ref["resource"] and ctx["causality_established"] is False
    if restart:
        lyon=[r for r in episode_data["records"] if r["scenario"]=="LYON_INTERMITTENT"]
        assert [r["tick"] for r in lyon if r["phase"]=="RECURRENCE"]==[4,6]
    print(json.dumps({"classification":"E12_EPISODES","result":"PASS","tick":end["current_tick"],"episodes":4,"stages":len(episode_data["records"]),"related_cases":len(related),"production_authorized":False}),file=sys.stderr)
    reports=call("/api/v1/enterprise-case-knowledge")
    assert reports["total_documents"]==len(cases)-2
    by_run={r["run_id"]:r for r in cases}
    for doc in reports["documents"]:
        source=doc["source"]
        assert source["evidence_refs"]==by_run[source["run_id"]]["evidence"]
        assert doc["scenario_id"]==by_run[source["run_id"]]["scenario_id"]
        old_context=call("/api/v1/enterprise-context?run_id="+source["run_id"])
        assert doc["id"] not in {d["id"] for d in old_context["case_retrieval"]["citations"]}
    print(json.dumps({"classification":"E11_CASE_KNOWLEDGE","result":"PASS","tick":end["current_tick"],"documents":reports["total_documents"],"families":len({d["family"] for d in reports["documents"]}),"production_authorized":False}),file=sys.stderr)
    assert len(cases)==(16 if restart else 8) and len({r["run_id"] for r in cases})==len(cases)
    assert len({r["scenario_id"] for r in cases})==len(cases)
    if restart:
        assert cases[:8]==[r for x in initial["recent"] for r in x["scenario_capture"]["incidents"]]
        for r in cases[:8]:
            assert call("/api/v1/enterprise-context?run_id="+r["run_id"])["root"]==r["resource"]
    print(json.dumps({"classification":"E10_DIVERSE_CAMPAIGN","result":"PASS","ticks":end["current_tick"],"scenarios":len(cases),"evidence_count":len(cases)*4,"runs":cases,"production_authorized":False}),file=sys.stderr)
    assert end["current_tick"]==(8 if restart else 4)
    assert [x["phase"] for x in end["recent"]]==["NOMINAL","CHANGE","DEGRADED","MODEL_RECOVERY"]*(2 if restart else 1)
    if restart:
        old=call("/api/v1/enterprise-context?run_id="+first)
        assert old["run_id"]==first and len(old["timeline"])==4
        assert old["document_history"]["logical_tick"]==3
        old_pay=next(d for d in old["document_references"] if d["id"]=="ENT-DOC-001")
        assert old_pay["version"]==2 and old_pay["sha256"]!=pay["sha256"]
        assert end["recent"][2]["measured_capture"]==old_capture
        assert end["recent"][2]["technical_capture"]==old_technical
        for item in old_technical["incidents"]:
            assert call("/api/v1/enterprise-context?run_id="+item["run_id"])["root"]==item["resource"]
        for item in old_capture["incidents"]:
            assert call("/api/v1/enterprise-context?run_id="+item["run_id"])["root"]==item["resource"]
    knowledge=call("/api/v1/enterprise-knowledge")
    assert len(knowledge["documents"])==(6 if restart else 3)
    assert all(not d["observed_evidence"] for d in knowledge["documents"])
    if restart:
        assert [d["kind"] for d in old["lifecycle_references"]]==["CHANGE"]
    print(json.dumps({"classification":"E8_LIFECYCLE_KNOWLEDGE","result":"PASS","current_tick":end["current_tick"],"documents":len(knowledge["documents"]),"historical_citations":len(lifecycle),"production_authorized":False}),file=sys.stderr)
    catalog=call("/api/v1/enterprise-corpus")
    current=next(d for d in catalog["documents"] if d["id"]=="ENT-DOC-001")
    assert len(catalog["documents"])==10 and current["version"]==(3 if restart else 2)
    print(json.dumps({"classification":"E7_HISTORICAL_CORPUS","result":"PASS","current_tick":end["current_tick"],"documents":10,"current_payments_version":current["version"],"historical_tick3_version":old_pay["version"] if restart else pay["version"],"current_document_sha256":current["sha256"],"historical_document_sha256":old_pay["sha256"] if restart else pay["sha256"],"production_authorized":False}),file=sys.stderr)
    try: advance(end["current_tick"]+2)
    except HTTPError as exc: assert exc.code==503
    else: raise AssertionError("skipped tick accepted")
    print(json.dumps({"classification":"E2_CLOCK_RESTART" if restart else "E2_CLOCK_FIRST_CYCLE","result":"PASS","current_tick":end["current_tick"],"published_run_ids":[x["publication"]["run_id"] for x in end["recent"] if x["publication"]["state"]=="PUBLISHED"],"measured_run_ids":[item["run_id"] for x in end["recent"] for item in x.get("measured_capture",{}).get("incidents",[])],"technical_run_ids":[item["run_id"] for x in end["recent"] for item in x.get("technical_capture",{}).get("incidents",[])],"scenario_runs":cases,"production_authorized":False}))

if __name__=="__main__":
    if len(sys.argv) not in (2,3) or (len(sys.argv)==3 and sys.argv[2]!="--restart"):
        raise SystemExit("usage: poc-enterprise-clock-smoke.py ORIGIN [--restart]")
    smoke(sys.argv[1],len(sys.argv)==3)
