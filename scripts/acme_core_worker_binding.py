"""Offline identity binding between canonical Core ACME readback and Worker receipt.

Checks independent declarations; never substitutes for authenticated readbacks,
Core's PG16 read() verification, Worker's digest, or sandbox runtime E2E.
"""
from __future__ import annotations
import re
import hashlib
from scripts.acme_worker_receipt_contract import inspect_worker_receipt

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,99}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")


def inspect_core_worker_binding(core, worker):
    errors = []
    if type(core) is not dict:
        return ["CORE_READBACK_INVALID"]
    if core.get("schema") != "aiops.core-acme-sandbox-readback.v1":
        errors.append("CORE_SCHEMA_INVALID")
    attempt = core.get("attempt_id")
    if type(attempt) is not str or not re.fullmatch(r"ACME-SIM-[A-F0-9]{16}", attempt):
        errors.append("CORE_ATTEMPT_INVALID")
    errors.extend(inspect_worker_receipt(worker, attempt if type(attempt) is str else None))
    if type(worker) is not dict:
        return sorted(set(errors))
    for key in ("tenant_id", "attempt_id", "incident_id", "run_id",
                "ticket_id", "proposal_id", "approval_id"):
        cv, wv = core.get(key), worker.get(key)
        if type(cv) is not str or not ID.fullmatch(cv) or cv != wv:
            errors.append("JOIN_" + key.upper() + "_MISMATCH")
    # Core's existing ident(prefix, attempt) is deterministic. Matching two
    # supplied documents alone must not legitimize a forged shared identity.
    if type(attempt) is str and re.fullmatch(r"ACME-SIM-[A-F0-9]{16}", attempt):
        def canonical(prefix, suffix="", length=24):
            return prefix + hashlib.sha256(
                ("ACME-TEST:" + attempt + suffix).encode("ascii")
            ).hexdigest()[:length].upper()
        for key, prefix in (("incident_id", "INC-SIM-"),
                            ("run_id", "RUN-SIM-"),
                            ("ticket_id", "SIM-GLPI-"),
                            ("proposal_id", "PROP-SIM-")):
            if core.get(key) != canonical(prefix):
                errors.append("CORE_" + key.upper() + "_NONCANONICAL")
        expected_events = [canonical("SYN-EVT-", ":" + str(i), 20)
                           for i in range(1, 8)]
        if core.get("source_event_ids") != expected_events:
            errors.append("CORE_SOURCE_EVENTS_NONCANONICAL")
    for key, expected in (("tenant_id", "ACME-TEST"),
                          ("scenario_id", "ACME-SAN-PAYMENTS"),
                          ("mode", "SIMULATION"),
                          ("ticket_authority", "SIMULATED_ONLY"),
                          ("glpi_mode", "SIMULATED_ONLY"),
                          ("incident_status", "RESOLVED"),
                          ("run_status", "RESOLVED"),
                          ("ticket_status", "RESOLVED")):
        if core.get(key) != expected:
            errors.append("CORE_" + key.upper() + "_INVALID")
    for key in ("worker_receipt_verified", "terminal_ticket_receipt_verified",
                "resolution_after_worker_receipt", "approval_fresh_at_resolution",
                "approval_nonce_consumed", "analysis_validated",
                "critic_validated", "source_hashes_qualified"):
        if core.get(key) is not True:
            errors.append("CORE_" + key.upper() + "_NOT_VERIFIED")
    for key in ("human_approved", "human_approval_claimed",
                "approval_nonce_revoked", "live_effects_allowed",
                "real_glpi_writes_allowed", "execution_allowed", "effect_allowed"):
        if core.get(key) is not False:
            errors.append("CORE_" + key.upper() + "_UNSAFE")
    for key, expected in (("source_event_count", 7),
                          ("evidence_count", 2)):
        if type(core.get(key)) is not int or core[key] != expected:
            errors.append("CORE_" + key.upper() + "_INVALID")
    for key, expected in (("analysis_kind", "SYNTHETIC_FIXTURE"),
                          ("approval_issuer", "TWIN_ACME_SIMULATED")):
        if core.get(key) != expected:
            errors.append("CORE_" + key.upper() + "_INVALID")
    terminal = core.get("terminal_ticket_sha256")
    if type(terminal) is not str or not DIGEST.fullmatch(terminal):
        errors.append("CORE_TERMINAL_TICKET_DIGEST_INVALID")
    request = core.get("request_sha256")
    if type(request) is not str or not DIGEST.fullmatch(request):
        errors.append("CORE_REQUEST_DIGEST_INVALID")
    digest = core.get("worker_receipt_sha256")
    if (type(digest) is not str or not DIGEST.fullmatch(digest)
            or worker.get("receipt_sha256") != digest):
        errors.append("JOIN_WORKER_RECEIPT_DIGEST_MISMATCH")
    if (type(core.get("source_event_ids")) is not list
            or len(core["source_event_ids"]) != 7
            or core["source_event_ids"] != worker.get("core_source_event_ids")):
        errors.append("JOIN_SOURCE_EVENTS_MISMATCH")
    if core.get("request_sha256") != worker.get("core_request_sha256"):
        errors.append("JOIN_CORE_REQUEST_MISMATCH")
    return sorted(set(errors))
