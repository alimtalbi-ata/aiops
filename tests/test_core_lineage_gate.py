from dataclasses import replace
from app.core.core_lineage_gate import Receipt, Verdict, evaluate

BASE = Receipt('tenant-a','INC-1','RUN-1','DEMO','EVT-1',('EVID-1',),
               'ANA-1','CRIT-1','POL-1','DENY',None,None,None,
               'GLPI','147',True,'RUN-1',False)

def test_blocked_end_to_end_readback_passes_without_execution():
    assert evaluate(BASE).verdict == Verdict.PASS

def test_missing_readback_unknown_not_pass():
    assert evaluate(replace(BASE, itsm_readback_verified=False)).verdict == Verdict.UNKNOWN

def test_missing_evidence_unknown():
    assert evaluate(replace(BASE,evidence_ids=())).verdict == Verdict.UNKNOWN

def test_portal_mismatch_fail():
    assert evaluate(replace(BASE,portal_run_id='RUN-OTHER')).verdict == Verdict.FAIL

def test_policy_denied_execution_fail():
    assert evaluate(replace(BASE,execution_expected=True)).verdict == Verdict.FAIL

def test_live_never_pass():
    assert evaluate(replace(BASE,mode='LIVE')).verdict == Verdict.FAIL

def test_unknown_policy_unknown():
    assert evaluate(replace(BASE,policy_state='UNKNOWN')).verdict == Verdict.UNKNOWN

def test_unexpected_worker_trace_fail():
    assert evaluate(replace(BASE,worker_run_id='RUN-1')).verdict == Verdict.FAIL

def test_allowed_execution_requires_temporal_worker_action():
    allowed=replace(BASE,policy_state='ALLOW',execution_expected=True)
    assert evaluate(allowed).verdict == Verdict.UNKNOWN
    assert evaluate(replace(allowed,action_id='ACT-1',temporal_run_id='RUN-1',worker_run_id='RUN-1')).verdict == Verdict.PASS

def test_different_external_adapter_without_engine_change():
    assert evaluate(replace(BASE,external_system='ServiceNow',external_ticket_id='INC000123')).verdict == Verdict.PASS

def test_wrong_input_type_unknown():
    assert evaluate({'run_id':'RUN-1'}).verdict == Verdict.UNKNOWN
