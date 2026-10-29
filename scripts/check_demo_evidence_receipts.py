#!/usr/bin/env python3
"""Compare two operator-supplied synthetic JSON read receipts, offline.

This checks *referential consistency*, not source truth, tenant RBAC, E2E,
Debian attestation, or that the two receipts came from independent services.
Never reads credentials or performs network/deployment operations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import re
import stat
import sys
from pathlib import Path

SCHEMA = "aiops.demo-evidence-offline-receipt.v1"
MAX_BYTES = 131072
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
MODES = frozenset({"DEMO", "REPLAY", "STORY"})
DECISIONS = frozenset({"SIMULATE", "HUMAN_APPROVAL", "ESCALATE", "BLOCK", "OBSERVE"})
STATES = frozenset({"PASS", "BLOCKED", "UNKNOWN"})


class Blocked(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise Blocked(reason)


def identifier(value: object) -> str:
    require(isinstance(value, str) and ID.fullmatch(value) is not None, "invalid_identity")
    return value


def unique_ids(value: object, *, allow_empty: bool = False) -> set[str]:
    require(isinstance(value, list) and len(value) <= 80, "invalid_evidence_ids")
    result = [identifier(item) for item in value]
    require(len(result) == len(set(result)) and (allow_empty or bool(result)), "duplicate_or_empty_evidence_ids")
    return set(result)


def records(value: object, *, maximum: int = 50) -> list[dict]:
    require(isinstance(value, list) and 0 < len(value) <= maximum
            and all(isinstance(item, dict) for item in value), "invalid_records")
    return value


def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    output = {}
    for key, value in pairs:
        require(key not in output, "duplicate_json_key")
        output[key] = value
    return output


def invalid_constant(_value: str):
    raise Blocked("invalid_json_constant")


def load_local_json(path: Path) -> dict:
    """Reject final symlinks/devices, large inputs, and detectable concurrent writes."""
    require(path.is_absolute() and hasattr(os, "O_NOFOLLOW"), "unsafe_receipt_path")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and 1 <= before.st_size <= MAX_BYTES,
                    "invalid_receipt_file")
            content = os.read(fd, MAX_BYTES + 1)
            after = os.fstat(fd)
        finally:
            os.close(fd)
    except OSError:
        raise Blocked("unreadable_receipt_file") from None
    require(len(content) == before.st_size and all(
        getattr(before, field) == getattr(after, field)
        for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    ), "receipt_changed_during_read")
    try:
        data = json.loads(content.decode("utf-8"), object_pairs_hook=no_duplicate_keys,
                          parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise Blocked("invalid_receipt_json") from None
    require(isinstance(data, dict), "invalid_receipt_json")
    return data


def qualify(run_id: str, ledger: dict, refs: dict) -> dict:
    identifier(run_id)
    require(isinstance(ledger, dict) and isinstance(refs, dict), "invalid_receipts")
    require(set(ledger) == {"schema", "run_id", "mode", "classification", "source",
                            "tenant_acl_qualified", "runtime_attested", "analyses",
                            "critiques", "evidence_classification", "event_link_verified",
                            "evidence_refs", "policy_decisions"}, "invalid_portal_fields")
    require(ledger.get("schema") == "aiops.demo-ledger-read.v1"
            and ledger.get("run_id") == run_id
            and ledger.get("mode") in MODES
            and ledger.get("classification") == "DEMO_CORE_RECORDED_NOT_LIVE"
            and ledger.get("source") == "CORE_AI_LEDGER_INTERNAL_READ"
            and ledger.get("tenant_acl_qualified") is False
            and ledger.get("runtime_attested") is False
            and ledger.get("evidence_classification") == "SYNTHETIC_ONLY"
            and ledger.get("event_link_verified") is True,
            "unqualified_portal_projection")
    require(set(refs) == {"schema", "run_id", "classification", "tenant_acl_qualified",
                          "runtime_attested", "event_link_verified", "items"}
            and refs["schema"] == "aiops.core-demo-evidence-refs.v1"
            and refs["run_id"] == run_id
            and refs["classification"] == "SYNTHETIC_ONLY"
            and refs["tenant_acl_qualified"] is False
            and refs["runtime_attested"] is False
            and refs["event_link_verified"] is True,
            "unqualified_core_references")
    reference_items = records(refs["items"], maximum=80)
    reference_map = {}
    for item in reference_items:
        require(set(item) == {"evidence_id", "source", "payload_sha256", "known_at"},
                "invalid_reference_fields")
        eid = identifier(item["evidence_id"])
        require(eid not in reference_map, "duplicate_reference")
        require(isinstance(item["known_at"], str) and len(item["known_at"]) <= 48,
                "invalid_reference_timestamp")
        require(isinstance(item["source"], str) and SOURCE.fullmatch(item["source"]) is not None
                and isinstance(item["payload_sha256"], str)
                and SHA256.fullmatch(item["payload_sha256"]) is not None,
                "invalid_reference_metadata")
        try:
            known = datetime.fromisoformat(item["known_at"])
        except (ValueError, TypeError, OverflowError):
            raise Blocked("invalid_reference_timestamp") from None
        require(known.tzinfo is not None and known.utcoffset() is not None
                and known.astimezone(timezone.utc) <= datetime.now(timezone.utc) + timedelta(minutes=5),
                "unqualified_reference_timestamp")
        reference_map[eid] = item
    require(0 < len(reference_map) <= 80, "invalid_reference_count")
    portal_refs = ledger.get("evidence_refs")
    require(isinstance(portal_refs, list) and len(portal_refs) == len(reference_map),
            "portal_core_reference_mismatch")
    seen = set()
    for item in portal_refs:
        require(isinstance(item, dict), "invalid_portal_reference")
        eid = identifier(item.get("evidence_id"))
        require(eid not in seen and item == reference_map.get(eid), "portal_core_reference_mismatch")
        seen.add(eid)

    analyses = {}
    for item in records(ledger.get("analyses")):
        require(set(item) == {"analysis_id", "model", "status", "evidence_ids"}
                and isinstance(item["model"], str) and len(item["model"]) <= 160
                and isinstance(item["status"], str) and len(item["status"]) <= 32,
                "invalid_analysis_fields")
        aid = identifier(item.get("analysis_id"))
        require(aid not in analyses, "duplicate_analysis")
        analyses[aid] = unique_ids(item.get("evidence_ids"))
    require(set().union(*analyses.values()) == set(reference_map), "analysis_reference_mismatch")
    critiques = set()
    for item in records(ledger.get("critiques")):
        require(set(item) == {"critique_id", "analysis_id", "model", "validated",
                              "evidence_ids", "claim_checks"}
                and isinstance(item["model"], str) and len(item["model"]) <= 160
                and isinstance(item["claim_checks"], list)
                and len(item["claim_checks"]) <= 50, "invalid_critique_fields")
        cid = identifier(item.get("critique_id"))
        aid = identifier(item.get("analysis_id"))
        require(cid not in critiques and aid in analyses and type(item.get("validated")) is bool,
                "unqualified_critique")
        critiques.add(cid)
        cited = unique_ids(item.get("evidence_ids"))
        require(cited.issubset(analyses[aid]), "cross_analysis_evidence")
        for check in item.get("claim_checks", []):
            require(isinstance(check, dict)
                    and set(check) == {"claim", "supported", "supporting_evidence_ids"}
                    and isinstance(check["claim"], str) and len(check["claim"]) <= 500
                    and type(check.get("supported")) is bool, "invalid_claim_check")
            supporting = unique_ids(check.get("supporting_evidence_ids"), allow_empty=True)
            require(supporting.issubset(cited) and (not check["supported"] or bool(supporting)),
                    "unlinked_claim_support")
    policies = set()
    simulate_pass = False
    for item in records(ledger.get("policy_decisions")):
        require(set(item) == {"policy_decision_id", "decision", "state"},
                "invalid_policy_fields")
        pid = identifier(item.get("policy_decision_id"))
        require(pid not in policies, "duplicate_policy_decision")
        policies.add(pid)
        require(item.get("decision") in DECISIONS and item.get("state") in STATES,
                "unsafe_policy_disposition")
        simulate_pass |= item["decision"] == "SIMULATE" and item["state"] == "PASS"
    require(simulate_pass, "missing_recorded_simulate_pass")
    return {
        "schema": SCHEMA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "assessment": "REFERENTIAL_CHECK_PASS",
        "overall": "NO_GO",
        "classification": "SYNTHETIC_ONLY",
        "provenance": "OPERATOR_SUPPLIED_JSON_UNATTESTED",
        "checks": {"same_run_id": "PASS", "synthetic_reference_join": "PASS",
                   "per_analysis_critique_citations": "PASS", "recorded_policy_simulate_pass": "PASS"},
        "incident_id_correlation": "NOT_TESTED",
        "temporal_execution": "NOT_TESTED",
        "policy_critic_linkage_origin": "NOT_TESTED",
        "tenant_rbac": "NOT_TESTED",
        "payments_runtime_impact": "NOT_TESTED",
        "independent_evidence_validation": "NOT_TESTED",
        "debian_deployment_and_rollback": "NOT_TESTED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ledger-file", type=Path, required=True)
    parser.add_argument("--refs-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = qualify(args.run_id, load_local_json(args.ledger_file),
                         load_local_json(args.refs_file))
    except (Blocked, ValueError, TypeError, KeyError, AttributeError):
        result = {"schema": SCHEMA, "assessment": "BLOCKED", "overall": "NO_GO",
                  "reason": "unqualified_synthetic_receipts", "field_e2e": "NOT_TESTED"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["assessment"] == "REFERENTIAL_CHECK_PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
