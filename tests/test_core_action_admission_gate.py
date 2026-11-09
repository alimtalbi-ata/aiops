from dataclasses import replace
from app.core.core_lineage_gate import Receipt
from app.core.core_action_admission_gate import ActionProof, Admission, admit

R = Receipt('tenant-a','INC-1','RUN-1','DEMO','EVT-1',('EVID-1',),
            'ANA-1','CRIT-1','POL-1','ALLOW','ACT-1','RUN-1','RUN-1',
            'GLPI','147',True,'RUN-1',True)
P = ActionProof('tenant-a','RUN-1','ACT-1','sha256:abc','ALLOW','APPROVED',
                'ACT-1','sha256:abc','worker-a','worker-a','42','42',
                'RECONCILED_SAFE_TO_RESUME',True)

def test_complete_is_only_revalidation():
    assert admit(R,P) == Admission.ELIGIBLE_FOR_REVALIDATION

def test_live_denied():
    assert admit(replace(R,mode='LIVE'),P) == Admission.DENIED

def test_policy_denials():
    for state in ('DENY','STOP_AUTO'):
        assert admit(R,replace(P,policy_state=state)) == Admission.DENIED

def test_pending_hitl_needs_human():
    assert admit(R,replace(P,hitl_state='PENDING')) == Admission.NEEDS_HUMAN

def test_action_bound_hitl():
    assert admit(R,replace(P,hitl_action_id='ACT-OTHER')) == Admission.DENIED
    assert admit(R,replace(P,hitl_action_digest='sha256:other')) == Admission.DENIED

def test_fencing_and_owner_mismatch():
    assert admit(R,replace(P,observed_fencing_token='41')) == Admission.DENIED
    assert admit(R,replace(P,observed_owner_id='worker-b')) == Admission.DENIED

def test_temporal_uncertainty_never_passes():
    assert admit(R,replace(P,temporal_reconciled=False)) == Admission.UNKNOWN
    assert admit(R,replace(P,temporal_state='RUNNING')) == Admission.UNKNOWN

def test_missing_or_malformed_attestations():
    assert admit(R,None) == Admission.UNKNOWN
    assert admit(R,replace(P,fencing_token=[])) == Admission.UNKNOWN

def test_lineage_and_mode_mismatch():
    assert admit(replace(R,itsm_readback_verified=False),P) == Admission.UNKNOWN
    assert admit(replace(R,mode='OTHER'),P) == Admission.UNKNOWN
    assert admit(replace(R,execution_expected=False,action_id=None,temporal_run_id=None,worker_run_id=None),P) == Admission.UNKNOWN

def test_input_not_mutated():
    before=(R,P)
    admit(R,P)
    assert (R,P)==before
