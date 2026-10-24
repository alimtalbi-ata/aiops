"""Fail-closed offline reconciliation of STAR checkpoint capture evidence.

A capture is not a runtime attestation. This module never contacts applications.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,95}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ALLOWED = {"ISOLATED_TEST_FIXTURE", "OPERATOR_BROWSER_UNREVIEWED"}


def reconcile_checkpoints(expected: Mapping, captures: list[Mapping]) -> dict:
    """Bind captures to independent canonical identities; refuse partial success."""
    if not isinstance(expected, Mapping) or set(expected) != {"run_id", "correlation_id", "events"}:
        raise ValueError("invalid canonical contract")
    run, corr, events = expected["run_id"], expected["correlation_id"], expected["events"]
    if not all(isinstance(v, str) and _ID.fullmatch(v) for v in (run, corr)):
        raise ValueError("invalid canonical identity")
    if not isinstance(events, Mapping) or not events or any(not isinstance(k, str) for k in events):
        raise ValueError("missing independent event map")
    if not isinstance(captures, list):
        raise ValueError("invalid captures")
    if len(captures) != len(events):
        raise ValueError("missing or extra checkpoints")
    seen = set()
    accepted = []
    for item in captures:
        if not isinstance(item, Mapping):
            raise ValueError("invalid capture")
        required = {"cue", "run_id", "correlation_id", "event_ref", "sha256", "provenance", "qualification"}
        if not required.issubset(item):
            raise ValueError("missing evidence fields")
        cue = item["cue"]
        if not isinstance(cue, str) or cue not in events or cue in seen:
            raise ValueError("unknown or duplicate checkpoint")
        ref = events[cue]
        if not isinstance(ref, str) or not _ID.fullmatch(ref):
            raise ValueError("invalid independent event reference")
        if (item["run_id"], item["correlation_id"], item["event_ref"]) != (run, corr, ref):
            raise ValueError("capture identity mismatch")
        if not isinstance(item["sha256"], str) or not _SHA.fullmatch(item["sha256"]):
            raise ValueError("invalid screenshot checksum")
        if not isinstance(item["provenance"], str) or item["provenance"] not in _ALLOWED or item["qualification"] != "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF":
            raise ValueError("unsupported provenance or claimed qualification")
        for flag in ("runtime_page_authenticated", "business_outcome_verified", "human_approval_authenticated"):
            if item.get(flag) is not False:
                raise ValueError("unsupported attestation")
        seen.add(cue)
        accepted.append({"cue": cue, "event_ref": ref, "sha256": item["sha256"], "provenance": item["provenance"]})
    if seen != set(events):
        raise ValueError("incomplete checkpoint set")
    return {"run_id": run, "correlation_id": corr, "status": "CAPTURES_UNREVIEWED", "checkpoints": accepted}
