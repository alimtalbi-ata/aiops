"""Fail-closed FS147 read-only bridge boundary; host supplies authenticated transport."""
from collections.abc import Mapping

def observe_fs147(request, *, fetch_observation):
    if request.mode != "DEMO" or request.ticket_id != 147:
        raise ValueError("invalid FS147 scope")
    payload = dict(tenant_id=request.tenant_id, actor_id=request.actor_id,
                   incident_id=request.incident_id, run_id=request.run_id,
                   ticket_id=147, filesystem="/fs-lab", commands=["df", "du", "ls"])
    response = fetch_observation(payload)
    if not isinstance(response, Mapping):
        raise ValueError("missing bridge observation")
    for field in ("tenant_id", "actor_id", "incident_id", "run_id", "ticket_id"):
        if (type(response.get(field)) is not type(payload[field])
                or response.get(field) != payload[field]):
            raise ValueError("bridge identity mismatch: " + field)
    if (response.get("source") != "fs-lab-bridge-readonly"
            or response.get("filesystem") != "/fs-lab"
            or response.get("commands") != ["df", "du", "ls"]
            or response.get("read_only") is not True
            or not isinstance(response.get("evidence_id"), str)
            or not response["evidence_id"].strip()):
        raise ValueError("untrusted bridge provenance")
    return dict(response)
