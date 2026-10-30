#!/usr/bin/env python3
"""Read-only discovery of a *recorded* ACME Payments DEMO run in Core.

No synthetic fixture is accepted as a Core run, and no injection is performed.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCENARIO = "SCN-GOLDEN-PAYMENT-P1"
SERVICE = "ACME-SVC-PAYMENTS"
RUN_ID = re.compile(r"RUN-[A-Za-z0-9_-]{1,120}\Z")


class _RejectRedirects(HTTPRedirectHandler):
    """Never forward an internal bearer credential to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT = build_opener(_RejectRedirects())


def _auth_transport_safe(base):
    """Bearer reads require HTTPS, except explicit loopback HTTP."""
    try:
        parts = urlsplit(base)
    except ValueError:
        return False
    return (parts.scheme == "https" or
            (parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1", "::1"))) and (
        bool(parts.hostname) and not parts.username and not parts.password and
        parts.path in ("", "/") and not parts.query and not parts.fragment
    )


# Core caps the list endpoints; these windows do not cover historical records.
RUN_REGISTRY_LIMIT = 100
INCIDENT_REGISTRY_LIMIT = 500


def fetch_json(base, path, token=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(base.rstrip("/") + path, headers=headers)
    with _NO_REDIRECT.open(request, timeout=8) as response:
        if response.status != 200:
            raise ValueError("unexpected_http_status")
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("invalid_core_json")
    return payload


def candidates(runs, incidents):
    if not isinstance(runs, dict) or not isinstance(runs.get("items"), list):
        raise ValueError("invalid_runs_contract")
    if not isinstance(incidents, dict) or not isinstance(incidents.get("items"), list):
        raise ValueError("invalid_incidents_contract")
    registry = {
        i["incident_id"]: i for i in incidents["items"]
        if isinstance(i, dict) and isinstance(i.get("incident_id"), str)
    }
    matches = []
    for run in runs["items"]:
        if not isinstance(run, dict) or run.get("mode") not in ("DEMO", "REPLAY", "STORY"):
            continue
        rid = run.get("run_id")
        if not isinstance(rid, str) or not RUN_ID.fullmatch(rid):
            continue
        if run.get("scenario_id") != SCENARIO:
            continue
        incident = registry.get(run.get("incident_id"))
        if not incident or incident.get("synthetic") is not True:
            continue
        if incident.get("service_id") != SERVICE or incident.get("source") not in (
            "portal-demo", "portal-demo-enriched", "synthetic-simulator"
        ):
            continue
        matches.append((run, incident))
    # Prefer terminal runs, then the order supplied by Core (newest first).
    return sorted(matches, key=lambda pair: pair[0].get("status") not in ("RESOLVED", "BLOCKED"))


def qualify(base, portal, get=fetch_json):
    runs = get(base, "/api/runs")
    incidents = get(base, "/api/incidents?limit=500")
    matches = candidates(runs, incidents)
    if not matches:
        # A full window cannot rule out older matching runs or incidents.
        limited = (len(runs["items"]) >= RUN_REGISTRY_LIMIT
                   or len(incidents["items"]) >= INCIDENT_REGISTRY_LIMIT)
        return {
            "result": "UNKNOWN",
            "reason": "REGISTRY_WINDOW_LIMITED" if limited else "NO_MATCHING_CORE_RUN",
            "run_id": None,
        }
    for run, incident in matches:
        rid = run["run_id"]
        detail = get(base, "/api/runs/" + quote(rid, safe=""))
        canonical = detail.get("run")
        events = detail.get("events")
        if not isinstance(canonical, dict) or not isinstance(events, list):
            continue
        if any(canonical.get(k) != run.get(k) for k in ("run_id", "incident_id", "scenario_id", "mode")):
            continue
        types = sorted({e.get("event_type") for e in events if isinstance(e, dict) and isinstance(e.get("event_type"), str)})
        evidence_refs = sorted({eid for e in events if isinstance(e, dict) and isinstance(e.get("evidence_ids"), list)
                                for eid in e["evidence_ids"] if isinstance(eid, str) and eid})
        return {
            "result": "SOURCE_VERIFIED_REGISTRY_ONLY", "run_id": rid,
            "incident_id": incident["incident_id"], "scenario_id": SCENARIO,
            "mode": canonical["mode"], "status": canonical.get("status", "UNKNOWN"),
            "incident_source": incident["source"], "synthetic": True,
            "service_id": SERVICE, "event_types": types, "evidence_refs_unattested": evidence_refs,
            "payments_runtime_impact": "UNKNOWN", "glpi_ticket": "UNKNOWN",
            "tenant_acl_qualified": False, "e2e_attested": False,
            "portal_url": portal.rstrip("/") + "/demo-studio/run/" + quote(rid, safe=""),
            "timeline_url": portal.rstrip("/") + "/timeline?run_id=" + quote(rid, safe=""),
        }
    return {"result": "UNKNOWN", "reason": "RUN_DETAIL_MISMATCH", "run_id": None}



_EVIDENCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_EVIDENCE_SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


def _qualified_evidence_items(items):
    """Validate the bounded, deduplicated metadata contract without emitting values."""
    if not isinstance(items, list) or not 1 <= len(items) <= 80:
        return False
    seen = set()
    now = datetime.now(timezone.utc)
    for item in items:
        if not isinstance(item, dict):
            return False
        eid, source = item.get("evidence_id"), item.get("source")
        known_at, digest = item.get("known_at"), item.get("payload_sha256")
        if (not isinstance(eid, str) or not _EVIDENCE_ID.fullmatch(eid)
                or eid in seen or not isinstance(source, str)
                or not _EVIDENCE_SOURCE.fullmatch(source)
                or not isinstance(digest, str)
                or re.fullmatch(r"[a-f0-9]{64}", digest) is None
                or not isinstance(known_at, str)):
            return False
        try:
            stamp = datetime.fromisoformat(known_at.replace("Z", "+00:00"))
            if (stamp.tzinfo is None or stamp.utcoffset() is None
                    or stamp.astimezone(timezone.utc) > now + timedelta(minutes=5)):
                return False
        except (ValueError, OverflowError):
            return False
        seen.add(eid)
    return True


def probe_authenticated_evidence(base, rid, token, get=fetch_json):
    """Probe Core's bearer-protected evidence refs, without attesting tenant or runtime.

    Core registry GETs are NOT auth-enforced; only this evidence endpoint
    checks the bearer token. Never expose tokens or raw evidence in output.
    """
    if not token:
        return {"status": "UNKNOWN", "reason": "TOKEN_NOT_CONFIGURED"}
    if not isinstance(rid, str) or not RUN_ID.fullmatch(rid):
        return {"status": "UNKNOWN", "reason": "RUN_ID_UNQUALIFIED"}
    if not _auth_transport_safe(base):
        return {"status": "UNKNOWN", "reason": "AUTH_TRANSPORT_UNSAFE"}
    try:
        response = get(base, "/api/noc/runs/" + quote(rid, safe="") + "/evidence-refs", token=token)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        return {"status": "UNKNOWN", "reason": "AUTH_EVIDENCE_READ_FAILED"}
    items = response.get("items") if isinstance(response, dict) else None
    if (not isinstance(response, dict)
            or response.get("schema") != "aiops.core-demo-evidence-refs.v1"
            or response.get("run_id") != rid
            or response.get("classification") != "SYNTHETIC_ONLY"
            or response.get("event_link_verified") is not True
            or response.get("tenant_acl_qualified") is not False
            or response.get("runtime_attested") is not False
            or not _qualified_evidence_items(items)):
        return {"status": "UNKNOWN", "reason": "EVIDENCE_CONTRACT_MISMATCH"}
    return {"status": "SOURCE_VERIFIED_SYNTHETIC_ONLY", "reference_count": len(items),
            "tenant_acl_qualified": False, "runtime_attested": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-url", default="http://127.0.0.1:810")
    parser.add_argument("--portal-url", default="http://127.0.0.1:7777")
    parser.add_argument("--probe-auth-evidence", action="store_true",
                        help="read-only bearer-protected evidence probe using AIOPS_INTERNAL_TOKEN or AIOPS_ADMIN_TOKEN")
    args = parser.parse_args(argv)
    for url in (args.core_url, args.portal_url):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ("", "/"):
            parser.error("base URLs must contain only scheme, host and optional port")
    try:
        output = qualify(args.core_url, args.portal_url)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
        output = {"result": "UNKNOWN", "reason": "CORE_READ_FAILED", "error_type": type(exc).__name__, "run_id": None}
    if args.probe_auth_evidence:
        token = os.getenv("AIOPS_INTERNAL_TOKEN") or os.getenv("AIOPS_ADMIN_TOKEN")
        output["authenticated_evidence_probe"] = (
            probe_authenticated_evidence(args.core_url, output["run_id"], token)
            if output.get("run_id") else {"status": "UNKNOWN", "reason": "NO_QUALIFIED_RUN"}
        )
        output["registry_auth_enforced"] = False
    print(json.dumps(output, sort_keys=True, ensure_ascii=False))
    registry_ok = output["result"] == "SOURCE_VERIFIED_REGISTRY_ONLY"
    auth_ok = (not args.probe_auth_evidence or
               output["authenticated_evidence_probe"]["status"] == "SOURCE_VERIFIED_SYNTHETIC_ONLY")
    return 0 if registry_ok and auth_ok else 2


if __name__ == "__main__":
    sys.exit(main())
