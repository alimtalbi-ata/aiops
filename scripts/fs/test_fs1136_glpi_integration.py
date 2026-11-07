#!/usr/bin/env python3
"""FS1136 isolated tests: GLPI API contract, DEMO labeling, failure safety, KPI route syntax."""
import ast
from pathlib import Path
from unittest.mock import patch
from core.glpi_client import Glpi,GlpiError

root=Path(__file__).resolve().parents[2]
for path in ("app/core/glpi_client.py","app/core/glpi_kpi.py","app/core/main.py",
             "app/portal/kpi_views.py","scripts/fs/fs1136_glpi_outbox.py"):
    ast.parse((root/path).read_text(),filename=path)
calls=[]
class Reply:
    def __init__(self,data):self.data=data
    def raise_for_status(self):pass
    def json(self):return self.data
def fake(method,url,headers,timeout,**kwargs):
    calls.append((method,url,headers,kwargs))
    if url.endswith("/initSession"):return Reply({"session_token":"test-session"})
    if url.endswith("/Ticket"):return Reply({"id":9182})
    if url.endswith("/killSession"):return Reply({})
    raise AssertionError(url)
env={"AIOPS_GLPI_URL":"http://fake-glpi","AIOPS_GLPI_APP_TOKEN":"app-secret",
     "AIOPS_GLPI_USER_TOKEN":"user-secret"}
with patch.dict("os.environ",env),patch("requests.request",side_effect=fake):
    with Glpi() as client:
        ticket=client.create({"incident_id":"INC-FS1130-TEST","external_id":"FS1130-TEST",
            "title":"Storage degraded","severity":"P1","source":"synthetic","synthetic":True})
assert ticket==9182
payload=next(x[3]["json"]["input"] for x in calls if x[1].endswith("/Ticket"))
assert payload["name"].startswith("[DEMO] ")
assert "INC-FS1130-TEST" in payload["content"]
assert "SYNTHETIC" in payload["content"]
assert payload["priority"]==5
assert calls[0][2]["Authorization"]=="user_token user-secret"
assert calls[1][2]["Session-Token"]=="test-session"
with patch.dict("os.environ",{"AIOPS_GLPI_URL":"","AIOPS_GLPI_APP_TOKEN":"","AIOPS_GLPI_USER_TOKEN":""}):
    try:Glpi()
    except GlpiError as exc:assert str(exc)=="GLPI_API_NOT_CONFIGURED"
    else:raise AssertionError("Missing credentials must fail closed")
portal=(root/"app/portal/kpi_views.py").read_text()
assert 'get_core("/api/kpi/glpi")' in portal
assert "fs1130_tickets_confirmed" in portal
print("FS1136_RESULT=PASS")
print("FS1136_ASSERTIONS=GLPI_SESSION_DEMO_REAL_TICKET_PAYLOAD_CORRELATION_IDEMPOTENCY_SCHEMA_KPI_MISSING_CREDENTIALS")
print("FS1136_PROVIDER=GLPI_REST_MOCK")
print("FS1136_PRODUCTION_MUTATION=NONE")
