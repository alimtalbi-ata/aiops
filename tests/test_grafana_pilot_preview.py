import copy, json, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
sys.path.insert(0,str(ROOT/'scripts'))
from portal.grafana_pilot_preview import preview_grafana_pilot_evidence
from portal.grafana_readonly_evidence import collect_grafana_alert_readonly
from validate_aiops2_readonly_pilot_register import validate
TEMPLATE=ROOT/'docs/ops/AIOPS2-READONLY-PILOT-EVIDENCE-REGISTER.template.json'
NOW='2026-11-14T12:00:00Z'
def fixture():
 return json.loads(TEMPLATE.read_text())
def projection():
 return collect_grafana_alert_readonly(fetch_alert=lambda rule,tenant:{'rule_uid':rule,'tenant_id':tenant,'dashboard_uid':'san-ops','state':'firing','observed_at_utc':'2026-11-14T11:59:00Z'},rule_uid='san-p1',tenant_id='acme-test',service_identity='grafana-reader',max_age_seconds=300,now_utc=NOW)
def test_business_preview_shows_alert_but_remains_blocked():
 register=fixture(); original=copy.deepcopy(register)
 preview=preview_grafana_pilot_evidence(register,projection())
 assert register==original
 assert preview['qualification']=='UNKNOWN'
 assert preview['runtime_attested'] is False
 assert preview['live_actions_authorized'] is False
 assert preview['register']['decision']=='BLOCKED'
 assert preview['register']['sources']['grafana']['status']=='UNKNOWN'
 assert preview['register']['sources']['grafana']['rule_uid']=='san-p1'
 assert preview['register']['sources']['grafana']['alert_state']=='firing'
 assert preview['register']['sources']['grafana']['tenant_scope']=='acme-test'
 assert validate(preview['register'])
@pytest.mark.parametrize('field,value', [('status','VERIFIED'),('runtime_attested',True),('native_tenant_acl_verified',True),('live_actions_authorized',True)])
def test_forged_attestation_is_rejected(field,value):
 p=projection();p[field]=value
 with pytest.raises(ValueError,match='pilot_preview_attestation_boundary_violation'):
  preview_grafana_pilot_evidence(fixture(),p)
def test_existing_verified_register_cannot_be_overwritten():
 r=fixture();r['sources']['grafana']['status']='VERIFIED'
 with pytest.raises(ValueError,match='pilot_preview_existing_source_must_be_unknown'):
  preview_grafana_pilot_evidence(r,projection())
def test_live_register_is_rejected():
 r=fixture();r['live_actions_authorized']=True
 with pytest.raises(ValueError,match='pilot_preview_live_authorization_forbidden'):
  preview_grafana_pilot_evidence(r,projection())

def test_invalid_candidate_state_is_rejected():
 p=projection();p['alert_state']='resolved_and_verified'
 with pytest.raises(ValueError,match='pilot_preview_alert_state_invalid'):
  preview_grafana_pilot_evidence(fixture(),p)
