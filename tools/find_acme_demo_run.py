#!/usr/bin/env python3
"""Read-only, fail-closed Core DEMO Run/Evidence locator (no injection)."""
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
RUN_ID = re.compile(r"RUN-[A-Za-z0-9_-]{1,120}\Z")
INCIDENT_ID = re.compile(r"INC-[A-Za-z0-9_-]{1,120}\Z")
EVIDENCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z")
MIN_EVIDENCE_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(_NoRedirect())


def _safe_url(base):
    try:
        p = urlsplit(base)
        return (p.scheme == "https" or (p.scheme == "http" and p.hostname in
                ("127.0.0.1", "localhost", "::1"))) and bool(p.hostname) and (
                p.username is None and p.password is None and p.path in ("", "/")
                and not p.query and not p.fragment)
    except (TypeError, ValueError):
        return False


def fetch_json(base, path, token=None):
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    with _OPENER.open(Request(base.rstrip("/") + path, headers=headers), timeout=8) as response:
        if response.status != 200:
            raise ValueError("unexpected_status")
        data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError("response_too_large")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("invalid_json_contract")
    return result


def _unknown(reason):
    return {"result": "UNKNOWN", "reason": reason, "run_id": None,
            "incident_id": None, "runtime_attested": False,
            "tenant_acl_qualified": False, "observed_payments_impact": "UNKNOWN"}


def _event_refs(events, rid):
    if not isinstance(events, list) or not 1 <= len(events) <= 1000:
        return None
    refs = set()
    for n, event in enumerate(events, 1):
        if (not isinstance(event, dict) or type(event.get("sequence")) is not int
                or event["sequence"] != n or
                ("run_id" in event and event["run_id"] != rid)):
            return None
        ids = event.get("evidence_ids")
        if (not isinstance(ids, list) or len(ids) > 80 or
                any(not isinstance(eid, str) or not EVIDENCE_ID.fullmatch(eid)
                    for eid in ids) or len(ids) != len(set(ids))):
            return None
        refs.update(ids)
    first = events[0]
    if (first.get("event_type") != "RUN_CREATED" or first.get("stage") != "INGEST"
            or first.get("status") != "CREATED"
            or not isinstance(first.get("payload"), dict)
            or first["payload"].get("scenario_id") != SCENARIO
            or first["payload"].get("mode") != "DEMO"
            or sum(e.get("event_type") == "RUN_CREATED" for e in events) != 1):
        return None
    return refs if 0 < len(refs) <= 80 else None


def _metadata_valid(items, refs, rid):
    if not isinstance(items, list) or not 1 <= len(items) <= 80:
        return False
    seen = set()
    now = datetime.now(timezone.utc)
    for item in items:
        if not isinstance(item, dict):
            return False
        eid, source, stamp, digest = (item.get("evidence_id"), item.get("source"),
                                       item.get("known_at"), item.get("payload_sha256"))
        if (not isinstance(eid, str) or not EVIDENCE_ID.fullmatch(eid)
                or eid not in refs or eid in seen or not isinstance(source, str)
                or not SOURCE.fullmatch(source) or not isinstance(digest, str)
                or re.fullmatch(r"[a-f0-9]{64}", digest) is None
                or not isinstance(stamp, str) or len(stamp) > 48
                or TIMESTAMP.fullmatch(stamp) is None or item.get("tenant_id") is not None
                or ("run_id" in item and item["run_id"] != rid)):
            return False
        try:
            at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if (at.utcoffset() is None or at.astimezone(timezone.utc) < MIN_EVIDENCE_UTC
                    or at.astimezone(timezone.utc) > now + timedelta(minutes=5)):
                return False
        except (ValueError, OverflowError):
            return False
        seen.add(eid)
    return True


