"""Test-only orchestration model, no runtime workflow changes or service calls."""
from copy import deepcopy
import pytest
from portal.acme_authority_readers import collect_prepared
from portal.acme_runtime_context import digest
from worker.acme_simulated_hitl import verify_no_effect_receipt
from worker.int06a_contract import IDENTITY, validate_postcheck
from test_int07_offline_collector import CollectorTests

def history_pair(prefix,final):
    # Proposed transport envelope, not a replacement for B business validators.
    return (prefix["phase"]=="PREFIX" and final["phase"]=="FINAL"
        and prefix["execution_id"]==final["execution_id"]
        and len(final["events"])>len(prefix["events"])
        and final["events"][:len(prefix["events"])]==prefix["events"]
        and digest(prefix)!=digest(final))

def model(f,e,*,mode="DEMO",second=None,prefix=None,final=None):
    trace=[]
    result=dict(trace=trace,worker_scheduled=0,finish_authorized=False,
                runtime_attested=False,resolution_authorized=False,final_consistent=False)
    if mode!="DEMO": return result
    readers={k:lambda k=k:deepcopy(f.rows[k]) for k in f.rows}
    b=collect_prepared(f.e,f.i,readers,f.policies,as_of_utc="2026-11-18T09:00:30Z",
                       source_registry={k:f.registry[k] for k in readers})
    trace.append(("admission",b["reason"]))
    if b["reason"]!="INJECTED_READBACKS_NOT_ATTESTED": return result
    # Hypothetical progression only; historical admission is not complete.
    trace.append(("hypothetical_worker",None))
    try:
        receipt=e["receipt"]["content"]
        if not verify_no_effect_receipt(receipt,{k:f.i[k] for k in IDENTITY}): return result
        p=validate_postcheck(intent=f.i,independently_read=e["independent"]["content"])
        if p!={"qualification":"CONTRACT_ONLY","runtime_attested":False,"finish_authorized":False}: return result
        if e["postcheck"]["content"]["verified"] is not True: return result
        if prefix['phase']!='PREFIX' or not prefix['events']: return result
    except (ValueError,TypeError,KeyError,AttributeError): return result
    trace.append(("hypothetical_preterminal",None))
    if not history_pair(prefix,final): return result
    q,_=CollectorTests().invoke(f,e,second)
    trace.append(("final",q["reason"]))
    result["final_consistent"]=q["reason"]=="OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED"
    return result

def fixture():
    f,e=CollectorTests().fixture()
    p=dict(phase="PREFIX",execution_id="offline-execution",events=[{"id":1}])
    q=dict(phase="FINAL",execution_id="offline-execution",events=[{"id":1},{"id":2}])
    return f,e,p,q

@pytest.mark.parametrize("case",["nominal","admission","live","receipt","postcheck","terminal_missing","terminal_foreign","second","history_changed","history_equal","history_foreign"])
def test_three_boundaries(case):
    f,e,p,q=fixture(); mode="DEMO"; second=None
    if case=="admission": f.rows["core"]=None
    if case=="live": mode="LIVE"
    if case=="receipt": e["receipt"]["content"]["receipt_sha256"]="0"*64
    if case=="postcheck": e["independent"]["content"]["postcheck_verified"]=False
    if case=="terminal_missing": del e["terminal"]
    if case=="terminal_foreign": e["terminal"]["content"]["identity"]["tenant_id"]="foreign"
    if case=="second": second=deepcopy(e["terminal_readback"]); second["observed_at"]="2026-11-18T09:00:23Z"
    if case=="history_changed": q["events"][0]["id"]=99
    if case=="history_equal": q["events"]=deepcopy(p["events"])
    if case=="history_foreign": q["execution_id"]="foreign"
    for v in e.values(): v["content_sha256"]=digest(v["content"])
    r=model(f,e,mode=mode,second=second,prefix=p,final=q)
    assert r["worker_scheduled"]==0
    assert r["finish_authorized"] is r["runtime_attested"] is r["resolution_authorized"] is False
    assert r["final_consistent"] is (case=="nominal")
    steps=[x[0] for x in r["trace"]]
    if case in ("admission","live"): assert "hypothetical_worker" not in steps
    if case in ("receipt","postcheck","history_changed","history_equal","history_foreign"): assert "final" not in steps

class Ledger:
    """Model only: atomic replacement of in-memory state, no Core implementation."""
    def __init__(self): self.state=(1,{},[])
    def transition(self,key,request,lost=False):
        version,records,outbox=self.state
        h=digest(request)
        if key in records:
            old,result=records[key]
            if h!=old: raise ValueError("conflict")
            return result
        if request["expected_version"]!=version: raise ValueError("CAS")
        result=version+1
        self.state=(result,{**records,key:(h,result)},[*outbox,key])
        if lost: raise TimeoutError("lost response after commit")
        return result

def test_lost_response_retry_model():
    l=Ledger(); request={"expected_version":1,"tenant":"ACME-TEST","run":"offline"}
    with pytest.raises(TimeoutError): l.transition("key",request,lost=True)
    assert l.transition("key",request)==2
    assert l.state[2]==["key"]
    with pytest.raises(ValueError,match="conflict"): l.transition("key",dict(request,run="other"))
    with pytest.raises(ValueError,match="CAS"): l.transition("other",request)
    assert l.state[0]==2 and l.state[2]==["key"]
