"""A unified synthetic cockpit cannot mix snapshots or promote absent proof."""
import copy
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit


def test_cockpit_is_single_fixture_consistent_and_never_authorized():
    impact = build_acme_impact_read_model()
    result = project_synthetic_incident_cockpit(impact)
    assert result["source_sha256"] == impact["source_sha256"]
    assert result["incident_id"] == impact["incident_id"]
    assert result["business_impact_incident_id"] == impact["impact_incident_id"]
    assert result["lifecycle"]["source_sha256"] == result["evidence_plan"]["source_sha256"]
    assert result["itil_readiness"]["source_sha256"] == result["analyst_critic_review"]["source_sha256"]
    assert len(result["lifecycle"]["stages"]) == 9
    assert len(result["itil_readiness"]["transitions"]) == 8
    assert result["evidence_plan"]["requested_count"] == 9
    assert result["evidence_plan"]["verified_count"] == 0
    assert result["analyst_critic_review"]["runtime_citations_verified"] == 0
    assert result["overall_qualification"] == "UNKNOWN"
    assert result["live_remediation_authorized"] is False


@pytest.mark.parametrize("path,value", [
    (("runtime_attested",), True),
    (("decision_preview", "critic", "decision"), "APPROVED"),
    (("decision_preview", "policy", "decision"), "ALLOW_LIVE_ACTION"),
    (("checkpoint_evidence", 0, "status"), "PASS"),
])
def test_cockpit_rejects_forged_runtime_or_decision(path, value):
    impact = copy.deepcopy(build_acme_impact_read_model())
    target = impact
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        project_synthetic_incident_cockpit(impact)


def test_canonical_portal_cockpit_endpoint_fail_closed():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    client = TestClient(app)
    response = client.get("/api/demo/acme-incident-cockpit")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["overall_qualification"] == "UNKNOWN"
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "invalid"}):
        assert client.get("/api/demo/acme-incident-cockpit").status_code == 503


def test_canonical_operator_cockpit_page_contains_all_gates_and_no_actions():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    client = TestClient(app)
    page = client.get("/demo/acme-incident-cockpit")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "NO-GO LIVE" in page.text
    assert "SAN P1" in page.text and "Payments P2" in page.text
    assert "HOLD_FOR_HUMAN_REVIEW" in page.text
    assert "DENY_LIVE_ACTION" in page.text
    assert "0 / 9" in page.text
    # 9 lifecycle + 8 ITIL + 9 customer timeline + 9 evidence requirements.
    assert page.text.count("<tr><th scope='row'>") == 35
    assert "<script" not in page.text.lower()
    assert "<form" not in page.text.lower()
    with patch("portal.acme_impact_read_model.build_acme_impact_read_model",
               return_value={"schema": "invalid"}):
        assert client.get("/demo/acme-incident-cockpit").status_code == 503


def test_html_renderer_rejects_forged_success():
    from portal.acme_incident_cockpit_html import render_synthetic_cockpit_html
    cockpit = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    cockpit["itil_readiness"]["transitions"][0]["authorized"] = True
    with pytest.raises(ValueError, match="unqualified_cockpit_details"):
        render_synthetic_cockpit_html(cockpit)


def test_operator_cockpit_explains_customer_use_case_and_proof_boundary():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    page = TestClient(app).get("/demo/acme-incident-cockpit")
    assert page.status_code == 200
    assert "Parcours démontrable" in page.text
    assert "SAN vers Payments" in page.text
    assert "scripts/verify_aiops2_demo_acceptance.py" in page.text
    assert "preuve runtime" in page.text
    assert "pas une attestation de production" in page.text
    assert "<script" not in page.text.lower()
    assert "<form" not in page.text.lower()


