"""Read only an explicitly selected synthetic Core run on an isolated loopback lab."""
import re
from bounded_http_transport import get_json

IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}")

def read_run(port, token, run_id):
    if type(port) is not int or not 1024 <= port <= 65535 or port in {7770,7777,7790}:
        raise ValueError("invalid isolated lab port")
    if not isinstance(token, str) or not 32 <= len(token) <= 256 or not token.isascii() or any(c.isspace() or ord(c)<33 or ord(c)>126 for c in token):
        raise ValueError("invalid internal token")
    if not isinstance(run_id, str) or not IDENT.fullmatch(run_id):
        raise ValueError("invalid run identity")
    data = get_json(port, token, "/api/noc/runs/" + run_id)
    run = data["run"]
    if (data.get("data_classification") != "SYNTHETIC_CANONICAL_RUN"
        or data.get("live_remediation_authorized") is not False
        or data.get("tenant_acl_qualified") is not False
        or data.get("runtime_authenticated") is not False
        or run.get("run_id") != run_id
        or run.get("mode") not in ("DEMO","REPLAY","STORY")
        or not isinstance(run.get("incident_id"),str)
        or not IDENT.fullmatch(run["incident_id"])
        or not isinstance(run.get("status"),str) or not run["status"]):
        raise ValueError("unverified synthetic Core run")
    return {"classification":"SYNTHETIC_CANONICAL_RUN",
            "run": {k:run[k] for k in ("run_id","incident_id","mode","status")},
            "tenant_acl_qualified":False, "policy":"DENY",
            "rca":"UNKNOWN", "production_authorized":False}
