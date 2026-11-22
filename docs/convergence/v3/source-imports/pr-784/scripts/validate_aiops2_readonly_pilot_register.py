"""Fail-closed validation of read-only pilot register metadata."""
import argparse, json, re, sys
from pathlib import Path
SCHEMA='aiops2.readonly-pilot-evidence-register.v1'
SOURCES={'oidc':['issuer','audience','jwks_key_id','revocation_check','mfa_assurance'],'grafana':['rule_uid','dashboard_uid','observed_at_utc','service_identity','tenant_scope','response_sha256'],'n8n':['workflow_id','execution_id','execution_status','started_at_utc','finished_at_utc','workflow_version','read_only_existing_execution','response_sha256'],'glpi_cmdb':['instance_id','entity_id','ticket_id','ci_id','human_actor_subject','native_acl_verified','xref_verified','response_sha256'],'core_temporal':['core_run_id','workflow_id','start_intent_present','inspection_read_only'],'policy_hitl':['policy_version','decision','human_actor_subject','approval_scope','audit_event_ref'],'independent_postcheck':['source_independent_from_action','observed_at_utc','expected_state','observed_state','verifier_identity','response_sha256']}
NEGATIVE=['cross_tenant_zero_upstream_calls','cross_entity_zero_upstream_calls','revoked_actor_zero_upstream_calls','replayed_token_zero_upstream_calls','glpi_acl_denial_zero_upstream_reads','temporal_inspection_no_start_or_restart','n8n_existing_execution_no_replay']
def validate(d):
 e=[]
 if not isinstance(d,dict) or d.get('schema')!=SCHEMA:return ['invalid_schema']
 if d.get('live_actions_authorized') is not False:e.append('live_actions_must_remain_false')
 env=d.get('environment') or {}
 if not isinstance(env,dict):return ['environment_invalid']
 for k in ['name','owner','created_at_utc','expires_at_utc','destruction_record']:
  if not env.get(k) or env[k]=='UNASSIGNED':e.append('environment_'+k+'_missing')
 if env.get('is_ephemeral') is not True:e.append('environment_not_ephemeral')
 if not isinstance(d.get('git_revision'),str) or not re.fullmatch('[0-9a-f]{40}',d['git_revision']):e.append('git_revision_invalid')
 sources=d.get('sources') or {}
 if not isinstance(sources,dict):return ['source_set_invalid']
 if set(sources)!=set(SOURCES):e.append('source_set_invalid')
 for name,fields in SOURCES.items():
  s=sources.get(name,{})
  if not isinstance(s,dict):e.append(name+'_invalid');continue
  if s.get('status')!='VERIFIED':e.append(name+'_not_verified');continue
  for f in fields:
   if s.get(f) in (None,'','UNKNOWN'):e.append(name+'_'+f+'_missing')
  for f in ('revocation_check','mfa_assurance','native_acl_verified','xref_verified','read_only_existing_execution','start_intent_present','inspection_read_only','source_independent_from_action'):
   if f in fields and s.get(f) is not True:e.append(name+'_'+f+'_must_be_true')
  refs=s.get('evidence_refs')
  if not isinstance(refs,list) or not refs or any(not isinstance(x,str) or not x.strip() for x in refs):e.append(name+'_evidence_refs_missing')
  if 'response_sha256' in s and s.get('response_sha256') is not None and not re.fullmatch('[0-9a-f]{64}',str(s['response_sha256'])):e.append(name+'_sha256_invalid')
 if isinstance(sources.get('core_temporal'),dict) and sources['core_temporal'].get('status')=='VERIFIED':
  t=sources['core_temporal']
  if t.get('inspection_read_only') is not True or t.get('start_intent_present') is not True or t.get('execution_outcome')!='UNKNOWN':e.append('temporal_read_only_contract_invalid')
 if isinstance(sources.get('n8n'),dict) and sources['n8n'].get('status')=='VERIFIED' and sources['n8n'].get('read_only_existing_execution') is not True:e.append('n8n_replay_forbidden')
 if isinstance(sources.get('glpi_cmdb'),dict) and sources['glpi_cmdb'].get('status')=='VERIFIED' and (sources['glpi_cmdb'].get('native_acl_verified') is not True or sources['glpi_cmdb'].get('xref_verified') is not True):e.append('glpi_acl_xref_required')
 if isinstance(sources.get('independent_postcheck'),dict) and sources['independent_postcheck'].get('status')=='VERIFIED' and sources['independent_postcheck'].get('source_independent_from_action') is not True:e.append('postcheck_not_independent')
 tests=d.get('negative_tests') or {}
 if not isinstance(tests,dict):return sorted(set(e+['negative_test_set_invalid']))
 if set(tests)!=set(NEGATIVE):e.append('negative_test_set_invalid')
 else:
  for k in NEGATIVE:
   if tests[k]!='PASS':e.append(k+'_not_passed')
 expected='GO_READ_ONLY_PILOT' if not e else 'BLOCKED'
 if d.get('decision')!=expected:e.append('decision_mismatch')
 return sorted(set(e))
def main():
 p=argparse.ArgumentParser();p.add_argument('register',type=Path);a=p.parse_args()
 try:
  d=json.loads(a.register.read_text());e=validate(d);out={'valid':not e,'decision':d.get('decision','BLOCKED'),'errors':e,'live_actions_authorized':False}
 except (OSError,ValueError,TypeError) as x:out={'valid':False,'decision':'BLOCKED','errors':['input_invalid:'+type(x).__name__],'live_actions_authorized':False}
 print(json.dumps(out,indent=2,sort_keys=True));return 0 if out['valid'] else 1
if __name__=='__main__':raise SystemExit(main())
