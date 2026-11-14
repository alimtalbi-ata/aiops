"""Fail-closed join between a DEMO simulation receipt and evidence qualification.

A valid deterministic receipt and consistent evidence metadata remain
insufficient to attest runtime recovery or authorize ITIL/LIVE transitions.
"""
from __future__ import annotations

import re

from portal.acme_isolated_remediation_simulator import verify_simulation_receipt


def assess_simulation_evidence_gate(request: object, simulation: object,
                                    evidence: object, *, expected_source_sha256: str) -> dict:
    if (not isinstance(expected_source_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256) is None):
        raise ValueError("trusted_expected_source_sha256_required")
    if not isinstance(request, dict) or not verify_simulation_receipt(request, simulation):
        raise ValueError("simulation_receipt_not_verified")
    if not isinstance(evidence, dict) or set(evidence) != {
        "schema", "mode", "expected_tenant_id", "source_sha256", "checkpoints",
        "integrity_consistent_unattested_count", "independently_attested_count",
        "overall_qualification", "evidence_accepted", "itil_transition_authorized",
        "live_remediation_authorized",
    }:
        raise ValueError("invalid_evidence_qualification_shape")
    if (evidence["schema"] != "aiops.synthetic-evidence-joint-qualification.v1"
            or evidence["mode"] != "DEMO"
            or evidence["expected_tenant_id"] != request["tenant_id"]
            or evidence["source_sha256"] != expected_source_sha256
            or evidence["overall_qualification"] != "UNKNOWN"
            or evidence["independently_attested_count"] != 0
            or evidence["evidence_accepted"] is not False
            or evidence["itil_transition_authorized"] is not False
            or evidence["live_remediation_authorized"] is not False):
        raise ValueError("evidence_scope_or_safety_mismatch")
    rows = evidence["checkpoints"]
    if not isinstance(rows, list) or len(rows) > 9:
        raise ValueError("invalid_evidence_rows")
    seen = set()
    count = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "checkpoint", "digest_state", "source_receipt_state",
            "integrity_consistent_unattested", "runtime_observation_independently_verified",
            "tenant_actor_authorized", "itil_transition_authorized",
        }:
            raise ValueError("invalid_evidence_row")
        cue = row["checkpoint"]
        if not isinstance(cue, str) or cue in seen:
            raise ValueError("duplicate_evidence_checkpoint")
        seen.add(cue)
        both = (row["digest_state"] == "DIGEST_MATCH_UNATTESTED"
                and row["source_receipt_state"] == "MAC_VALID_SOURCE_KEY_UNATTESTED")
        if (row["integrity_consistent_unattested"] is not both
                or row["runtime_observation_independently_verified"] is not False
                or row["tenant_actor_authorized"] is not False
                or row["itil_transition_authorized"] is not False):
            raise ValueError("forged_evidence_row")
        count += int(both)
    if type(evidence["integrity_consistent_unattested_count"]) is not int or (
            evidence["integrity_consistent_unattested_count"] != count):
        raise ValueError("forged_evidence_count")
    receipt = simulation["receipt"]
    return {
        "schema": "aiops.demo-simulation-evidence-gate.v1",
        "mode": "DEMO",
        "tenant_id": request["tenant_id"],
        "source_sha256": expected_source_sha256,
        "incident_id": request["incident_id"],
        "action_id": request["action_id"],
        "simulation_receipt_sha256": simulation["receipt_sha256"],
        "hypothetical_after_sha256": receipt["after_sha256"],
        "evidence_integrity_consistent_unattested_count": count,
        "simulation_receipt_verified": True,
        "independent_runtime_postcheck_verified": False,
        "actual_recovery_state": "UNKNOWN",
        "next_operator_step": "COLLECT_INDEPENDENT_RUNTIME_POSTCHECK",
        "itil_transition_authorized": False,
        "live_remediation_authorized": False,
    }
