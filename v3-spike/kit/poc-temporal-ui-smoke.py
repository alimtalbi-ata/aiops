"""Read the actual synthetic Temporal workflow through the optional Web UI HTTP API."""
import hashlib
import json
import re
import sys
import time
import urllib.request
from urllib.parse import urlsplit

origin,receipt_file=sys.argv[1:]
url=urlsplit(origin)
if url.scheme!="http" or url.hostname!="127.0.0.1" or not url.port or url.port in (7770,7777,7790) or url.path or url.query or url.fragment or url.username or url.password:
    raise ValueError("Dedicated loopback URL required")
with open(receipt_file) as f: expected=json.load(f)
rid=expected["run_id"]
assert re.fullmatch(r"RUN-[A-F0-9]{16}",rid)
assert expected["classification"]=="V3_TEMPORAL_BOUNDARY_RUNTIME" and expected["result"]=="PASS" and expected["core_status"]=="BLOCKED" and expected["production_authorized"] is False
def get(path):
    with urllib.request.urlopen(origin+path,timeout=5) as r:
        assert r.status==200 and urlsplit(r.geturl()).netloc==url.netloc
        return r.read()
for attempt in range(45):
    try:
        page=get("/")
        assert b"<html" in page.lower() or b"<!doctype html" in page.lower()
        info=json.loads(get("/api/v1/namespaces/default/workflows/"+rid))
        execution=info["workflowExecutionInfo"]
        assert execution["execution"]["workflowId"]==rid
        assert execution["type"]["name"]=="V3BoundaryWorkflow"
        assert execution["status"] in ("WORKFLOW_EXECUTION_STATUS_COMPLETED","Completed")
        run_id=execution["execution"]["runId"]
        assert re.fullmatch(r"[a-f0-9-]{36}",run_id)
        break
    except (OSError,ValueError,KeyError,AssertionError):
        if attempt==44: raise
        time.sleep(2)
# UI transport may use the explicit execution route rather than the SDK route.
# Require actual event history and the same completed execution; no list-only fallback.
paths=[f"/api/v1/namespaces/default/workflows/{rid}/history?execution.runId={run_id}",
       f"/api/v1/namespaces/default/workflows/{rid}/executions/{run_id}/history"]
last=None
for path in paths:
    try:
        data=json.loads(get(path))
        events=data["history"]["events"]
        assert not data.get("nextPageToken")
        assert len(events)==expected["history_events"]
        types=[e["eventType"] for e in events]
        assert sum(t in ("EVENT_TYPE_ACTIVITY_TASK_COMPLETED","ActivityTaskCompleted") for t in types)==2
        assert types[-1] in ("EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED","WorkflowExecutionCompleted")
        break
    except (OSError,ValueError,KeyError,AssertionError) as err:
        last=err
else: raise RuntimeError("UI history not verified") from last
print(json.dumps({"classification":"V3_TEMPORAL_UI_READBACK","result":"PASS","workflow_id":rid,
                  "temporal_run_id":run_id,"history_events":len(events),"activity_completions":2,
                  "event_type_sha256":hashlib.sha256(json.dumps(types).encode()).hexdigest(),
                  "core_business_state":"BLOCKED","production_authorized":False},sort_keys=True))
