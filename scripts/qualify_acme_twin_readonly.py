#!/usr/bin/env python3
"""Fail-closed read-only qualification of the *seeded* Twin ACME impact contract.

This does not attest Debian, CMDB provenance, a tenant ACL, or Payments outage.
Only HTTP GET to an explicit loopback Twin is allowed; no redirect is followed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = "ACME-SAN-FABRIC-A"
PATH = (
    "ACME-SAN-FABRIC-A", "ACME-STO-PURE01", "ACME-VM-PAY01",
    "ACME-APP-ORACLEPAY", "ACME-SVC-PAYMENTS", "ACME-BIZ-PAYMENTS",
)
DEPTHS = {
    "ACME-SAN-FABRIC-A": 0, "ACME-STO-PURE01": 1,
    "ACME-STO-POWERMAX01": 1, "ACME-VM-PAY01": 2,
    "ACME-VM-PAY02": 2, "ACME-APP-ERP": 2,
    "ACME-APP-ORACLEPAY": 3, "ACME-SVC-ERP": 3,
    "ACME-SVC-PAYMENTS": 4, "ACME-BIZ-PAYMENTS": 5,
}
# Exact IDs/directions from db/migrations/005_seed_acme.sql, not inferred edges.
EDGES = (
    ("ACME-E01", "ACME-BIZ-PAYMENTS", "ACME-SVC-PAYMENTS", "USES"),
    ("ACME-E02", "ACME-SVC-PAYMENTS", "ACME-APP-ORACLEPAY", "DEPENDS_ON"),
    ("ACME-E04", "ACME-APP-ORACLEPAY", "ACME-VM-PAY01", "RUNS_ON"),
    ("ACME-E05", "ACME-APP-ORACLEPAY", "ACME-VM-PAY02", "RUNS_ON"),
    ("ACME-E06", "ACME-VM-PAY01", "ACME-STO-PURE01", "USES"),
    ("ACME-E07", "ACME-VM-PAY02", "ACME-STO-PURE01", "USES"),
    ("ACME-E08", "ACME-STO-PURE01", "ACME-SAN-FABRIC-A", "PATH"),
    ("ACME-E14", "ACME-SVC-ERP", "ACME-APP-ERP", "DEPENDS_ON"),
    ("ACME-E15", "ACME-APP-ERP", "ACME-STO-POWERMAX01", "USES"),
    ("ACME-E16", "ACME-STO-POWERMAX01", "ACME-SAN-FABRIC-A", "PATH"),
)
CHAIN_EDGES = ("ACME-E08", "ACME-E06", "ACME-E04", "ACME-E02", "ACME-E01")
BLOCKERS = (
    "TENANT_RBAC_NOT_QUALIFIED",
    "DEBIAN_TWIN_NOT_TESTED",
    "CMDB_AND_RUNTIME_IMPACT_NOT_ATTESTED",
    "SAN_HOST_LINK_ABSENT_FROM_SEED",
    "CORE_COPILOT_POLICY_EVIDENCE_E2E_NOT_TESTED",
    "DEPLOY_COVERAGE_AND_ROLLBACK_NOT_QUALIFIED",
)


class QualificationError(ValueError):
    """Fixed diagnostic code, never a token, URL, or remote response body."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise QualificationError(code)