def qualify(base, rid, iid, token, get=fetch_json):
    """Never certify from public Core GETs; two bearer reads are mandatory."""
    if (not isinstance(rid, str) or not RUN_ID.fullmatch(rid) or
            not isinstance(iid, str) or not INCIDENT_ID.fullmatch(iid)):
        return _unknown("EXPECTED_PAIR_INVALID")
    if not token:
        return _unknown("TOKEN_NOT_CONFIGURED")
    if not _safe_url(base):
        return _unknown("AUTH_TRANSPORT_UNSAFE")
    try:
        runs = get(base, "/api/runs")
        if not isinstance(runs.get("items"), list):
            return _unknown("REGISTRY_CONTRACT_MISMATCH")
        matches = [x for x in runs["items"] if isinstance(x, dict) and x.get("run_id") == rid]
        if len(matches) != 1:
            return _unknown("RUN_NOT_UNIQUELY_IN_REGISTRY_WINDOW")
        row = matches[0]
        if (row.get("incident_id") != iid or row.get("scenario_id") != SCENARIO
                or row.get("mode") != "DEMO"):
            return _unknown("RUN_REGISTRY_MISMATCH")
        detail = get(base, "/api/runs/" + quote(rid, safe=""))
        canonical = detail.get("run")
        if (not isinstance(canonical, dict) or
                any(canonical.get(k) != row.get(k) for k in
                    ("run_id", "incident_id", "scenario_id", "mode", "status"))):
            return _unknown("RUN_DETAIL_MISMATCH")
        for key in ("stages", "gates"):
            nested = detail.get(key, [])
            if (not isinstance(nested, list) or any(
                    not isinstance(x, dict) or ("run_id" in x and x["run_id"] != rid)
                    for x in nested)):
                return _unknown("NESTED_RUN_SCOPE_MISMATCH")
        refs = _event_refs(detail.get("events"), rid)
        if refs is None:
            return _unknown("EVENT_EVIDENCE_REFS_UNQUALIFIED")
        auth_run = get(base, "/api/noc/runs/" + quote(rid, safe=""), token=token)
        a = auth_run.get("run")
        if (not isinstance(a, dict) or
                any(a.get(k) != row.get(k) for k in ("run_id", "incident_id", "mode", "status"))
                or auth_run.get("data_classification") != "SYNTHETIC_CANONICAL_RUN"
                or auth_run.get("tenant_acl_qualified") is not False
                or auth_run.get("runtime_authenticated") is not False
                or auth_run.get("live_remediation_authorized") is not False):
            return _unknown("AUTH_RUN_CONTRACT_MISMATCH")
        evidence = get(base, "/api/noc/runs/" + quote(rid, safe="") + "/evidence-refs", token=token)
        if (evidence.get("schema") != "aiops.core-demo-evidence-refs.v1"
                or evidence.get("run_id") != rid
                or evidence.get("classification") != "SYNTHETIC_ONLY"
                or evidence.get("event_link_verified") is not True
                or evidence.get("tenant_acl_qualified") is not False
                or evidence.get("runtime_attested") is not False
                or not _metadata_valid(evidence.get("items"), refs, rid)):
            return _unknown("EVIDENCE_EVENT_LINK_MISMATCH")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return _unknown("CORE_AUTH_READ_FAILED")
    return {"result": "SOURCE_VERIFIED_SYNTHETIC_ONLY", "scenario_id": SCENARIO,
            "run_id": rid, "incident_id": iid, "mode": "DEMO",
            "status": canonical["status"], "authenticated_evidence_count": len(evidence["items"]),
            "run_event_evidence_count": len(refs), "tenant_acl_qualified": False,
            "runtime_attested": False, "observed_payments_impact": "UNKNOWN"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--core-url", required=True)
    p.add_argument("--expect-run-id", required=True)
    p.add_argument("--expect-incident-id", required=True)
    p.add_argument("--probe-auth-evidence", action="store_true", required=False)
    args = p.parse_args(argv)
    if not args.probe_auth_evidence:
        p.error("--probe-auth-evidence is mandatory")
    result = qualify(args.core_url, args.expect_run_id, args.expect_incident_id,
                     os.getenv("AIOPS_INTERNAL_TOKEN"))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["result"] == "SOURCE_VERIFIED_SYNTHETIC_ONLY" else 2


if __name__ == "__main__":
    sys.exit(main())
