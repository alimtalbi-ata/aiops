#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "FS1131_MODE=ISOLATED_READ_ONLY_KPI_PAGE_TEST"
echo "FS1131_PRODUCTION_MUTATION=NONE"
docker run --rm -i -v "$ROOT:/src:ro" -w /src python:3.12-slim sh -c '
python -m pip install -q "fastapi>=0.110" "pydantic>=2" "requests>=2" &&
PYTHONPATH=/src/app python -' <<'PY'
import sys,types,datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal.kpi_views import metrics,register_kpi_views
now="2026-11-07T12:00:00+00:00"
end="2026-11-07T12:00:20+00:00"
runs=[{"run_id":"RUN-A","scenario_id":"FS1130-CASE-01","status":"BLOCKED","created_at":now,"started_at":now,"completed_at":end},
      {"run_id":"RUN-B","scenario_id":"OTHER","status":"RESOLVED"}]
details={"RUN-A":{"stages":[{"stage":"ANALYZE","started_at":now,"completed_at":end},{"stage":"CRITIQUE","started_at":now,"completed_at":end}]}}
m=metrics(runs[:1],details)
assert m["total"]==1 and m["terminal"]==1 and m["median_seconds"]==20 and m["analyst_median_seconds"]==20,m
app=FastAPI()
def get_core(path):
 if path=="/api/runs":return {"items":runs}
 if path=="/api/runs/RUN-A":return details["RUN-A"]
 raise AssertionError(path)
register_kpi_views(app,get_core)
client=TestClient(app)
r=client.get("/kpi")
assert r.status_code==200,r.status_code
assert "Runs FS1130 visibles" in r.text
assert "NON MESURÉ" in r.text
assert "Tokens et coût IA" in r.text
assert "BLOCKED" in r.text
assert "OTHER" not in r.text
print("FS1131_RESULT=PASS")
print("FS1131_ASSERTIONS=CORE_FILTER_TIMINGS_TERMINAL_STATES_MISSING_TOKENS_READ_ONLY_ROUTE")
PY
'
