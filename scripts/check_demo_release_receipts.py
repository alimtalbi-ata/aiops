#!/usr/bin/env python3
"""Aggregate *operator-supplied* P0 release receipts, offline and fail-closed.

No network, secrets, deployments, LIVE operations, or independent attestation.
A successful exit means only that the limited receipts are internally reviewable;
it NEVER authorizes promotion or establishes ACME E2E / Debian qualification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import re
import sys
from pathlib import Path

if __package__:
    from .check_demo_evidence_receipts import (
        Blocked, identifier, load_local_json, qualify as qualify_evidence, require,
    )
else:
    from check_demo_evidence_receipts import (
        Blocked, identifier, load_local_json, qualify as qualify_evidence, require,
    )

SCHEMA = "aiops.demo-release-receipt-aggregate.v1"
SHA = re.compile(r"[a-f0-9]{40}\Z")
FIELD_CHECKS = frozenset({
    "core_health", "twin_health", "copilot_health", "portal_health",
    "core_anonymous_noc_denied", "portal_demo_studio_readable",
    "local_applied_sha_consistency",
})


def qualify_release(stable_sha: str, candidate_sha: str, run_id: str,
                    coverage: dict, field: dict, ledger: dict, refs: dict,
                    *, now: datetime | None = None) -> dict:
    """Check consistency, never the truth or independence of supplied receipts."""
    require(isinstance(stable_sha, str) and SHA.fullmatch(stable_sha) is not None
            and isinstance(candidate_sha, str) and SHA.fullmatch(candidate_sha) is not None
            and stable_sha != candidate_sha, "invalid_release_shas")
    identifier(run_id)
    require(isinstance(coverage, dict) and
            coverage.get("schema") == "aiops.demo-stable-deployment-coverage.v1"
            and coverage.get("stable_sha") == stable_sha
            and coverage.get("candidate_sha") == candidate_sha
            and coverage.get("assessment") == "READY_FOR_REVIEW"
            and coverage.get("overall") == "NO_GO"
            and coverage.get("provenance") == "OFFLINE_GIT_DIFF_NOT_RUNTIME"
            and coverage.get("unsupported_count") == 0
            and coverage.get("unsupported_paths") == []
            and coverage.get("field_smoke_tests") == "NOT_TESTED"
            and coverage.get("rollback_test") == "NOT_TESTED",
            "unqualified_transport_receipt")
    matrix = coverage.get("module_deployment_matrix")
    require(isinstance(matrix, list) and bool(matrix)
            and type(coverage.get("changed_count")) is int
            and coverage["changed_count"] == len(matrix)
            and all(isinstance(row, dict) and row.get("decision") == "REVIEWABLE"
                    and row.get("git_status") in ("A", "M") for row in matrix),
            "unqualified_transport_matrix")
    require(isinstance(field, dict)
            and field.get("schema") == "aiops.demo-field-readonly-preflight.v1"
            and field.get("assessment") == "READONLY_PREFLIGHT_PASS"
            and field.get("overall") == "NO_GO"
            and field.get("provenance") == "OPERATOR_LOCAL_READONLY_OBSERVATION_UNATTESTED"
            and field.get("applied_sha_verified") == "MATCH_UNATTESTED"
            and field.get("tenant_rbac") == "NOT_TESTED"
            and field.get("core_temporal_analyst_critic_policy_evidence") == "NOT_TESTED"
            and field.get("run_incident_evidence_correlation") == "NOT_TESTED"
            and field.get("twin_payments_impact") == "NOT_TESTED"
            and field.get("rollback_verified") == "NOT_TESTED",
            "unqualified_field_receipt")
    checks = field.get("checks")
    require(isinstance(checks, dict) and set(checks) == FIELD_CHECKS
            and all(value == "PASS" for value in checks.values()),
            "incomplete_field_checks")
    timestamp = field.get("timestamp_utc")
    require(isinstance(timestamp, str) and len(timestamp) <= 48,
            "invalid_field_timestamp")
    try:
        observed = datetime.fromisoformat(timestamp)
    except (ValueError, OverflowError):
        raise Blocked("invalid_field_timestamp") from None
    current = now if now is not None else datetime.now(timezone.utc)
    require(observed.tzinfo is not None and observed.utcoffset() is not None
            and current.tzinfo is not None and current.utcoffset() is not None
            and current - timedelta(minutes=15) <= observed <= current + timedelta(minutes=5),
            "stale_or_future_field_receipt")
    evidence = qualify_evidence(run_id, ledger, refs)
    require(evidence.get("assessment") == "REFERENTIAL_CHECK_PASS"
            and evidence.get("overall") == "NO_GO"
            and evidence.get("provenance") == "OPERATOR_SUPPLIED_JSON_UNATTESTED"
            and evidence.get("classification") == "SYNTHETIC_ONLY",
            "unqualified_evidence_receipt")
    return {
        "schema": SCHEMA,
        "timestamp_utc": current.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "assessment": "REVIEWABLE_UNATTESTED",
        "overall": "NO_GO",
        "ready_for_stable": "BLOCKED",
        "provenance": "OPERATOR_SUPPLIED_FILES_UNATTESTED",
        "candidate_sha": candidate_sha,
        "checks": {
            "static_transport_matrix": "PASS",
            "loopback_health_and_anonymous_denial": "PASS",
            "local_applied_sha_match_only": "PASS_UNATTESTED",
            "core_portal_synthetic_evidence_join": "PASS_UNATTESTED",
        },
        "run_incident_field_linkage": "NOT_TESTED",
        "temporal_analyst_critic_policy_execution": "NOT_TESTED",
        "policy_critic_origin": "NOT_TESTED",
        "tenant_rbac": "NOT_TESTED",
        "payments_runtime_impact": "NOT_TESTED",
        "independent_evidence_validation": "NOT_TESTED",
        "debian_applied_sha_attestation": "NOT_TESTED",
        "debian_rollback": "NOT_TESTED",
        "promotion_protection_and_approval": "NOT_TESTED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run-id", required=True)
    for name in ("coverage", "field", "ledger", "refs"):
        parser.add_argument("--" + name + "-file", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = qualify_release(
            args.stable_sha, args.candidate_sha, args.run_id,
            *(load_local_json(getattr(args, name + "_file"))
              for name in ("coverage", "field", "ledger", "refs")),
        )
    except (Blocked, ValueError, TypeError, KeyError, AttributeError):
        # Do not disclose paths, IDs, tokens, receipt data or internal exception text.
        result = {"schema": SCHEMA, "assessment": "BLOCKED", "overall": "NO_GO",
                  "ready_for_stable": "BLOCKED", "reason": "unqualified_release_receipts",
                  "field_e2e": "NOT_TESTED"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["assessment"] == "REVIEWABLE_UNATTESTED" else 2


if __name__ == "__main__":
    sys.exit(main())
