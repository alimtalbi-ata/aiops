#!/usr/bin/env python3
"""Read-only discovery of a *recorded* ACME Payments DEMO run in Core.

No synthetic fixture is accepted as a Core run, and no injection is performed.
"""
import argparse
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

SCENARIO = "SCN-GOLDEN-PAYMENT-P1"
SERVICE = "ACME-SVC-PAYMENTS"
RUN_ID = re.compile(r"RUN-[A-Za-z0-9_-]{1,120}\Z")


def fetch_json(base, path):
    request = Request(base.rstrip("/") + path, headers={"Accept": "application/json"})
    with urlopen(request, timeout=8) as response:
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
    matches = candidates(get(base, "/api/runs"), get(base, "/api/incidents?limit=500"))
    if not matches:
        return {"result": "UNKNOWN", "reason": "NO_MATCHING_CORE_RUN", "run_id": None}
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
            "portal_url": portal.rstrip("/") + "/demo-studio?run_id=" + quote(rid, safe=""),
            "timeline_url": portal.rstrip("/") + "/timeline?run_id=" + quote(rid, safe=""),
        }
    return {"result": "UNKNOWN", "reason": "RUN_DETAIL_MISMATCH", "run_id": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-url", default="http://127.0.0.1:810")
    parser.add_argument("--portal-url", default="http://127.0.0.1:7777")
    args = parser.parse_args(argv)
    for url in (args.core_url, args.portal_url):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ("", "/"):
            parser.error("base URLs must contain only scheme, host and optional port")
    try:
        output = qualify(args.core_url, args.portal_url)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
        output = {"result": "UNKNOWN", "reason": "CORE_READ_FAILED", "error_type": type(exc).__name__, "run_id": None}
    print(json.dumps(output, sort_keys=True, ensure_ascii=False))
    return 0 if output["result"] == "SOURCE_VERIFIED_REGISTRY_ONLY" else 2


if __name__ == "__main__":
    sys.exit(main())
