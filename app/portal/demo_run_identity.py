"""Fail-closed identity check for read-only ACME Run detail responses.

A registry match is not sufficient if the detail API contradicts it. This
function does not grant tenant authorization or attest LIVE execution.
"""
from collections.abc import Mapping


def matches_demo_run(detail, requested_id, registry_mode):
    if not isinstance(detail, Mapping):
        return False
    run = detail.get("run", detail)
    if not isinstance(run, Mapping):
        return False
    if run.get("run_id") != requested_id:
        return False
    if run.get("mode") != registry_mode:
        return False
    if detail.get("run_id", requested_id) != requested_id:
        return False
    return True
