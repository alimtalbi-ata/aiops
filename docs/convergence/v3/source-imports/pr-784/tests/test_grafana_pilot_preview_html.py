import json, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from portal.grafana_pilot_preview_html import render_grafana_pilot_preview_html
from portal.grafana_pilot_preview import preview_grafana_pilot_evidence
from portal.grafana_readonly_evidence import collect_grafana_alert_readonly

def preview():
 register=json.loads((ROOT/'docs/ops/AIOPS2-READONLY-PILOT-EVIDENCE-REGISTER.template.json').read_text())
 evidence=collect_grafana_alert_readonly(fetch_alert=lambda r,t:{'rule_uid':r,'tenant_id':t,'dashboard_uid':'san-ops','state':'firing','observed_at_utc':'2026-11-14T11:59:00Z'},rule_uid='san-p1',tenant_id='acme-test',service_identity='grafana-reader',max_age_seconds=300,now_utc='2026-11-14T12:00:00Z')
 return preview_grafana_pilot_evidence(register,evidence)

def test_customer_preview_is_readonly_and_explicitly_unattested():
 html=render_grafana_pilot_preview_html(preview())
 for marker in ('SAN → Payments','san-p1','acme-test','UNKNOWN / BLOCKED','NO-GO','Analyst/Critic','postcheck indépendant','État candidat','firing'):
  assert marker in html
 assert '<script' not in html and '<form' not in html

def test_untrusted_field_is_escaped():
 p=preview();p['register']['sources']['grafana']['rule_uid']='<img src=x onerror=alert(1)>'
 html=render_grafana_pilot_preview_html(p)
 assert '&lt;img' in html and '<img' not in html

@pytest.mark.parametrize('field,value', [('qualification','VERIFIED'),('runtime_attested',True),('live_actions_authorized',True)])
def test_forged_attestation_is_rejected(field,value):
 p=preview();p[field]=value
 with pytest.raises(ValueError,match='grafana_pilot_preview_unqualified'):
  render_grafana_pilot_preview_html(p)

def test_forged_register_verification_is_rejected():
 p=preview();p['register']['sources']['grafana']['status']='VERIFIED'
 with pytest.raises(ValueError,match='grafana_pilot_evidence_not_attested'):
  render_grafana_pilot_preview_html(p)

def test_forged_scenario_hash_is_rejected():
 p=preview()
 p['synthetic_scenario']={'incident_id':'SAN','business_impact_incident_id':'PAYMENTS','source_sha256':'not-a-hash','qualification':'UNKNOWN'}
 with pytest.raises(ValueError,match='grafana_pilot_scenario_unqualified'):
  render_grafana_pilot_preview_html(p)

def test_scenario_html_escapes_untrusted_identifiers():
 p=preview()
 p['synthetic_scenario']={'incident_id':'<script>alert(1)</script>','business_impact_incident_id':'PAYMENTS','source_sha256':'a'*64,'qualification':'UNKNOWN'}
 html=render_grafana_pilot_preview_html(p)
 assert '&lt;script&gt;' in html and '<script>' not in html
