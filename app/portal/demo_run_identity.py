"""Check contradictions in the existing Core Run detail response contract.

The registry remains the mode filter. Core detail historically omits run_id
and/or mode; absence is not proof of identity, and this check is not tenant ACL.
Reject only explicit contradictions, without breaking qualified V2.8 fixtures.
"""
from collections.abc import Mapping


def matches_demo_run(detail, requested_id, registry_mode):
    if not isinstance(detail, Mapping):
        return False
    run = detail.get("run", detail)
    if not isinstance(run, Mapping):
        return False
    for value in (detail.get("run_id"), run.get("run_id")):
        if value is not None and value != requested_id:
            return False
    if run.get("mode") is not None and run["mode"] != registry_mode:
        return False
    return True
