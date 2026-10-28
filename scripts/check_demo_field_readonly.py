#!/usr/bin/env python3
"""Operator-side read-only preflight for an explicitly forwarded loopback endpoint set.

No deployment, POST, secrets, redirects, DNS, production address or LIVE claims.
The receipt never constitutes E2E qualification, even if every probe succeeds.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import os
import stat
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

SCHEMA = "aiops.demo-field-readonly-preflight.v1"
LIMIT = 131072
COMPONENTS = ("core", "twin", "copilot", "portal")


class UnsafeEndpoint(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_base(raw: str) -> str:
    if not isinstance(raw, str) or not re.fullmatch(r"http://(?:127\.0\.0\.1|\[::1\]):[0-9]{1,5}", raw):
        raise UnsafeEndpoint("endpoint_not_literal_loopback_http")
    parsed = urlsplit(raw)
    try:
        port = parsed.port
        address = ipaddress.ip_address(parsed.hostname or "")
    except ValueError:
        raise UnsafeEndpoint("invalid_loopback_port_or_address") from None
    if port is None or not 1 <= port <= 65535 or not address.is_loopback:
        raise UnsafeEndpoint("invalid_loopback_port_or_address")
    return raw


def read_http(opener, base: str, path: str, accept: str) -> tuple[int, str, bytes]:
    request = Request(base + path, method="GET", headers={
        "Accept": accept, "Cache-Control": "no-store",
    })
    try:
        with opener.open(request, timeout=3) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read(LIMIT + 1)
    except HTTPError as exc:
        # Never read or emit error bodies, URLs or exception strings.
        return exc.code, "", b""
    except (URLError, TimeoutError, OSError, ValueError):
        return 0, "", b""


def verify_local_applied_sha(path: str, expected_sha: str) -> str:
    """Compare an explicitly selected local receipt; never authenticate its origin.

    The file is not a signature or independent Debian attestation. Do not
    follow a final symlink, read devices, or disclose its path or contents.
    """
    if (not isinstance(path, str) or not os.path.isabs(path)
            or not isinstance(expected_sha, str)
            or not re.fullmatch(r"[0-9a-f]{40}", expected_sha)
            or not hasattr(os, "O_NOFOLLOW")):
        return "BLOCKED"
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or not 40 <= before.st_size <= 41:
                return "BLOCKED"
            data = os.read(fd, 42)
            after = os.fstat(fd)
        finally:
            os.close(fd)
    except (OSError, ValueError):
        return "BLOCKED"
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        return "BLOCKED"
    encoded = expected_sha.encode("ascii")
    return "MATCH_UNATTESTED" if data in (encoded, encoded + b"\n") else "BLOCKED"


def qualify(endpoints: dict[str, str], applied_sha_status: str = "NOT_TESTED") -> dict:
    # Validate every destination before issuing any request.
    bases = {name: validate_base(endpoints[name]) for name in COMPONENTS}
    if applied_sha_status not in ("NOT_TESTED", "MATCH_UNATTESTED", "BLOCKED"):
        raise UnsafeEndpoint("invalid_applied_sha_status")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    checks: dict[str, str] = {}
    if applied_sha_status != "NOT_TESTED":
        checks["local_applied_sha_consistency"] = (
            "PASS" if applied_sha_status == "MATCH_UNATTESTED" else "BLOCKED"
        )
    for name, base in bases.items():
        code, ctype, body = read_http(opener, base, "/health", "application/json")
        try:
            data = json.loads(body) if code == 200 and len(body) <= LIMIT and "application/json" in ctype.lower() else None
        except (ValueError, UnicodeError):
            data = None
        checks[name + "_health"] = (
            "PASS" if isinstance(data, dict) and data.get("status") == "ok"
            and data.get("component") == name else "BLOCKED"
        )

    # This is a negative authorization check, not tenant-RBAC certification.
    code, _, _ = read_http(opener, bases["core"], "/api/noc/runs/SMOKE-UNAUTH", "application/json")
    checks["core_anonymous_noc_denied"] = "PASS" if code == 401 else "BLOCKED"

    code, ctype, body = read_http(opener, bases["portal"], "/demo-studio", "text/html")
    checks["portal_demo_studio_readable"] = (
        "PASS" if code == 200 and len(body) <= LIMIT
        and "text/html" in ctype.lower() and b"ACME Demo Studio" in body else "BLOCKED"
    )
    return {
        "schema": SCHEMA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provenance": "OPERATOR_LOCAL_READONLY_OBSERVATION_UNATTESTED",
        "assessment": "READONLY_PREFLIGHT_PASS" if all(x == "PASS" for x in checks.values()) else "BLOCKED",
        "overall": "NO_GO",
        "checks": checks,
        "tenant_rbac": "NOT_TESTED",
        "core_temporal_analyst_critic_policy_evidence": "NOT_TESTED",
        "run_incident_evidence_correlation": "NOT_TESTED",
        "twin_payments_impact": "NOT_TESTED",
        "applied_sha_verified": applied_sha_status,
        "rollback_verified": "NOT_TESTED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in COMPONENTS:
        parser.add_argument("--" + name + "-url", required=True)
    parser.add_argument("--expected-sha", help="Approved 40-hex Git commit (no remote lookup)")
    parser.add_argument("--applied-sha-file", help="Explicit absolute local applied.sha path")
    args = parser.parse_args(argv)
    try:
        if bool(args.expected_sha) != bool(args.applied_sha_file):
            raise UnsafeEndpoint("applied_sha_pair_required")
        applied = (verify_local_applied_sha(args.applied_sha_file, args.expected_sha)
                   if args.expected_sha else "NOT_TESTED")
        if applied == "BLOCKED":
            result = {"schema": SCHEMA, "assessment": "BLOCKED", "overall": "NO_GO",
                      "reason": "applied_sha_unreadable_or_mismatch",
                      "applied_sha_verified": "BLOCKED", "field_e2e": "NOT_TESTED"}
        else:
            result = qualify({name: getattr(args, name + "_url") for name in COMPONENTS}, applied)
    except (UnsafeEndpoint, KeyError) as exc:
        result = {"schema": SCHEMA, "assessment": "BLOCKED", "overall": "NO_GO",
                  "reason": str(exc), "field_e2e": "NOT_TESTED"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["assessment"] == "READONLY_PREFLIGHT_PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
