#!/usr/bin/env python3
"""Read-only bearer-protected Twin SAN->Payments topology qualification.

The reverse traversal is a dependency hypothesis, not observed business impact.
No writes, injection, ticket creation, or LIVE action are performed.
"""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

class _RejectRedirects(HTTPRedirectHandler):
    """Never forward Twin's internal bearer token to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT = build_opener(_RejectRedirects())


ROOT = "ACME-SAN-FABRIC-A"
# Source: db/migrations/005_seed_acme.sql. Stored direction: consumer -> dependency.
EXPECTED = (
    ("ACME-E08", "ACME-STO-PURE01", ROOT, "PATH"),
    ("ACME-E06", "ACME-VM-PAY01", "ACME-STO-PURE01", "USES"),
    ("ACME-E04", "ACME-APP-ORACLEPAY", "ACME-VM-PAY01", "RUNS_ON"),
    ("ACME-E02", "ACME-SVC-PAYMENTS", "ACME-APP-ORACLEPAY", "DEPENDS_ON"),
    ("ACME-E01", "ACME-BIZ-PAYMENTS", "ACME-SVC-PAYMENTS", "USES"),
)


def fetch_impact(base, token):
    request = Request(base.rstrip("/") + "/api/twin/impact/" + quote(ROOT, safe=""),
                      headers={"Accept": "application/json", "Authorization": "Bearer " + token})
    with _NO_REDIRECT.open(request, timeout=8) as response:
        if response.status != 200:
            raise ValueError("unexpected_http_status")
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("invalid_twin_json")
    return payload


def qualify(payload):
    """Fail closed unless all five *actual returned* edges match the seed."""
    unknown = {"result": "UNKNOWN", "reason": "TWIN_PATH_NOT_VERIFIED",
               "run_id": None, "observed_payments_impact": "UNKNOWN"}
    if not isinstance(payload, dict) or any((
        payload.get("root") != ROOT,
        payload.get("path_semantics") != "SEEDED_TOPOLOGY_SHORTEST_HOPS_NOT_RUNTIME_CAUSALITY",
        payload.get("traversal_direction") != "REVERSE_CONSUMER_TO_DEPENDENCY",
        payload.get("affected_semantics") != "DEPENDENT_CANDIDATES_NOT_CONFIRMED_IMPACT",
        payload.get("provenance") != "TWIN_DB_TOPOLOGY_READ_ONLY",
        payload.get("runtime_impact_state") != "UNKNOWN",
        payload.get("runtime_authenticated") is not False,
        payload.get("tenant_acl_qualified") is not False,
        payload.get("redundancy_evaluated") is not False,
        payload.get("live_remediation_authorized") is not False,
    )):
        return unknown
    edges, affected = payload.get("shortest_path_edges"), payload.get("affected")
    if not isinstance(edges, list) or not isinstance(affected, list):
        return unknown
    actual = set()
    seen_edge_ids = set()
    for edge in edges:
        if not isinstance(edge, dict) or not all(isinstance(edge.get(k), str)
                 for k in ("edge_id", "source_id", "target_id", "relation_type")):
            return unknown
        # A set of tuples alone silently hides duplicate/conflicting edge IDs.
        # One edge ID must denote exactly one edge in the Twin API response.
        if not edge["edge_id"] or edge["edge_id"] in seen_edge_ids:
            return unknown
        seen_edge_ids.add(edge["edge_id"])
        actual.add((edge["edge_id"], edge["source_id"], edge["target_id"], edge["relation_type"]))
    depths = {}
    for item in affected:
        if not isinstance(item, dict) or not isinstance(item.get("node_id"), str):
            return unknown
        depth = item.get("depth")
        if type(depth) is not int or depth < 0 or depth > 8:
            return unknown
        # Even identical duplicate affected nodes make the response ambiguous.
        if not item["node_id"] or item["node_id"] in depths:
            return unknown
        depths[item["node_id"]] = depth
    if not set(EXPECTED).issubset(actual):
        return unknown
    chain = (ROOT, "ACME-STO-PURE01", "ACME-VM-PAY01", "ACME-APP-ORACLEPAY",
             "ACME-SVC-PAYMENTS", "ACME-BIZ-PAYMENTS")
    if any(depths.get(node) != i for i, node in enumerate(chain)):
        return unknown
    return {"result": "SOURCE_VERIFIED_TWIN_DB_TOPOLOGY_ONLY", "root": ROOT,
            "path_edge_ids": [edge[0] for edge in EXPECTED],
            "dependency_direction": "CONSUMER_TO_DEPENDENCY",
            "traversal_direction": "REVERSE_CONSUMER_TO_DEPENDENCY",
            "payments_service": "ACME-SVC-PAYMENTS",
            "observed_payments_impact": "UNKNOWN", "run_id": None,
            "core_run_correlation": "UNKNOWN", "redundancy_evaluated": False,
            "tenant_acl_qualified": False, "runtime_authenticated": False,
            "source": "TWIN_DB_TOPOLOGY_READ_ONLY", "seed_source": "db/migrations/005_seed_acme.sql"}


def main(argv=None, get=fetch_impact):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--twin-url", required=True, help="Twin API base URL; HTTPS required except loopback")
    args = parser.parse_args(argv)
    parts = urlsplit(args.twin_url)
    if (parts.scheme not in ("http", "https") or not parts.hostname or
        parts.username or parts.password or parts.query or parts.fragment or
        parts.path not in ("", "/") or
        (parts.scheme == "http" and parts.hostname not in ("localhost", "127.0.0.1", "::1"))):
        parser.error("use HTTPS or loopback HTTP base URL without credentials, path or query")
    token = os.getenv("AIOPS_INTERNAL_TOKEN") or os.getenv("AIOPS_ADMIN_TOKEN")
    if not token:
        output = {"result": "UNKNOWN", "reason": "TOKEN_NOT_CONFIGURED", "run_id": None,
                  "observed_payments_impact": "UNKNOWN"}
    else:
        try:
            output = qualify(get(args.twin_url, token))
        except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
            output = {"result": "UNKNOWN", "reason": "TWIN_AUTH_READ_FAILED",
                      "error_type": type(exc).__name__, "run_id": None,
                      "observed_payments_impact": "UNKNOWN"}
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0 if output["result"] == "SOURCE_VERIFIED_TWIN_DB_TOPOLOGY_ONLY" else 2


if __name__ == "__main__":
    sys.exit(main())
