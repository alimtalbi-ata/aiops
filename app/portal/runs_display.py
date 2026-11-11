"""Bounded, explicit Runs projection for the legacy read-only Portal cockpit.

This is presentation-only: never asserts tenant ACL, provenance, or LIVE status.
The caller remains responsible for authorization before obtaining source rows.
"""
from collections.abc import Mapping

MAX_COCKPIT_RUNS = 100


def cockpit_runs_projection(runs):
    """Return at most 100 rows and an explicit count of omitted source rows.

    Reject malformed source envelopes rather than silently claiming an empty
    or complete list. Values remain untrusted and must be HTML-escaped by the
    Portal's existing table renderer.
    """
    if not isinstance(runs, list) or any(not isinstance(run, Mapping) for run in runs):
        raise ValueError("invalid runs collection")
    shown = runs[:MAX_COCKPIT_RUNS]
    rows = [
        (
            run.get("run_id", "UNKNOWN"),
            run.get("mode", "UNKNOWN"),
            run.get("status", "UNKNOWN"),
            run.get("scenario_id", "UNKNOWN"),
        )
        for run in shown
    ]
    return rows, len(runs) - len(shown)
