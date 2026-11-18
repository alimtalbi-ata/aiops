"""INT08C offline probes: actual baseline workflow AST and actual collectors, no server."""
import ast, asyncio, datetime
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
import pytest
from test_int07_offline_collector import CollectorTests
from portal.acme_runtime_context import digest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"app/worker/main.py"
ARGS=dict(run_id="offline-run",mode="DEMO",scenario_id="ACME-SAN-PAYMENTS",version=0)

def loop(stop,status):
    src=ast.parse(SOURCE.read_text())
    stages=ast.literal_eval(next(n.value for n in src.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="STAGES" for t in n.targets)))
    cls=next(n for n in src.body if isinstance(n,ast.ClassDef) and n.name=="IncidentWorkflow")
    cls.decorator_list=[]
    for f in cls.body:
        if isinstance(f,ast.AsyncFunctionDef): f.decorator_list=[]
    calls=[]
    def start_run(): pass
    def execute_stage(): pass
    def finish_run(): pass
    async def invoke(fn,a,**kw):
        k=a.get("stage",fn.__name__); calls.append(k)
        assert kw["start_to_close_timeout"].total_seconds() in (30,60)
        if k==stop and status=="timeout": raise TimeoutError("injected")
        if k=="start_run": return {"version":1}
        if k=="finish_run": raise AssertionError("FINISH forbidden")
        return dict(run_id="foreign" if k==stop and status=="foreign" else a["run_id"],stage=k,status=status if k==stop and status!="foreign" else "PASS",version=a["version"]+1)
    ns=dict(workflow=SimpleNamespace(execute_activity=invoke),start_run=start_run,execute_stage=execute_stage,finish_run=finish_run,STAGES=stages,RETRY=object(),datetime=datetime)
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(SOURCE),"exec"),ns)
    return ns["IncidentWorkflow"](),calls,["start_run",*stages]

@pytest.mark.parametrize("stage,status",[("start_run","timeout"),("OBSERVE","timeout"),("DGX_CRITIC","BLOCKED"),("POLICY","BLOCKED"),("HITL","BLOCKED"),("REMEDIATE","FAIL"),("REMEDIATE","timeout"),("POLICY","foreign"),("VERIFY","BLOCKED")])
def test_actual_loop_stop(stage,status):
    wf,calls,order=loop(stage,status)
    if status=="BLOCKED": assert asyncio.run(wf.run(ARGS))["blocked_stage"]==stage
    else:
        with pytest.raises((ValueError,TimeoutError)): asyncio.run(wf.run(ARGS))
    assert calls==order[:order.index(stage)+1]
    assert "finish_run" not in calls

@pytest.mark.parametrize("case",["receipt","terminal_foreign","terminal_version","second","core_missing","twin_missing"])
def test_actual_collector_refusal(case):
    t=CollectorTests(); f,e=t.fixture(); second=None
    if case=="receipt": e["receipt"]["content"]["receipt_sha256"]="0"*64
    if case=="terminal_foreign": e["terminal"]["content"]["identity"]["tenant_id"]="FOREIGN"
    if case=="terminal_version": e["terminal"]["content"]["version"]=0
    if case=="second": second=deepcopy(e["terminal_readback"]); second["observed_at"]="2026-11-18T09:00:23Z"
    if case.endswith("_missing"): f.rows[case.split("_")[0]]=None
    for v in e.values(): v["content_sha256"]=digest(v["content"])
    result,calls=t.invoke(f,e,second)
    assert result["reason"]!="OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED"
    assert result["qualification"] in ("BLOCK","REJECT")

def test_design_preflight_no_authority():
    # Explicit design-only gate, never call workflow or transport.
    def preflight(mode,isolation):
        return mode=="DEMO" and isolation is True
    for mode,iso in [("LIVE",True),("SIMULATION",True),("DEMO",None),("DEMO",False),("DEMO",1)]:
        assert not preflight(mode,iso)
    # Positive preflight is not launch authority.
    assert preflight("DEMO",True)

def test_proposal_has_no_public_ports_or_prod_services():
    text=(ROOT/"docs/qualification/int08c/compose.proposed.yaml").read_text()
    assert "ports:" not in text and "container_name:" not in text
    assert all(x not in text for x in ("glpi:","n8n:","dgx:","build:"))
    assert text.count("internal: true")==5
