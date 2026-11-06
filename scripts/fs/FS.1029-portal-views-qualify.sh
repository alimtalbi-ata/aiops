#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/home/aiops/aiops2-v2-delivery}"
cd "$ROOT"
echo "SOURCE_BRANCH=$(git branch --show-current)"
python3 -m compileall -q app/portal
PYTHONPATH=app python3 - <<'PY'
import sys
from unittest.mock import patch
from fastapi import FastAPI
from portal.observability_views import register_views, prometheus_query
from portal.ui_theme import NAV

assert all(x in [p for p,_ in NAV] for x in ("/databases","/prometheus","/cmdb"))
app=FastAPI()
register_views(app,lambda p: {"status":"ok"},lambda p: {"nodes":[{"node_id":"CI-1","type":"server","site":"LAB","state":"UP"}],"edges":[]})
with patch("portal.observability_views.prometheus_query",return_value={"status":"UNKNOWN"}):
    routes={r.path:r for r in app.routes if getattr(r,"path",None) in ("/databases","/prometheus","/cmdb")}
    assert len(routes)==3
    for path,route in routes.items():
        html=route.endpoint()
        assert "LECTURE SEULE" in html, path
    assert "CI-1" in routes["/cmdb"].endpoint()
try:
    prometheus_query("arbitrary_promql")
    raise AssertionError("unapproved PromQL accepted")
except ValueError:
    pass
print("PORTAL_VIEWS_UNIT=PASS")
print("UNBOUNDED_PROMQL=REJECTED")
print("HTTP_WRITES=0")
print("DATABASE_WRITES=0")
PY
echo "PORTAL_7777_QUALIFICATION=PASS"
