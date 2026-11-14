import copy, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_aiops2_readonly_pilot_register import validate
TEMPLATE=ROOT/'docs/ops/AIOPS2-READONLY-PILOT-EVIDENCE-REGISTER.template.json'
def test_template_is_blocked_and_never_authorizes_live():
 d=json.loads(TEMPLATE.read_text());errors=validate(d)
 assert errors and 'oidc_not_verified' in errors
 assert d['live_actions_authorized'] is False
 assert d['decision']=='BLOCKED'
def test_unknown_sources_cannot_be_promoted_by_decision_field():
 d=json.loads(TEMPLATE.read_text());d['decision']='GO_READ_ONLY_PILOT'
 assert 'decision_mismatch' in validate(d)
def test_live_true_is_always_rejected():
 d=json.loads(TEMPLATE.read_text());d['live_actions_authorized']=True
 assert 'live_actions_must_remain_false' in validate(d)
def test_verified_glpi_requires_native_acl_and_xref():
 d=json.loads(TEMPLATE.read_text());s=d['sources']['glpi_cmdb'];s.update(status='VERIFIED',instance_id='i',entity_id='e',ticket_id='t',ci_id='ci',human_actor_subject='sub',native_acl_verified=False,xref_verified=True,response_sha256='a'*64,evidence_refs=['evidence/glpi.json'])
 assert 'glpi_acl_xref_required' in validate(d)
def test_verified_postcheck_must_be_independent():
 d=json.loads(TEMPLATE.read_text());s=d['sources']['independent_postcheck'];s.update(status='VERIFIED',source_independent_from_action=False,observed_at_utc='2026-11-14T12:00:00Z',expected_state='healthy',observed_state='healthy',verifier_identity='verifier',response_sha256='b'*64,evidence_refs=['evidence/postcheck.json'])
 assert 'postcheck_not_independent' in validate(d)
def test_negative_tests_must_all_pass():
 d=json.loads(TEMPLATE.read_text());d['negative_tests']['cross_tenant_zero_upstream_calls']='FAIL'
 assert 'cross_tenant_zero_upstream_calls_not_passed' in validate(d)
