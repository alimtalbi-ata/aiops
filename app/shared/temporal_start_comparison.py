"""Strictly compare a decoded Temporal START history input to a Core request.

The caller MUST obtain the input from Temporal's authenticated workflow history,
not from a client-provided JSON object, search attribute or workflow ID.
This pure function is not itself an attestation of provenance or execution.
"""
import hmac
from shared.temporal_start_fingerprint import canonical_start_request


def compare_temporal_start_input(core_request, temporal_input):
    """Return MATCH, MISMATCH or UNKNOWN; never an execution authorization."""
    if not isinstance(core_request, dict) or not isinstance(temporal_input, dict):
        return "UNKNOWN"
    keys = {"run_id", "mode", "scenario_id", "version"}
    if set(core_request) != keys or set(temporal_input) != keys:
        return "UNKNOWN"
    try:
        expected = canonical_start_request(**core_request)
        observed = canonical_start_request(**temporal_input)
    except (TypeError, ValueError):
        return "UNKNOWN"
    return "MATCH" if hmac.compare_digest(expected, observed) else "MISMATCH"
