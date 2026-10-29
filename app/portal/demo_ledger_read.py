"""Viewer-authorized, read-only Demo Studio projection of the Core AI ledger.

The browser never receives the Core internal credential. This is not a tenant
ACL or a runtime/LLM quality attestation; scoped data is denied until an
identity-bound tenant authorization contract exists.
"""
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from shared.http import get_json
from shared.tenant_scope import reject_unqualified_tenant_scope

router = APIRouter()
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
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


def _qualified_refs(rid, refs, expected_ids):
    """Only Core-linked, synthetic references qualify; never assert source truth."""
    if (not isinstance(refs, dict)
            or set(refs) != {"schema", "run_id", "classification",
                             "tenant_acl_qualified", "runtime_attested",
                             "event_link_verified", "items"}
            or refs["schema"] != "aiops.core-demo-evidence-refs.v1"
            or refs["run_id"] != rid or refs["classification"] != "SYNTHETIC_ONLY"
            or refs["tenant_acl_qualified"] is not False
            or refs["runtime_attested"] is not False
            or refs["event_link_verified"] is not True):
        raise ValueError("unqualified evidence resolver")
    items = refs["items"]
    reject_unqualified_tenant_scope(items)
    if (not isinstance(items, list) or not 1 <= len(items) <= 80
            or not expected_ids or len(items) != len(expected_ids)):
        raise ValueError("missing evidence references")
    projected = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {
                "evidence_id", "source", "payload_sha256", "known_at"}:
            raise ValueError("invalid evidence reference")
        evidence_id = _identifier(item["evidence_id"])
        source = item["source"]
        digest = item["payload_sha256"]
        timestamp = item["known_at"]
        if (not isinstance(source, str) or not _SOURCE.fullmatch(source)
                or not isinstance(digest, str) or not _SHA.fullmatch(digest)
                or not isinstance(timestamp, str) or len(timestamp) > 48):
            raise ValueError("invalid evidence metadata")
        try:
            known = datetime.fromisoformat(timestamp)
        except ValueError as exc:
            raise ValueError("invalid evidence timestamp") from exc
        if (known.tzinfo is None or known.utcoffset() is None
                or known.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(minutes=5)):
            raise ValueError("unqualified evidence timestamp")
        projected.append({"evidence_id": evidence_id, "source": source,
                          "payload_sha256": digest, "known_at": timestamp})
    if {item["evidence_id"] for item in projected} != expected_ids:
        raise ValueError("unlinked evidence references")
    return projected


def _project(rid, detail, ledger, refs):
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
    # Only internally linked Core records may be presented as a sourced claim.
    # This is referential consistency, NOT evidence existence or tenant ACL proof.
    analyses = []
    analysis_evidence = {}
    for item in _records(ledger.get("analyses")):
        analysis_id = _identifier(item.get("analysis_id"))
        if analysis_id in analysis_evidence:
            raise ValueError("duplicate analysis identity")
        evidence_ids = _evidence_ids(item.get("evidence_ids"))
        analysis_evidence[analysis_id] = set(evidence_ids)
        analyses.append({
            "analysis_id": analysis_id,
            "model": _short(item.get("model"), 160),
            "status": _short(item.get("status"), 32),
            "evidence_ids": evidence_ids,
        })
    critiques = []
    critique_ids = set()
    critique_analysis = {}
    for item in _records(ledger.get("critiques")):
        output = item.get("output")
        if not isinstance(output, dict) or not isinstance(item.get("validated"), bool):
            raise ValueError("invalid critique")
        critique_id = _identifier(item.get("critique_id"))
        analysis_id = _identifier(item.get("analysis_id"))
        if critique_id in critique_ids or analysis_id not in analysis_evidence:
            raise ValueError("unlinked critique")
        critique_ids.add(critique_id)
        critique_analysis[critique_id] = analysis_id
        evidence_ids = _evidence_ids(item.get("evidence_ids"))
        # A Critique may cite only Evidence from its own linked Analysis.
        # The Core resolver validates the Run-wide union, not this per-Analysis edge.
        if not set(evidence_ids).issubset(analysis_evidence[analysis_id]):
            raise ValueError("critique evidence outside linked analysis")
        linked_ids = set(evidence_ids)
        checks = []
        for check in _records(output.get("claim_checks")):
            if not isinstance(check.get("supported"), bool):
                raise ValueError("invalid claim support")
            supporting_ids = _evidence_ids(check.get("supporting_evidence_ids"))
            if (not set(supporting_ids).issubset(linked_ids)
                    or (check["supported"] and not supporting_ids)):
                raise ValueError("unlinked supporting evidence")
            checks.append({"claim": _short(check.get("claim")),
                           "supported": check["supported"],
                           "supporting_evidence_ids": supporting_ids})
        critiques.append({
            "critique_id": critique_id,
            "analysis_id": analysis_id,
            "model": _short(item.get("model"), 160),
            "validated": item["validated"],
            "evidence_ids": evidence_ids,
            "claim_checks": checks,
        })
    expected_ids = set().union(*analysis_evidence.values()) if analysis_evidence else set()
    qualified_refs = _qualified_refs(rid, refs, expected_ids)
    decisions = []
    policy_ids = set()
    for item in _records(ledger.get("policy_decisions")):
        policy_id = _identifier(item.get("policy_decision_id"))
        if policy_id in policy_ids:
            raise ValueError("duplicate policy identity")
        policy_ids.add(policy_id)
        policy_analysis = item.get("analysis_id")
        policy_critique = item.get("critique_id")
        # Core's foreign keys permit a Policy row for this Run to reference
        # an Analysis/Critique from another Run. Do not project such a decision.
        if policy_analysis is None and policy_critique is None:
            raise ValueError("unlinked policy decision")
        if policy_analysis is not None:
            policy_analysis = _identifier(policy_analysis)
            if policy_analysis not in analysis_evidence:
                raise ValueError("policy analysis outside run ledger")
        if policy_critique is not None:
            policy_critique = _identifier(policy_critique)
            linked_analysis = critique_analysis.get(policy_critique)
            if linked_analysis is None or (
                    policy_analysis is not None and linked_analysis != policy_analysis):
                raise ValueError("policy critique outside linked analysis")
        decisions.append({"policy_decision_id": policy_id,
                          "decision": _short(item.get("decision"), 64),
                          "state": _short(item.get("state"), 64)})
    return {"schema": "aiops.demo-ledger-read.v1", "run_id": rid,
            "mode": run["mode"], "classification": "DEMO_CORE_RECORDED_NOT_LIVE",
            "source": "CORE_AI_LEDGER_INTERNAL_READ", "tenant_acl_qualified": False,
            "runtime_attested": False, "analyses": analyses, "critiques": critiques,
            "evidence_classification": "SYNTHETIC_ONLY",
            "event_link_verified": True, "evidence_refs": qualified_refs,
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
        refs = get_json(base, "/api/noc/runs/" + rid + "/evidence-refs")
        return _response(_project(rid, detail, ledger, refs))
    except Exception:
        # Includes Core 401, timeout, malformed payload, missing source and tenant scope.
        # Never reflect upstream URLs, headers, exceptions or tokens.
        return _response({"status": "UNKNOWN", "reason": "ledger_unavailable"}, 503)
