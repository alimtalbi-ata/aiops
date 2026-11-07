#!/usr/bin/env python3
"""FS1134 integration: real Intelligence call_model + HTTP provider stub + event KPI aggregation.
No live DB, external LLM or production mutation. Provider responses are deterministic fixtures.
"""
import json
import pathlib
import sys
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/"app"))
from intelligence import main as intel
from intelligence import llm_telemetry as telemetry
from portal.kpi_views import metrics

class Response:
    def __init__(self, content, usage=None, status=200):
        self.content=content
        self.usage=usage
        self.status_code=status
    def json(self):
        result={"choices":[{"message":{"content":json.dumps(self.content)}}]}
        if self.usage is not None:result["usage"]=self.usage
        return result
    def raise_for_status(self):
        if self.status_code>=400:raise intel.requests.HTTPError("mock HTTP failure")

def analyst():
    return {"classification":"storage","severity":"P2","severity_rationale":"synthetic fixture",
            "hypotheses":[{"id":"h1","statement":"degraded path","confidence":0.6,"supporting_evidence_ids":["EV-1"]}],
            "confidence":0.6,"confidence_basis":"synthetic evidence"}

def critic():
    return {"validated":False,"issues":[{"code":"UNSUPPORTED_CLAIM","description":"fixture requires human review"}],
            "claim_checks":[{"claim":"degraded path","supported":False}],
            "diagnostic_confidence":0.4,"final_recommendation":"HUMAN_APPROVAL"}

def invoke(schema, responses):
    telemetry.reset()
    pending=iter(responses)
    def post(*args,**kwargs):
        return next(pending)
    with patch.object(intel,"BASE","http://fake-provider/v1"),patch.object(intel,"MODEL","fixture-model"),patch.object(intel.requests,"post",side_effect=post):
        result=intel.call_model("system",{"synthetic":True},schema)
    return result,telemetry.snapshot()

analysis,usage_a=invoke(intel.Analyst,[Response(analyst(),{"prompt_tokens":100,"completion_tokens":40,"total_tokens":140})])
assert analysis.confidence==0.6
assert usage_a["attempts"]==1 and usage_a["total_tokens"]==140
assert usage_a["calls"][0]["duration_ms"]>=0
assert usage_a["calls"][0]["status"]=="http_200"
critique,usage_c=invoke(intel.Critique,[Response(critic(),{"prompt_tokens":200,"completion_tokens":30,"total_tokens":230})])
assert critique.validated is False and usage_c["total_tokens"]==230
# Critic schema error triggers one bounded provider repair; usage must include BOTH calls.
invalid=critic()
invalid["claim_checks"][0]["forbidden_extra"]="must repair"
critique2,usage_repair=invoke(intel.Critique,[
    Response(invalid,{"prompt_tokens":220,"completion_tokens":40,"total_tokens":260}),
    Response(critic(),{"prompt_tokens":260,"completion_tokens":50,"total_tokens":310})])
assert critique2.validated is False
assert usage_repair["attempts"]==2 and usage_repair["total_tokens"]==570
# Missing provider usage on one retry invalidates totals, not a fabricated partial sum.
_,partial=invoke(intel.Critique,[
    Response(invalid,{"prompt_tokens":220,"completion_tokens":40,"total_tokens":260}),
    Response(critic())])
assert partial["attempts"]==2 and partial["total_tokens"] is None
# Simulate the canonical run event shape produced by Worker and consumed by Portal.
events=[
    {"event_type":"ANALYST_COMPLETED","payload":{"llm_telemetry":usage_a}},
    {"event_type":"CRITIC_COMPLETED","payload":{"llm_telemetry":usage_repair}},
]
run={"run_id":"FS1134-fixture","status":"BLOCKED","started_at":"2026-11-07T12:00:00Z","completed_at":"2026-11-07T12:00:30Z"}
data=metrics([run],{run["run_id"]:{"events":events,"stages":[]}})
assert data["llm_tokens"]=={"analyst":140,"critic":570},data
assert data["llm_median_ms"]["analyst"] is not None
assert data["llm_p95_ms"]["critic"] is not None
assert data["statuses"]["BLOCKED"]==1
# No raw prompt, API secret, or model output in telemetry.
assert "synthetic fixture" not in json.dumps(usage_a)
print("FS1134_RESULT=PASS")
print("FS1134_ASSERTIONS=PROVIDER_HTTP_ANALYST_CRITIC_REPAIR_TOKENS_MISSING_USAGE_RUN_EVENT_PORTAL_KPI")
print("FS1134_PROVIDER=DETERMINISTIC_MOCK_NOT_REAL_LLM")
print("FS1134_PRODUCTION_MUTATION=NONE")
