#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "FS1133_MODE=ISOLATED_TELEMETRY_QUALIFICATION"
echo "FS1133_PRODUCTION_MUTATION=NONE"
docker run --rm -i -v "$ROOT:/src:ro" -w /src python:3.12-slim sh -c '
set -eu
python -m pip install -q "fastapi>=0.110" "pydantic>=2" "requests>=2" "httpx2"
PYTHONPATH=/src/app python -' <<'PY'
import ast
from pathlib import Path
from unittest.mock import patch
from time import perf_counter
for path in ("app/intelligence/main.py","app/intelligence/llm_telemetry.py","app/worker/main.py","app/portal/kpi_views.py"):
    ast.parse(Path(path).read_text(),filename=path)
from intelligence import llm_telemetry as t
from portal.kpi_views import metrics
class FakeResponse:
    def json(self):return {"usage":{"prompt_tokens":12,"completion_tokens":8,"total_tokens":20}}
t.reset()
t.record(perf_counter(),FakeResponse())
t.record(perf_counter(),FakeResponse())
a=t.snapshot()
assert a["attempts"]==2 and a["total_tokens"]==40 and a["prompt_tokens"]==24,a
t.reset()
t.record(perf_counter())
assert t.snapshot()["total_tokens"] is None
runs=[{"run_id":"R1","status":"BLOCKED","started_at":"2026-11-07T12:00:00Z","completed_at":"2026-11-07T12:00:20Z"}]
details={"R1":{"stages":[{"stage":"DGX_ANALYST","started_at":"2026-11-07T12:00:00Z","completed_at":"2026-11-07T12:00:05Z"}],
"events":[{"event_type":"ANALYST_COMPLETED","payload":{"llm_telemetry":{"duration_ms":900,"total_tokens":40}}},
{"event_type":"CRITIC_COMPLETED","payload":{"llm_telemetry":{"duration_ms":1000,"total_tokens":None}}}]}}
m=metrics(runs,details)
assert m["analyst_median_seconds"]==5,m
assert m["llm_tokens"]["analyst"]==40 and m["llm_tokens"]["critic"] is None,m
assert m["llm_p95_ms"]["critic"]==1000,m
print("FS1133_RESULT=PASS")
print("FS1133_ASSERTIONS=SYNTAX_USAGE_ATTEMPTS_MISSING_TOKENS_PERSISTED_EVENT_KPI")
PY
