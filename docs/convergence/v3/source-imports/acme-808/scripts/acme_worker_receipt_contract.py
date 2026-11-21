#!/usr/bin/env python3
"""Offline strict structural check of the *existing* Worker ACME no-effect receipt.

Not a Temporal attestation, tenant ACL check, or Core→Worker join. No HTTP.
"""
from __future__ import annotations

import re
import hashlib
import hmac
import json

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
    "core_014_015_written", "glpi_write",
    "effect_allowed", "real_glpi_writes_allowed", "live_effects_allowed",
)
TRUE_FLAGS = ("post_resolution_readback_required",)


def inspect_worker_receipt(value, expected_attempt_id: str | None = None):
    """Return explicit rejection reasons. Digest integrity checked offline; runtime authority must be checked by Worker/Core."""
    if type(value) is not dict:
        return ["WORKER_RECEIPT_INVALID"]
    errors = []
    if value.get("schema") != SCHEMA:
        errors.append("WORKER_SCHEMA_INVALID")
    attempt = value.get("attempt_id")
    if type(attempt) is not str or not re.fullmatch(r"ACME-SIM-[A-F0-9]{16}", attempt):
        errors.append("WORKER_ATTEMPT_INVALID")
    if type(attempt) is str and re.fullmatch(r"ACME-SIM-[A-F0-9]{16}", attempt):
        for field, prefix in (("incident_id", "INC-SIM-"),
                              ("run_id", "RUN-SIM-"),
                              ("ticket_id", "SIM-GLPI-"),
                              ("proposal_id", "PROP-SIM-")):
            expected = prefix + hashlib.sha256(
                ("ACME-TEST:" + attempt).encode("ascii")
            ).hexdigest()[:24].upper()
            if value.get(field) != expected:
                errors.append("WORKER_" + field.upper() + "_NONCANONICAL")
        approval = value.get("approval_id")
        if type(approval) is not str or not re.fullmatch(
                r"SIM-APP-[A-Za-z0-9_-]{3,92}", approval):
            errors.append("WORKER_APPROVAL_ID_INVALID")
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
    if type(value.get("receipt_sha256")) is not str or not re.fullmatch(
            r"[a-f0-9]{64}", value["receipt_sha256"]):
        errors.append("WORKER_DIGEST_INVALID")
    else:
        try:
            canonical = json.dumps(
                {k: v for k, v in value.items() if k != "receipt_sha256"},
                sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("ascii")
            actual = hashlib.sha256(canonical).hexdigest()
            if not hmac.compare_digest(actual, value["receipt_sha256"]):
                errors.append("WORKER_DIGEST_MISMATCH")
        except (TypeError, ValueError, UnicodeError, OverflowError):
            errors.append("WORKER_DIGEST_INVALID")
    for field in ("core_request_sha256", "twin_approval_nonce_sha256"):
        if type(value.get(field)) is not str or not re.fullmatch(
                r"[a-f0-9]{64}", value[field]):
            errors.append("WORKER_" + field.upper() + "_INVALID")
    if type(attempt) is str and re.fullmatch(r"ACME-SIM-[A-F0-9]{16}", attempt):
        expected_events = [
            "SYN-EVT-" + hashlib.sha256(
                ("ACME-TEST:" + attempt + ":" + str(i)).encode("ascii")
            ).hexdigest()[:20].upper() for i in range(1, 8)
        ]
        if value.get("core_source_event_ids") != expected_events:
            errors.append("WORKER_SOURCE_IDS_NONCANONICAL")
    if value.get("audit_transitions") != TRANSITIONS:
        errors.append("WORKER_TRANSITIONS_INVALID")
    return errors