def test_customer_walkthrough_has_five_working_anchor_targets_and_safe_verdict():
    from html.parser import HTMLParser

    class Anchors(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = set()
            self.targets = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if "id" in attrs:
                self.ids.add(attrs["id"])
            if tag == "a" and attrs.get("href", "").startswith("#"):
                self.targets.append(attrs["href"][1:])

    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    page = TestClient(app).get("/demo/acme-incident-cockpit")
    assert page.status_code == 200
    anchors = Anchors()
    anchors.feed(page.text)
    assert anchors.targets == ["impact", "workbench", "impact", "workbench", "decision", "itil", "verdict"]
    # Preserve the historical direct-link target while the guided journey uses Workbench.
    assert "evidence" in anchors.ids
    assert "workbench" in anchors.ids
    assert set(anchors.targets).issubset(anchors.ids)
    assert page.text.index("id='decision'") < page.text.index("id='itil'")
    assert page.text.index("id='itil'") < page.text.index("id='verdict'")
    assert "GO pour le scénario synthétique" in page.text
    assert "UNKNOWN pour les preuves runtime" in page.text
    assert "NO-GO LIVE" in page.text
    assert "<script" not in page.text.lower()
    assert "<form" not in page.text.lower()


def test_customer_timeline_is_nine_unattested_business_steps():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    page = TestClient(app).get("/demo/acme-incident-cockpit")
    assert page.status_code == 200
    assert "Chronologie explicative" in page.text
    assert "pas événements observés" in page.text
    assert page.text.count("UNKNOWN — preuve runtime absente") == 9
    for label in ("Signal SAN candidat", "Relier le SAN au service Payments",
                  "Formuler puis contester une hypothèse",
                  "Exiger une vérification indépendante", "Préparer Problem et PIR"):
        assert label in page.text
    assert "aucune horodatée ni attestée" in page.text
    assert "NO-GO LIVE" in page.text


def test_noc_decision_card_explains_proof_human_gate_and_safe_next_step():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    page = TestClient(app).get("/demo/acme-incident-cockpit")
    assert page.status_code == 200
    assert "Fiche de décision" in page.text
    for label in ("Ce que nous savons", "Ce qui manque", "Qui doit valider",
                  "Pourquoi c'est bloqué", "Prochaine étape permise"):
        assert label in page.text
    assert "Neuf preuves indépendantes sur neuf" in page.text
    assert "HOLD_FOR_HUMAN_REVIEW" in page.text
    assert "DENY_LIVE_ACTION" in page.text
    assert "lecture seule" in page.text
    assert "Pas d'exécution Temporal" in page.text
    assert "<form" not in page.text.lower()
    assert "<script" not in page.text.lower()


@pytest.mark.parametrize("field,value", [
    ("human_approval_verified", True),
    ("independent_postcheck_verified", True),
    ("operational_decision_authorized", True),
])
def test_noc_decision_card_rejects_forged_authority(field, value):
    from portal.acme_incident_cockpit_html import render_synthetic_cockpit_html
    cockpit = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    cockpit["analyst_critic_review"][field] = value
    with pytest.raises(ValueError, match="unqualified_cockpit_details"):
        render_synthetic_cockpit_html(cockpit)


def test_customer_evidence_register_names_nine_actual_requirements():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    page = TestClient(app).get("/demo/acme-incident-cockpit")
    assert page.status_code == 200
    assert "Registre des preuves attendues" in page.text
    assert page.text.count("MISSING — contrôle humain requis") == 9
    for kind in ("ALERT_STATE", "CORRELATION_EVENT",
                 "SERVICE_DEPENDENCY_OBSERVATION", "ANALYST_CRITIC_REVIEW",
                 "GLPI_AUTHENTICATED_TICKET_READBACK", "POLICY_AND_HITL_DECISION",
                 "ISOLATED_SIMULATOR_RECEIPT", "INDEPENDENT_POSTCHECK",
                 "GLPI_AUTHENTICATED_CLOSURE_AND_PIR_READBACK"):
        assert kind in page.text
    assert "observed_at, source_id, content_sha256" in page.text
    assert "<form" not in page.text.lower()


@pytest.mark.parametrize("field,value", [
    ("submitted_evidence", {"fake": "receipt"}),
    ("attested", True),
    ("qualifies_runtime", True),
    ("collection_mode", "AUTO_LIVE"),
    ("required_evidence_type", "FORGED_PROOF"),
    ("expected_source", "forged-source"),
])
def test_customer_evidence_register_rejects_forged_receipts(field, value):
    from portal.acme_incident_cockpit_html import render_synthetic_cockpit_html
    cockpit = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    cockpit["evidence_plan"]["requests"][0][field] = value
    with pytest.raises(ValueError, match="unqualified_evidence_requirements"):
        render_synthetic_cockpit_html(cockpit)


def test_customer_cockpit_responsive_layout_preserves_readonly_semantics():
    from html.parser import HTMLParser

    class TableWrappers(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.wrapper_count = 0
            self.table_count = 0
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "div" and "table-scroll" in attrs.get("class", "").split():
                self.wrapper_count += 1
                self.stack.append("wrapper")
            elif tag == "table":
                self.table_count += 1
                assert self.stack and self.stack[-1] == "wrapper"
                self.stack.append("table")
        def handle_endtag(self, tag):
            if tag == "table":
                assert self.stack.pop() == "table"
            elif tag == "div" and self.stack and self.stack[-1] == "wrapper":
                self.stack.pop()

    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    page = TestClient(app).get("/demo/acme-incident-cockpit")
    assert page.status_code == 200
    parser = TableWrappers()
    parser.feed(page.text)
    assert parser.wrapper_count == parser.table_count == 4
    assert parser.stack == []
    assert "Résumé de qualification" in page.text
    assert "GO — scénario synthétique" in page.text
    assert "UNKNOWN — preuves runtime" in page.text
    assert "NO-GO LIVE" in page.text
    assert "prefers-reduced-motion:reduce" in page.text
    assert "focus-visible" in page.text
    assert "<script" not in page.text.lower()
    assert "<form" not in page.text.lower()


def test_cockpit_cross_navigation_connects_existing_operator_surfaces():
    with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "unit-test-only"}):
        from portal.main import app
    page = TestClient(app).get("/demo/acme-incident-cockpit")
    assert page.status_code == 200
    for href in (
        "/#noc", "/demo/explore-story", "/demo/acme-impact",
        "/#incidents", "/#runs", "#evidence",
    ):
        assert f'href="{href}"' in page.text or f"href='{href}'" in page.text
    assert "Navigation espace opérateur" in page.text
    assert "href='#evidence'>Workbench</a>" in page.text
    assert "Aller au parcours SAN vers Payments" in page.text
    assert "assets/aiops-theme.css" in page.text
    assert "NO-GO LIVE" in page.text