def validate_impact(data: object) -> dict:
    """Validate a Twin HTTP response as a seeded graph, never as an outage."""
    require(type(data) is dict, "invalid_json_shape")
    require(data.get("root") == ROOT, "wrong_root")
    require(data.get("traversal_direction") == "REVERSE_CONSUMER_TO_DEPENDENCY",
            "wrong_traversal")
    require(data.get("affected_semantics") == "DEPENDENT_CANDIDATES_NOT_CONFIRMED_IMPACT"
            and data.get("path_semantics") ==
            "SEEDED_TOPOLOGY_SHORTEST_HOPS_NOT_RUNTIME_CAUSALITY",
            "invalid_semantics")
    require(data.get("provenance") == "TWIN_DB_TOPOLOGY_READ_ONLY"
            and data.get("runtime_impact_state") == "UNKNOWN"
            and data.get("runtime_authenticated") is False
            and data.get("tenant_acl_qualified") is False
            and data.get("redundancy_evaluated") is False
            and data.get("live_remediation_authorized") is False,
            "false_runtime_or_acl_attestation")
    require(data.get("max_depth") == 8, "unexpected_depth_limit")
    affected = data.get("affected")
    require(type(affected) is list and len(affected) == len(DEPTHS),
            "affected_count_mismatch")
    seen = {}
    for item in affected:
        require(type(item) is dict and type(item.get("node_id")) is str
                and type(item.get("depth")) is int, "malformed_affected")
        node = item["node_id"]
        require(node not in seen, "duplicate_node")
        seen[node] = item["depth"]
    require(seen == DEPTHS, "seeded_reachability_mismatch")
    edges = data.get("shortest_path_edges")
    require(type(edges) is list and len(edges) == len(EDGES), "edge_count_mismatch")
    actual = []
    for edge in edges:
        require(type(edge) is dict and all(type(edge.get(k)) is str for k in
                ("edge_id", "source_id", "target_id", "relation_type")),
                "malformed_edge")
        actual.append(tuple(edge[k] for k in
                            ("edge_id", "source_id", "target_id", "relation_type")))
    require(tuple(actual) == EDGES, "seeded_edge_provenance_mismatch")
    require(all(DEPTHS[src] == DEPTHS[dst] + 1 for _, src, dst, _ in actual),
            "non_shortest_edge")
    # A VM also depends on a host (ACME-E10); that does NOT make the host
    # reachable from SAN-A. Never label this as SAN -> host -> VM.
    require("ACME-SRV-RHEL01" not in seen and "ACME-SAN-FABRIC-B" not in seen,
            "invented_host_or_fabric")
    return {
        "schema": "aiops.acme-twin-readonly-qualification.v1",
        "scope": "SEEDED_TWIN_TOPOLOGY_ONLY",
        "contract_status": "PASS",
        "overall": "NO_GO",
        "provenance": "SIMULATED_TOPOLOGY_NOT_RUNTIME_IMPACT",
        "root": ROOT,
        "topological_candidates": len(seen),
        "path_nodes": list(PATH),
        "path_edge_ids": list(CHAIN_EDGES),
        "san_host_link_verified": False,
        "runtime_impact_state": "UNKNOWN",
        "blockers": list(BLOCKERS),
    }


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate JSON keys at any depth, including nested edge IDs."""
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_twin_json_key")
        result[key] = value
    return result


def _reject_nonfinite_json(_value: str) -> None:
    raise QualificationError("nonfinite_twin_json")


def decode_impact_json(raw: bytes) -> object:
    """Strict UTF-8 JSON: ambiguous or non-finite topology is never qualified."""
    try:
        return json.loads(raw.decode("utf-8"),
                          object_pairs_hook=_unique_json_object,
                          parse_constant=_reject_nonfinite_json)
    except QualificationError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise QualificationError("invalid_json") from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def loopback_base(url: str) -> str:
    # urlsplit strips some control characters; reject non-canonical input first.
    require(type(url) is str and re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{0,4}/?", url) is not None,
            "invalid_loopback_url")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise QualificationError("invalid_loopback_url") from None
    require(parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
            and port is not None and 0 < port <= 65535
            and not parsed.username and not parsed.password
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment,
            "invalid_loopback_url")
    return "http://127.0.0.1:" + str(port)


def read_impact(base: str, token: str | None) -> tuple[int, object | None]:
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    request = Request(base + "/api/twin/impact/" + ROOT,
                      headers=headers, method="GET")
    try:
        # Explicitly ignore HTTP(S)_PROXY/ALL_PROXY so the bearer never
        # reaches an ambient proxy, even if NO_PROXY is empty.
        response = build_opener(ProxyHandler({}), NoRedirect).open(request, timeout=4)
    except HTTPError as exc:
        if exc.code == 401:
            require(exc.headers.get("Cache-Control") == "no-store"
                    and exc.headers.get("WWW-Authenticate") == "Bearer",
                    "invalid_anonymous_denial")
            return 401, None
        raise QualificationError("unexpected_http_status") from None
    except (URLError, TimeoutError, OSError):
        raise QualificationError("twin_unreachable") from None
    with response:
        require(response.status == 200, "unexpected_http_status")
        require(response.headers.get("Cache-Control") == "no-store",
                "missing_no_store")
        require(response.headers.get_content_type() == "application/json",
                "invalid_content_type")
        raw = response.read(256 * 1024 + 1)
    require(len(raw) <= 256 * 1024, "oversized_response")
    return 200, decode_impact_json(raw)


def qualify(base_url: str, token: str) -> dict:
    base = loopback_base(base_url)
    require(type(token) is str and bool(token.strip())
            and token == token.strip() and len(token) <= 4096
            and all(32 <= ord(char) <= 126 for char in token),
            "invalid_token")
    anonymous_status, _ = read_impact(base, None)
    require(anonymous_status == 401, "anonymous_topology_not_denied")
    authenticated_status, data = read_impact(base, token)
    require(authenticated_status == 200, "authorized_read_denied")
    return validate_impact(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loopback Twin topology qualification")
    parser.add_argument("--base-url", required=True,
                        help="Ephemeral Twin loopback, e.g. http://127.0.0.1:811")
    args = parser.parse_args(argv)
    try:
        result = qualify(args.base_url, os.environ.get("AIOPS_TWIN_READ_TOKEN", ""))
    except QualificationError as exc:
        result = {
            "schema": "aiops.acme-twin-readonly-qualification.v1",
            "scope": "SEEDED_TWIN_TOPOLOGY_ONLY",
            "contract_status": "BLOCKED", "overall": "NO_GO",
            "reason": str(exc), "blockers": list(BLOCKERS),
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
