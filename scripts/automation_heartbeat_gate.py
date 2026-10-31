#!/usr/bin/env python3
"""Offline evidence-only missed-run gate. Never invokes a scheduler or a runtime."""
import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

UTC = dt.timezone.utc
VALID_PLANES = {"debian", "github", "chatgpt", "lab"}


def parse_time(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return stamp.astimezone(UTC)


def evaluate(snapshot, now, grace_seconds=300):
    if snapshot.get("schema_version") != "aiops.automation-heartbeat.v1":
        raise ValueError("unsupported heartbeat schema")
    entries = snapshot.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("nonempty entries required")
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
    if type(grace_seconds) is not int or grace_seconds < 0:
        raise ValueError("grace_seconds must be a nonnegative integer")
    seen = set()
    results = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("entry must be object")
        ident = item.get("id")
        plane = item.get("plane")
        if not isinstance(ident, str) or not ident or plane not in VALID_PLANES:
            raise ValueError("invalid id or plane")
        key = (plane, ident)
        if key in seen:
            raise ValueError("duplicate plane/id")
        seen.add(key)
        enabled = item.get("enabled")
        if enabled is not None and type(enabled) is not bool:
            raise ValueError("enabled must be boolean or null")
        cadence = item.get("cadence_seconds")
        if cadence is not None and (type(cadence) is not int or cadence < 1):
            raise ValueError("cadence_seconds must be a positive integer or null")
        last = parse_time(item.get("last_success_at"))
        next_run = parse_time(item.get("next_run_at"))
        evidence = item.get("evidence_ref")
        receipt_path = item.get("receipt_path")
        receipt_sha256 = item.get("receipt_sha256")
        state = item.get("state", "UNKNOWN")
        problems = []
        if state == "UNATTESTED" or enabled is None:
            problems.append("UNATTESTED")
        if enabled is False:
            problems.append("INACTIVE")
        if enabled is True:
            if last is None:
                problems.append("NO_SUCCESS_EVIDENCE")
            elif last > now + dt.timedelta(seconds=grace_seconds):
                problems.append("CLOCK_SKEW")
            elif cadence is not None and (now - last).total_seconds() > cadence + grace_seconds:
                problems.append("MISSED_RUN")
            if cadence is not None and next_run is None:
                problems.append("NEXT_UNKNOWN")
            if next_run is not None and next_run < now - dt.timedelta(seconds=grace_seconds):
                problems.append("NEXT_OVERDUE")
            if (not isinstance(evidence, str) or not evidence.strip()) and not receipt_path:
                problems.append("EVIDENCE_MISSING")
            if receipt_path is not None or receipt_sha256 is not None:
                if (not isinstance(receipt_path, str) or not receipt_path
                        or not isinstance(receipt_sha256, str)
                        or re.fullmatch(r"[0-9a-f]{64}", receipt_sha256) is None):
                    problems.append("RECEIPT_HASH_MISMATCH")
                else:
                    try:
                        receipt = Path(receipt_path)
                        if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > 65536:
                            raise OSError("receipt is not a bounded regular file")
                        digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
                        if digest != receipt_sha256:
                            problems.append("RECEIPT_HASH_MISMATCH")
                    except OSError:
                        problems.append("RECEIPT_HASH_MISMATCH")
        if plane == "lab" and state != "SYNTHETIC":
            problems.append("LAB_PROVENANCE_UNKNOWN")
        level = "FAIL" if any(p in problems for p in ("MISSED_RUN", "NEXT_OVERDUE", "CLOCK_SKEW", "RECEIPT_HASH_MISMATCH")) else "WARN" if problems else "PASS"
        results.append({"plane": plane, "id": ident, "level": level, "signals": problems})
    overall = "FAIL" if any(x["level"] == "FAIL" for x in results) else "WARN" if any(x["level"] == "WARN" for x in results) else "PASS"
    return {"schema_version": snapshot["schema_version"], "checked_at": now.isoformat().replace("+00:00", "Z"), "overall": overall, "entries": results}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="JSON evidence snapshot, or - for stdin")
    p.add_argument("--now", help="UTC ISO-8601 for reproducible tests")
    p.add_argument("--grace-seconds", type=int, default=300)
    args = p.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        now = parse_time(args.now) if args.now else dt.datetime.now(UTC)
        result = evaluate(json.loads(raw), now, args.grace_seconds)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"overall": "FAIL", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return {"PASS": 0, "WARN": 1, "FAIL": 2}[result["overall"]]


if __name__ == "__main__":
    sys.exit(main())
