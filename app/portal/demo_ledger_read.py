"""Viewer-authorized, read-only Demo Studio projection of the Core AI ledger.

The browser never receives the Core internal credential. This is not a tenant
ACL or a runtime/LLM quality attestation; scoped data is denied until an
identity-bound tenant authorization contract exists.
"""
import hmac
import json
import os
import re

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from shared.http import get_json
from shared.tenant_scope import reject_unqualified_tenant_scope

router = APIRouter()
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
_ALLOWED_MODES = frozenset({"DEMO", "REPLAY", "STORY"})


def _response(payload, status=200):
    return JSONResponse(payload, status_code=status, headers=_HEADERS)


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("invalid ledger identity")
    return value


def _evidence_ids(value):
    if not isinstance(value, list) or len(value) > 80:
        raise ValueError("invalid evidence list")
    result = [_identifier(item) for item in value]
    if len(result) != len(set(result)):
        raise ValueError("duplicate evidence identity")
    return result


def _short(value, maximum=500):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError("invalid ledger text")
    return value


def _records(value):
    if not isinstance(value, list) or len(value) > 50 or not all(isinstance(x, dict) for x in value):
        raise ValueError("invalid ledger records")
    return value


def _project(rid, detail, ledger):
    if not isinstance(detail, dict) or not isinstance(ledger, dict):
        raise ValueError("missing Core source")
    reject_unqualified_tenant_scope(detail)
    reject_unqualified_tenant_scope(ledger)
    run = detail.get("run")
    if not isinstance(run, dict) or run.get("run_id") != rid or run.get("mode") not in _ALLOWED_MODES:
        raise ValueError("unqualified Core Run")
    if ledger.get("run_id") != rid:
        raise ValueError("ledger identity mismatch")
    if len(json.dumps(ledger, ensure_ascii=False, default=str).encode("utf-8")) > 131072:
        raise ValueError("ledger too large")
    analyses = []
    for item in _records(ledger.get("analyses")):
        analyses.append({
            "analysis_id": _identifier(item.get("analysis_id")),
            "model": _short(item.get("model"), 160),
            "status": _short(item.get("status"), 32),
            "evidence_ids": _evidence_ids(item.get("evidence_ids")),
        })
    critiques = []
    for item in _records(ledger.get("critiques")):
        output = item.get("output")
        if not isinstance(output, dict) or not isinstance(item.get("validated"), bool):
            raise ValueError("invalid critique")
        checks = []
        for check in _records(output.get("claim_checks")):
            if not isinstance(check.get("supported"), bool):
                raise ValueError("invalid claim support")
            checks.append({"claim": _short(check.get("claim")),
                           "supported": check["supported"],
                           "supporting_evidence_ids": _evidence_ids(check.get("supporting_evidence_ids"))})
        critiques.append({
            "critique_id": _identifier(item.get("critique_id")),
            "analysis_id": _identifier(item.get("analysis_id")),
            "model": _short(item.get("model"), 160),
            "validated": item["validated"],
            "evidence_ids": _evidence_ids(item.get("evidence_ids")),
            "claim_checks": checks,
        })
    decisions = []
    for item in _records(ledger.get("policy_decisions")):
        decisions.append({"policy_decision_id": _identifier(item.get("policy_decision_id")),
                          "decision": _short(item.get("decision"), 64),
                          "state": _short(item.get("state"), 64)})
    return {"schema": "aiops.demo-ledger-read.v1", "run_id": rid,
            "mode": run["mode"], "classification": "DEMO_CORE_RECORDED_NOT_LIVE",
            "source": "CORE_AI_LEDGER_INTERNAL_READ", "tenant_acl_qualified": False,
            "runtime_attested": False, "analyses": analyses, "critiques": critiques,
            "policy_decisions": decisions}


@router.get("/api/demo-studio/runs/{rid}/ai-ledger")
def read_demo_ledger(rid: str, authorization: str | None = Header(default=None)):
    """Fail closed before I/O; never forward the browser's viewer credential."""
    viewer = os.getenv("AIOPS_PORTAL_READ_TOKEN", "")
    internal = os.getenv("AIOPS_INTERNAL_TOKEN") or os.getenv("AIOPS_ADMIN_TOKEN", "")
    if (not viewer or len(viewer) < 32 or len(viewer) > 256
            or not viewer.isascii() or any(ch.isspace() for ch in viewer)
            or not internal or hmac.compare_digest(viewer, internal)):
        return _response({"status": "UNKNOWN", "reason": "viewer_auth_not_configured"}, 503)
    scheme, separator, supplied = (authorization or "").partition(" ")
    if (scheme.lower() != "bearer" or not separator or not supplied
            or not hmac.compare_digest(supplied, viewer)):
        return _response({"status": "UNKNOWN", "reason": "unauthorized"}, 401)
    if not isinstance(rid, str) or _ID.fullmatch(rid) is None:
        return _response({"status": "UNKNOWN", "reason": "ledger_unavailable"}, 503)
    try:
        base = os.getenv("CORE_URL", "http://aiops2-core:810")
        detail = get_json(base, "/api/runs/" + rid)
        if (not isinstance(detail, dict) or not isinstance(detail.get("run"), dict)
                or detail["run"].get("run_id") != rid
                or detail["run"].get("mode") not in _ALLOWED_MODES):
            raise ValueError("unqualified run")
        reject_unqualified_tenant_scope(detail)
        ledger = get_json(base, "/api/runs/" + rid + "/ai-ledger")
        return _response(_project(rid, detail, ledger))
    except Exception:
        # Includes Core 401, timeout, malformed payload, missing source and tenant scope.
        # Never reflect upstream URLs, headers, exceptions or tokens.
        return _response({"status": "UNKNOWN", "reason": "ledger_unavailable"}, 503)
