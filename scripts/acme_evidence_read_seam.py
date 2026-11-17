"""Non-HTTP ACME evidence orchestration seam; no service credential handling.

Callers must provide an independently authenticated/authorized decision from
their real server-side identity and ACL providers. This module intentionally
does not implement those providers or publish an HTTP endpoint.
"""
from __future__ import annotations

import hashlib
import re

from scripts.acme_core_worker_binding import inspect_core_worker_binding
from scripts.acme_viewer_access_policy import ViewerDecision


def qualify_evidence_read(decision: ViewerDecision, attempt_id: str,
                          read_core, read_worker):
    """Refuse all upstream I/O unless the caller's decision is affirmative.

    Even with a positive pure-policy decision, both readbacks must be valid
    and bound to the requested attempt. Not an independent ACL authority.
    """
    if type(decision) is not ViewerDecision or not decision.authorized:
        return {"status": "NO_GO", "reason": "TENANT_ACL_NOT_QUALIFIED"}
    if decision.reason != "POLICY_CONDITIONS_SATISFIED_ONLY":
        return {"status": "NO_GO", "reason": "TENANT_ACL_NOT_QUALIFIED"}
    # A fabricated positive decision is not authority; nevertheless reject
    # malformed attempts before any upstream request and verify the Core
    # canonical run binding before contacting Worker.
    if type(attempt_id) is not str or not re.fullmatch(
            r"ACME-SIM-[A-F0-9]{16}", attempt_id):
        return {"status": "NO_GO", "reason": "ACME_ATTEMPT_INVALID"}
    expected_run = "RUN-SIM-" + hashlib.sha256(
        ("ACME-TEST:" + attempt_id).encode("ascii")
    ).hexdigest()[:24].upper()
    # The caller MUST establish the viewer ACL before calling this seam.
    # No response payload or exception text from either source is exposed.
    try:
        core = read_core(attempt_id)
        if type(core) is not dict or core.get("attempt_id") != attempt_id:
            return {"status": "NO_GO", "reason": "CORE_BINDING_NOT_QUALIFIED"}
        if core.get("tenant_id") != "ACME-TEST" or core.get("run_id") != expected_run:
            return {"status": "NO_GO", "reason": "CORE_BINDING_NOT_QUALIFIED"}
        worker = read_worker(attempt_id)
        errors = inspect_core_worker_binding(core, worker)
    except Exception:
        return {"status": "NO_GO", "reason": "EVIDENCE_READBACK_UNAVAILABLE"}
    if errors:
        return {"status": "NO_GO", "reason": "CORE_WORKER_BINDING_NOT_QUALIFIED"}
    # This proves only offline declaration consistency of injected readbacks.
    # No tenant data is returned and no browser evidence is qualified.
    return {"status": "OFFLINE_CONSISTENT_ONLY", "reason": "NO_RUNTIME_ATTESTATION"}
