"""Canonical Core start-request fingerprint; never an execution attestation.

A digest identifies the exact requested start tuple only. It does not prove
Temporal accepted, executed, or received those arguments.
"""
import hashlib
import json
import re

_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_MODES = frozenset({"DEMO", "REPLAY", "STORY", "LIVE"})


def canonical_start_request(run_id, mode, scenario_id, version):
    for value in (run_id, scenario_id):
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise ValueError("invalid start identifier")
    if not isinstance(mode, str) or mode not in _MODES:
        raise ValueError("invalid start mode")
    if type(version) is not int or version < 0:
        raise ValueError("invalid start version")
    return json.dumps(
        {"mode": mode, "run_id": run_id, "scenario_id": scenario_id,
         "version": version},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def start_request_digest(run_id, mode, scenario_id, version):
    """Return an untrusted comparison digest, NOT a Temporal proof."""
    return hashlib.sha256(
        b"aiops2/core-start-request/v1\x00"
        + canonical_start_request(run_id, mode, scenario_id, version)
    ).hexdigest()
