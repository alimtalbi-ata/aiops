"""Opt-in, localhost-only, read-only Core/Worker ACME sandbox receipt check.

NEVER creates an attempt, resolves a run, starts Temporal or calls GLPI.
Not a browser, OIDC, tenant ACL, or deployed-provenance attestation.
Run only in an explicitly approved isolated sandbox with loopback port forwards.
"""
from __future__ import annotations

import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from scripts.acme_core_worker_binding import inspect_core_worker_binding

ATTEMPT = re.compile(r"ACME-SIM-[A-F0-9]{16}\Z")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def loopback_url(base: str) -> bool:
    try:
        p = urlsplit(base)
        return (p.scheme == "http" and p.hostname in ("127.0.0.1", "::1")
                and p.port is not None and p.username is None and p.password is None
                and not p.path.rstrip("/") and not p.query and not p.fragment)
    except (TypeError, ValueError):
        return False


def qualify_runtime_readback(*, attempt: str, core_base: str, worker_base: str,
                             core_token: str, worker_token: str,
                             fetch=None) -> dict:
    result = {"schema": "aiops.acme-readonly-runtime-recipe.v1",
              "status": "NO_GO", "reason": "PREFLIGHT_REJECTED",
              "runtime_evidence_consistent": False, "viewer_acl_verified": False,
              "browser_verified": False, "real_execution_allowed": False,
              "remediation_effect_verified": False,
              "autonomous_closed_loop_verified": False,
              "deployed_sha_attested": False,
              "learning_claim_verified": False}
    if (type(attempt) is not str or ATTEMPT.fullmatch(attempt) is None
            or not loopback_url(core_base) or not loopback_url(worker_base)
            or core_base == worker_base
            or type(core_token) is not str or len(core_token) < 32
            or type(worker_token) is not str or len(worker_token) < 32
            or any(c in core_token + worker_token for c in "\r\n")):
        return result
    def read(base, token):
        url = base.rstrip("/") + "/api/sandbox/acme/e2e/" + quote(attempt, safe="")
        if fetch is not None:
            return fetch(url, token)
        opener = build_opener(ProxyHandler({}), NoRedirect())
        req = Request(url, headers={"Authorization": "Bearer " + token,
                                    "Accept": "application/json"}, method="GET")
        with opener.open(req, timeout=5) as response:
            if response.status != 200:
                raise ValueError("upstream rejected")
            if response.headers.get_content_type() != "application/json":
                raise ValueError("unexpected content type")
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("oversized receipt")
        return json.loads(raw)
    try:
        core = read(core_base, core_token)
        # Check canonical Core attempt/tenant before touching Worker.
        if (type(core) is not dict or core.get("attempt_id") != attempt
                or core.get("tenant_id") != "ACME-TEST"
                or core.get("schema") != "aiops.core-acme-sandbox-readback.v1"):
            return {**result, "reason": "CORE_READBACK_REJECTED"}
        worker = read(worker_base, worker_token)
        errors = inspect_core_worker_binding(core, worker)
        if errors:
            return {**result, "reason": "CORE_WORKER_INCONSISTENT",
                    "rejection_codes": errors}
    except (HTTPError, URLError, ValueError, TypeError, KeyError, TimeoutError, OSError):
        return {**result, "reason": "READBACK_UNAVAILABLE_OR_INVALID"}
    return {**result, "status": "RUNTIME_READBACK_CONSISTENT_ONLY",
            "reason": "NO_VIEWER_ACL_OR_BROWSER_ATTESTATION",
            "runtime_evidence_consistent": True}


def main() -> int:
    # Explicit opt-in for a separately approved, isolated sandbox. Never infer
    # approval from available service tokens or a loopback endpoint.
    if (os.environ.get('ACME_READONLY_SANDBOX_APPROVED') != 'YES'
            or os.environ.get('ACME_SANDBOX_ISOLATED') != 'YES'):
        print(json.dumps({'schema': 'aiops.acme-readonly-runtime-recipe.v1',
                          'status': 'NO_GO', 'reason': 'SANDBOX_EXECUTION_NOT_APPROVED',
                          'runtime_evidence_consistent': False,
                          'viewer_acl_verified': False, 'browser_verified': False,
                          'real_execution_allowed': False}, sort_keys=True))
        return 2
    # No command-line tokens; do not print response bodies or bearer values.
    result = qualify_runtime_readback(
        attempt=os.environ.get("ACME_ATTEMPT_ID", ""),
        core_base=os.environ.get("ACME_CORE_LOOPBACK_URL", ""),
        worker_base=os.environ.get("ACME_WORKER_LOOPBACK_URL", ""),
        core_token=os.environ.get("ACME_CORE_SERVICE_TOKEN", ""),
        worker_token=os.environ.get("ACME_WORKER_SERVICE_TOKEN", ""))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["runtime_evidence_consistent"] else 2


if __name__ == "__main__":
    sys.exit(main())
