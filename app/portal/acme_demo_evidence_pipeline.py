"""Offline DEMO incident -> simulation -> supplied evidence integrity inspection.

Callbacks must be explicitly supplied by a trusted caller; no default network,
credential, source key, production authorization or runtime attestation exists.
"""
from __future__ import annotations

from collections.abc import Callable

from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from portal.acme_isolated_remediation_simulator import simulate_remediation_dry_run
from portal.acme_evidence_joint_qualification import qualify_synthetic_evidence_jointly
from portal.acme_simulation_evidence_gate import assess_simulation_evidence_gate


def inspect_acme_demo_evidence(
    manifest: object, receipts: object,
    readback: Callable[[str, str], bytes],
    resolve_key: Callable[[str, str], bytes],
    *, expected_tenant_id: str,
) -> dict:
    cockpit = project_synthetic_incident_cockpit(build_acme_impact_read_model())
    if (cockpit["mode"] != "DEMO"
            or cockpit["overall_qualification"] != "UNKNOWN"
            or cockpit["live_remediation_authorized"] is not False
            or cockpit["analyst_critic_review"]["policy_disposition"] != "DENY_LIVE_ACTION"):
        raise ValueError("cockpit_not_safe_for_demo")
    # Validate tenant and manifest before invoking any external callback.
    from portal.acme_evidence_manifest_validator import inspect_synthetic_evidence_manifest
    if (not isinstance(expected_tenant_id, str)
            or not 2 <= len(expected_tenant_id) <= 128
            or not expected_tenant_id[0].isascii()
            or not expected_tenant_id[0].isalnum()
            or any(not c.isascii() or not (c.isalnum() or c in "_.:-")
                   for c in expected_tenant_id)):
        raise ValueError("trusted_expected_tenant_required")
    lifecycle = cockpit["lifecycle"]
    inspect_synthetic_evidence_manifest(lifecycle, manifest)
    request = {
        "schema": "aiops.demo-remediation-simulation-request.v1",
        "mode": "DEMO",
        "tenant_id": expected_tenant_id,
        "incident_id": cockpit["incident_id"],
        "action_id": "acme-payments-restart-hypothesis-001",
        "action_kind": "SERVICE_RESTART_SIMULATION",
        "policy_decision": "SIMULATE_ONLY",
        "before": {"service": "payments", "health": "DEGRADED",
                   "alert_active": True},
    }
    simulation = simulate_remediation_dry_run(request)
    evidence = qualify_synthetic_evidence_jointly(
        lifecycle, manifest, receipts, readback, resolve_key,
        expected_tenant_id=expected_tenant_id)
    gate = assess_simulation_evidence_gate(
        request, simulation, evidence,
        expected_source_sha256=cockpit["source_sha256"],
        expected_incident_id=cockpit["incident_id"])
    return {
        "schema": "aiops.acme-demo-evidence-pipeline.v1",
        "mode": "DEMO",
        "incident_id": cockpit["incident_id"],
        "source_sha256": cockpit["source_sha256"],
        "simulation": simulation,
        "evidence_qualification": evidence,
        "evidence_gate": gate,
        "actual_recovery_state": "UNKNOWN",
        "itil_transition_authorized": False,
        "live_remediation_authorized": False,
    }
