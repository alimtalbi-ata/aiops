"""Customer-facing Grafana preview route is synthetic, read-only and fail-closed."""
import os, sys
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))

def client():
 with patch.dict(os.environ,{'AIOPS_INTERNAL_TOKEN':'unit-test-only'}):
  from portal.main import app
 return TestClient(app)

def test_synthetic_grafana_preview_route_is_safe():
 response=client().get('/demo/acme-grafana-pilot-preview')
 assert response.status_code==200
 assert response.headers['cache-control']=='no-store'
 assert "default-src 'none'" in response.headers['content-security-policy']
 for marker in ('SAN → Payments','UNKNOWN / BLOCKED','LOCAL_SYNTHETIC_FIXTURE_NOT_AUTHENTICATED','NO-GO','acme-synthetic','État candidat','firing'):
  assert marker in response.text
 assert '<script' not in response.text

def test_synthetic_grafana_preview_fails_closed_when_register_missing():
 with patch('pathlib.Path.read_text',side_effect=OSError('no evidence template')):
  response=client().get('/demo/acme-grafana-pilot-preview')
 assert response.status_code==503
 assert response.json()['detail']=='synthetic_grafana_pilot_preview_unqualified'

def test_customer_can_navigate_both_synthetic_views_without_network():
 c=client()
 cockpit=c.get('/demo/acme-incident-cockpit')
 preview=c.get('/demo/acme-grafana-pilot-preview')
 assert cockpit.status_code==200 and preview.status_code==200
 assert "href='/demo/acme-grafana-pilot-preview'" in cockpit.text
 assert "href='/demo/acme-incident-cockpit'" in preview.text
 assert 'NO-GO LIVE' in cockpit.text
 assert 'UNKNOWN / BLOCKED' in preview.text

def test_grafana_preview_reuses_canonical_san_payments_incident_ids():
 from portal.acme_impact_read_model import build_acme_impact_read_model
 from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
 cockpit=project_synthetic_incident_cockpit(build_acme_impact_read_model())
 page=client().get('/demo/acme-grafana-pilot-preview')
 assert page.status_code==200
 assert cockpit['incident_id'] in page.text
 assert cockpit['business_impact_incident_id'] in page.text
 assert cockpit['source_sha256'] in page.text
 assert 'ne prouvent aucune corrélation runtime' in page.text

def test_grafana_preview_fails_closed_when_incident_fixture_invalid():
 with patch('portal.acme_impact_read_model.build_acme_impact_read_model',return_value={'schema':'invalid'}):
  response=client().get('/demo/acme-grafana-pilot-preview')
 assert response.status_code==503
 assert response.json()['detail']=='synthetic_grafana_pilot_preview_unqualified'
