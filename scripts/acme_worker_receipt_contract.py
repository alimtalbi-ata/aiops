#!/usr/bin/env python3
"""Offline strict structural check of the *existing* Worker ACME no-effect receipt.

Not a Temporal attestation, tenant ACL check, or Core→Worker join. No HTTP.
"""
from __future__ import annotations

import re

SCHEMA = "aiops.worker-acme-simulated-no-effect.v1"
TRANSITIONS = [
    "CORE_PREPARED_INDEPENDENTLY_VERIFIED",
    "TWIN_SIMULATED_APPROVAL_VALIDATED",
    "POLICY_SIMULATE_INDEPENDENTLY_VERIFIED",
    "WORKER_NO_EFFECT",
]
CONSTANTS = {
    "tenant_id": "ACME-TEST",
    "approval_issuer": "TWIN_ACME_SIMULATED",
    "approval_kind": "SIMULATED",
    "action": "SIMULATE",
    "receipt_status": "SIMULATED_NO_EFFECT",
    "receipt_phase": "PRE_RESOLUTION",
    "core_status_at_validation": "PREPARED",
    "audit_authority": "TEMPORAL_WORKFLOW_HISTORY_ONLY",
}
FALSE_FLAGS = (
    "resolution_verified", "human_approved", "execution_allowed",
    "effect_allowed", "real_glpi_writes_allowed", "live_effects_allowed",
)
TRUE_FLAGS = ("post_resolution_readback_required",)


def inspect_worker_receipt(value, expected_attempt_id: str | None = None):
    """Return explicit rejection reasons. Digest/authority must be checked by Worker."""
    if type(value) is not dict:
        return ["WORKER_RECEIPT_INVALID"]
    errors = []
    if value.get("schema") != SCHEMA:
        errors.append("WORKER_SCHEMA_INVALID")
    attempt = value.get("attempt_id")
    if type(attempt) is not str or not re.fullmatch(r"ACME-SIM-[A-F0-9]{16}", attempt):
        errors.append("WORKER_ATTEMPT_INVALID")
    if expected_attempt_id is not None and attempt != expected_attempt_id:
        errors.append("WORKER_ATTEMPT_MISMATCH")
    for field, expected in CONSTANTS.items():
        if value.get(field) != expected:
            errors.append("WORKER_" + field.upper() + "_INVALID")
    for field in FALSE_FLAGS:
        if value.get(field) is not False:
            errors.append("WORKER_" + field.upper() + "_INVALID")
    for field in TRUE_FLAGS:
        if value.get(field) is not True:
            errors.append("WORKER_" + field.upper() + "_INVALID")
    if type(value.get("effect_receipts")) is not int or value["effect_receipts"] != 0:
        errors.append("WORKER_EFFECT_RECEIPTS_INVALID")
    if value.get("audit_transitions") != TRANSITIONS:
        errors.append("WORKER_TRANSITIONS_INVALID")
    return errors
