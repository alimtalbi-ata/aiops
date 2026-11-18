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
