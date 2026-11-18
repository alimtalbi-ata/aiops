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

def test_san_actual_graph_connected():
    from portal.acme_historical_san_offline import NODES,NODE_NAMES,NODE_CRITICALITY,EDGES,SITE,PAYMENTS
    from portal.acme_impact_read_model import render_acme_impact_html
    nodes=[(k,v,NODE_NAMES[k],SITE,"SIMULATED",NODE_CRITICALITY[k],1) for k,v in NODES.items()]
    edges=[(k,*v,1,1) for k,v in EDGES.items()]
    model=build_acme_impact_read_model()
    html=render_acme_impact_html(model,offline_san=("FC_SFP_DEGRADATION",nodes,edges))
    for label in (PAYMENTS,"Services candidats","Services observés","SYNTHETIC_FIXTURE_ONLY","ABSTAIN","UNBOUND","graph_sha256"):
        assert label in html
    assert "Services observés</dt><dd>MISSING" in html
    assert html.count("<nav ")==1
    bad=render_acme_impact_html(model,offline_san=("FC_SFP_DEGRADATION",nodes,edges[:-1]))
    assert "entrée refusée" in bad
    assert "Relations directes synthétiques" not in bad

def test_golden_nominal_admission_in_cockpit():
    from test_int09b_admission_nominal import fixture, call, assert_closed
    f=fixture()
    before=deepcopy(f)
    result=call(f)
    assert_closed(result)
    assert result["contract_status"]=="CONTRACT_ONLY"
    model=project_synthetic_incident_cockpit(build_acme_impact_read_model())
    html=render_synthetic_cockpit_html(model,offline_admission=result)
    for label in ("Admission : BLOCK — UNKNOWN", "ADMISSION_CONSISTENT_NOT_ATTESTED",
                  "INC-IMPACT-001","RUN-SIM-001","SIM-GLPI-001","CONTRACT_ONLY",
                  "core-source","twin-source","policy-source","critic-source","hitl-source",
                  "Préterminal : MISSING","NO-GO LIVE"):
        assert label in html
    assert f==before
    assert html.count("Evidence Workbench — lecture seule")==1
    assert "public-test-fixture-not-a-credential" not in html
    assert f[6]["signature"] not in html
    assert f[6]["payload"]["approval_nonce"] not in html
    f[6]["signature"]="0"*64
    refused=call(f)
    assert_closed(refused)
    html=render_synthetic_cockpit_html(model,offline_admission=refused)
    assert "Admission : REJECT — UNKNOWN" in html
    assert "HISTORICAL_PREDICATE_REFUSED" in html
    assert "core-source" not in html


def test_same_run_source_provenance_and_scope():
    snapshot, rows = fixture(True)
    model = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    html = render_synthetic_cockpit_html(model, offline_journey=(snapshot, rows, ATTEMPT), offline_events=[{"payload":{"message":"UNRELATED-OFFLINE"}}])
    assert html.count("id='same-run-history'") == 1
    for event_id in snapshot["source_event_ids"]:
        assert event_id in html
    assert html.index("same-run-history") < html.index("UNRELATED-OFFLINE")
    assert "non reliés au Same-Run" in html
    assert "Référentiel STORY_OFFLINE" in html
    assert "UNKNOWN pour ce Run" in html


def test_existing_b_chain_phase_identity_comparison():
    from test_int09b_admission_nominal import fixture, call
    from test_int09b_preterminal import chain, invoke
    from portal.acme_runtime_workbench import render_collector_result
    admission, preterminal = call(fixture()), invoke(chain())
    before = deepcopy((admission, preterminal))
    html = render_collector_result(admission=admission, preterminal=preterminal)
    assert "Identités déclarées concordantes" in html
    assert "continuité causale UNKNOWN" in html
    assert "receipt-source" in html and "postcheck-source" in html
    assert (admission, preterminal) == before
    preterminal["projection"]["identity"]["run_id"] = "FOREIGN"
    assert "identités divergentes" in render_collector_result(admission=admission, preterminal=preterminal)
    preterminal["execution_allowed"] = True
    assert "Identités déclarées concordantes" not in render_collector_result(admission=admission, preterminal=preterminal)


def test_historical_wire_missing_fields_not_inferred():
    snapshot, rows = fixture(True)
    html = render_same_run_journey((snapshot, rows, ATTEMPT))
    assert "Impact indépendant</dt><dd>UNKNOWN" in html
    assert "Horodatage snapshot Core</dt><dd>MISSING" in html
    assert "SIMULATED_ONLY" in html
    assert "Policy indépendante : UNKNOWN" in html
    assert "HITL négatif : aucun lien incident/attempt attesté" in html

def test_actual_c_collector_in_existing_workbench():
    from test_int07_offline_collector import CollectorTests
    from test_int09b_admission_nominal import fixture as golden, call
    from test_int09b_preterminal import chain, invoke
    collector = CollectorTests()
    f, e = collector.fixture()
    result, _ = collector.invoke(f, e)
    assert result["reason"] == "OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED"
    model = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    html = render_synthetic_cockpit_html(model, offline_collector_result=result,
        offline_admission=call(golden()), offline_preterminal=invoke(chain()))
    assert "Qualification finale" in html
    assert "OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED" in html
    assert "continuité causale UNKNOWN" in html
    assert "PROD / LIVE : NO-GO" in html
    assert "RESOLVED" not in html


def test_historical_twin_consumer_connected_to_existing_impact():
    from pathlib import Path
    from portal.acme_twin_provenance import build_twin_evidence
    from portal.acme_impact_read_model import render_acme_impact_html
    fixture_bytes=Path("app/portal/acme-fixtures.json").read_bytes()
    twin=build_twin_evidence(fixture_bytes)
    impact={k:twin[k] for k in ("source_sha256","run_id","incident_id","impact_incident_id")}
    impact.update({k:twin["impact"][k] for k in ("impact_path","affected_ci_ids")})
    impact.update(ci_count=len(twin["nodes"]),twin_evidence=twin)
    before=deepcopy(impact)
    html=render_acme_impact_html(build_acme_impact_read_model(),offline_twin=impact)
    for label in ("Twin historique — STORY_OFFLINE","UNBOUND","UNKNOWN","NO_RUNTIME_OBSERVATION",
                  "Runtime attesté : NON","Remédiation LIVE : NON","Nombre de chemins","Citations de dépendances"):
        assert label in html
    assert "HITL" not in html
    assert html.count("<nav ")==1
    assert impact==before
    impact["twin_evidence"]["runtime_attested"]=True
    bad=render_acme_impact_html(build_acme_impact_read_model(),offline_twin=impact)
    assert "UNKNOWN — projection refusée" in bad
    assert "source_sha256" not in bad


def test_existing_glpi_handoff_navigation():
    model=project_synthetic_incident_cockpit(build_acme_impact_read_model())
    html=render_synthetic_cockpit_html(model)
    assert html.count("href='/itsm'")==1
    assert "TENANT_ACL_NOT_QUALIFIED" in html
    assert "Association ticket/Run : NOT_INSTALLED" in html
    assert "Aucun ticket réel ni droit HITL déduit" in html
