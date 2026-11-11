"""Minimal fail-closed Evidence timestamp gate for a future read-only join.

This is deliberately not a Core/GLPI client or an evidence authenticator.
Call ``preflight_then_join`` *before* any authenticated Core/GLPI GET; the
injected join owns source authentication, tenant ACL and link verification.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Callable

_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z"
)
# Evidence timestamps before the Unix epoch are not plausible runtime records.
# Refuse them before any authenticated GET, including year-0001 values that
# Python can convert to UTC without raising OverflowError.
_MIN_EVIDENCE_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


def evidence_timestamps_valid(ledger: object, *, now: datetime | None = None) -> bool:
    """Validate every Core ai-ledger reference before allowing any I/O.

    Reject malformed/naive/pre-epoch/future timestamps and UTC conversion
    overflow at the datetime year boundaries. This is a *syntax and time*
    check only; passing it does not authenticate the ledger or Evidence bytes.
    """
    if not isinstance(ledger, dict) or ledger.get("schema") != "aiops.demo-ledger-read.v1":
        return False
    refs = ledger.get("evidence_refs")
    if not isinstance(refs, list) or not 1 <= len(refs) <= 80:
        return False
    try:
        clock = now if now is not None else datetime.now(timezone.utc)
        # A naive or malformed clock must never inherit the host's timezone.
        if not isinstance(clock, datetime) or clock.utcoffset() is None:
            return False
        clock = clock.astimezone(timezone.utc)
        latest = clock + timedelta(minutes=5)
        for ref in refs:
            if not isinstance(ref, dict):
                return False
            value = ref.get("known_at")
            if not isinstance(value, str) or len(value) > 48 or _TIMESTAMP.fullmatch(value) is None:
                return False
            stamp = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
            stamp_utc = stamp.astimezone(timezone.utc)
            if stamp.utcoffset() is None or stamp_utc < _MIN_EVIDENCE_UTC or stamp_utc > latest:
                return False
    except (ValueError, OverflowError, TypeError):
        return False
    return True


def _unknown() -> dict:
    return {"state": "UNKNOWN", "incident_id": None, "run_id": None,
            "ticket_id": None, "evidence_id": None, "evidence_ids": [],
            "verified_evidence_ids": [], "ticket_verification": "UNKNOWN",
            "evidence_verification": "UNKNOWN"}


def preflight_then_join(ledger: object, *, join_read_only: Callable[[], dict],
                        now: datetime | None = None) -> dict:
    """Short-circuit malformed Evidence before an injected Core/GLPI join.

    ``join_read_only`` must itself authenticate and validate all upstreams;
    this gate never promotes an Evidence or ticket ID. Missing/unverified
    sources remain UNKNOWN. No HTTP client, host or credential is configured.
    """
    if not evidence_timestamps_valid(ledger, now=now):
        return _unknown()
    try:
        result = join_read_only()
    except Exception:
        return _unknown()
    return result if isinstance(result, dict) else _unknown()
