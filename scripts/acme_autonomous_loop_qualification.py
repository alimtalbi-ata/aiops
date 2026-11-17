"""Offline qualification of the AIOps autonomous decision-to-verification loop.

The existing Core/Worker receipts are synthetic and pre-resolution/no-effect.
A structurally complete loop is NOT an authorization to execute a real action,
a claim of learned model improvement, or a runtime attestation.
"""
from __future__ import annotations

from scripts.acme_core_worker_binding import inspect_core_worker_binding

STAGES = ("OBSERVE", "CORRELATE", "DIAGNOSE", "POLICY", "SIMULATED_ACTION",
          "VERIFY", "AUDIT", "REMEDIATION_EFFECT", "LEARN")


def assess_autonomous_loop(core: object, worker: object) -> dict:
    result = {
        "schema": "aiops.acme-autonomous-loop-qualification.v1",
        "status": "NO_GO",
        "mode": "SIMULATION_ONLY",
        "stages": {stage: "NOT_VERIFIED" for stage in STAGES},
        "runtime_attested": False,
        "real_execution_allowed": False,
        "learning_claim_verified": False,
    }
    errors = inspect_core_worker_binding(core, worker)
    if errors:
        return {**result, "reason": "CORE_WORKER_LOOP_INCONSISTENT",
                "rejection_codes": errors}
    # These stage labels describe ONLY internally consistent supplied bytes.
    # No trusted runtime identity, temporal provenance, browser or effect proof.
    return {**result, "status": "OFFLINE_CONSISTENT_ONLY",
            "reason": "NO_RUNTIME_ATTESTATION",
            "stages": {stage: ("NOT_VERIFIED" if stage in
                       ("REMEDIATION_EFFECT", "LEARN") else "OFFLINE_DECLARED_ONLY")
                       for stage in STAGES},
            "action_semantics": "WORKER_SIMULATED_NO_EFFECT_PRE_RESOLUTION",
            "verification_semantics": "CORE_SYNTHETIC_RESOLUTION_DECLARED",
            "audit_semantics": "WORKER_TEMPORAL_HISTORY_DECLARED_NOT_ATTESTED"}
