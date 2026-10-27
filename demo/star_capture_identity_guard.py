"""Strict read-only identity comparison for ACME STAR screenshot evidence.

Pure contract: no network, no identifier generation, no business/HITL attestation.
"""
from __future__ import annotations

import re
from typing import Mapping

_RUN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,95}$")
_EVENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
_KEYS = ("run_id", "correlation_id", "event_ref")


def verify_snapshot_identity(expected: Mapping[str, object],
                             observed: Mapping[str, object]) -> dict[str, object]:
    """Reject absent, malformed or conflicting identifiers without repairing them.

    Both maps must be independently sourced: expected from canonical ingress,
    observed from the exact event page. Caller must NOT fill missing DOM values
    from the expected map. A match is not proof of runtime authenticity.
    """
    for name in _KEYS:
        pattern = _EVENT if name == "event_ref" else _RUN
        lhs, rhs = expected.get(name), observed.get(name)
        if not isinstance(lhs, str) or not pattern.fullmatch(lhs):
            raise ValueError("invalid or missing expected " + name)
        if not isinstance(rhs, str) or not pattern.fullmatch(rhs):
            raise ValueError("invalid or missing observed " + name)
        if lhs != rhs:
            raise ValueError("snapshot identity contradiction: " + name)
    return {
        "identity_consistent": True,
        "run_id": expected["run_id"],
        "correlation_id": expected["correlation_id"],
        "event_ref": expected["event_ref"],
        "runtime_authenticated": False,
        "business_validated": False,
        "human_approval_authenticated": False,
        "live_action_authorized": False,
    }
