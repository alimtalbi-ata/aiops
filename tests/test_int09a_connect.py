from copy import deepcopy
from test_acme_historical_journey_offline import fixture, ATTEMPT, RUN, INC, TICKET
from portal.acme_workbench_presentation import render_same_run_journey
from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from portal.acme_incident_cockpit_html import render_synthetic_cockpit_html
import pytest

@pytest.mark.parametrize("resolved",[False,True])
def test_connected_actual_projector(resolved):
    snapshot,rows=fixture(resolved)
    before=deepcopy((snapshot,rows))
    model=project_synthetic_incident_cockpit(build_acme_impact_read_model())
    html=render_synthetic_cockpit_html(model,offline_journey=(snapshot,rows,ATTEMPT))
    for label in (RUN,INC,TICKET,"INJECTED_OFFLINE_NOT_ATTESTED","UNBOUND","NO-GO LIVE","occurred_at_utc"):
        assert label in html
    assert html.count("Evidence Workbench — lecture seule")==1
    assert html.count("<table>")==4
    assert (snapshot,rows)==before

def test_foreign_run_refused():
    snapshot,rows=fixture()
    rows[0][7]["run_id"]="FOREIGN"
    html=render_same_run_journey((snapshot,rows,ATTEMPT))
    assert "entrée refusée" in html
    assert RUN not in html
    assert "MISSING" in render_same_run_journey()

def test_actual_phase_refusals_connected():
    from portal.acme_int08_phases import admission_v1, preterminal_v1
    from portal.acme_runtime_workbench import render_collector_result
    now="2026-11-18T09:00:00Z"
    a=admission_v1({}, {}, None, None, {k:k+"-source" for k in ("core","twin","policy","critic","hitl")},{},as_of_utc=now)
    p=preterminal_v1({}, {}, {"contract_status":"CONTRACT_ONLY"}, {}, {}, {}, {}, {},as_of_utc=now)
    html=render_collector_result(admission=a,preterminal=p)
    assert "Admission : BLOCK — UNKNOWN" in html
    assert "Préterminal : REJECT — UNKNOWN" in html
    assert "Qualification finale</h4><p>MISSING" in html
    assert "NO-GO" in html
    assert "projection incompatible" in render_collector_result(admission=p)
    a["execution_allowed"]=True
    assert "projection incompatible" in render_collector_result(admission=a)
