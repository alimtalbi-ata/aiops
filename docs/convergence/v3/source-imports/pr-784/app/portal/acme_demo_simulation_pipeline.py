"""End-to-end in-memory DEMO path: incident cockpit -> simulation -> safety gate.

No network, database, Temporal worker, ITIL mutation or LIVE action.
"""
from __future__ import annotations

from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from portal.acme_isolated_remediation_simulator import simulate_remediation_dry_run
from portal.acme_simulation_evidence_gate import assess_simulation_evidence_gate


def run_acme_demo_simulation(*, tenant_id: str = "acme-demo") -> dict:
    # The incident identity and fixture digest are derived from one validated
    # cockpit snapshot, never copied from a caller-supplied evidence report.
    cockpit = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    if (cockpit["mode"] != "DEMO"
            or cockpit["overall_qualification"] != "UNKNOWN"
            or cockpit["live_remediation_authorized"] is not False
            or cockpit["analyst_critic_review"]["policy_disposition"] != "DENY_LIVE_ACTION"):
        raise ValueError("cockpit_not_safe_for_demo")
    request = {
        "schema": "aiops.demo-remediation-simulation-request.v1",
        "mode": "DEMO",
        "tenant_id": tenant_id,
        "incident_id": cockpit["incident_id"],
        "action_id": "acme-payments-restart-hypothesis-001",
        "action_kind": "SERVICE_RESTART_SIMULATION",
        "policy_decision": "SIMULATE_ONLY",
        "before": {
            "service": "payments",
            "health": "DEGRADED",
            "alert_active": True,
        },
    }
    simulation = simulate_remediation_dry_run(request)
    # The fixture contains NO runtime evidence. Do not fabricate a MAC,
    # source readback, post-check, or an evidence acceptance.
    evidence = {
        "schema": "aiops.synthetic-evidence-joint-qualification.v1",
        "mode": "DEMO",
        "expected_tenant_id": tenant_id,
        "source_sha256": cockpit["source_sha256"],
        "checkpoints": [],
        "integrity_consistent_unattested_count": 0,
        "independently_attested_count": 0,
        "overall_qualification": "UNKNOWN",
        "evidence_accepted": False,
        "itil_transition_authorized": False,
        "live_remediation_authorized": False,
    }
    gate = assess_simulation_evidence_gate(
        request, simulation, evidence,
        expected_source_sha256=cockpit["source_sha256"],
        expected_incident_id=cockpit["incident_id"],
    )
    if (gate["actual_recovery_state"] != "UNKNOWN"
            or gate["itil_transition_authorized"] is not False
            or gate["live_remediation_authorized"] is not False):
        raise ValueError("unsafe_demo_gate")
    return {
        "schema": "aiops.acme-demo-simulation-pipeline.v1",
        "mode": "DEMO",
        "incident_id": cockpit["incident_id"],
        "source_sha256": cockpit["source_sha256"],
        "business_impact_incident_id": cockpit["business_impact_incident_id"],
        "simulation": simulation,
        "evidence_gate": gate,
        "runtime_execution_performed": False,
        "glpi_write_performed": False,
        "temporal_execution_performed": False,
        "actual_recovery_state": "UNKNOWN",
        "live_remediation_authorized": False,
    }
