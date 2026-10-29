#!/usr/bin/env python3
"""Read-only ACME demo source preflight. No Docker, network, secrets or writes."""
from __future__ import annotations
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
checks = []

def check(label, condition, detail=""):
    checks.append((label, bool(condition), detail))
    print(("PASS" if condition else "FAIL") + " | " + label + ((" | " + detail) if detail else ""))

def source(path):
    p = ROOT / path
    if not p.is_file():
        check("source exists: " + path, False)
        return ""
    try:
        s = p.read_text(encoding="utf-8")
        ast.parse(s, filename=path) if p.suffix == ".py" else None
    except (SyntaxError, UnicodeError, OSError) as exc:
        check("parse: " + path, False, type(exc).__name__)
        return ""
    check("source exists and parses: " + path, True)
    return s

sim = source("app/simulator/main.py")
worker = source("app/worker/main.py")
policy = source("app/policy/main.py")
core = source("app/core/main.py")
twin = source("app/twin/main.py")
evidence = source("app/evidence/main.py")
qualification = source("app/portal/qualification_lab.py")
source("app/core/demo_evidence_read.py")
source("app/shared/tenant_scope.py")
source("tests/test_p0_policy_consolidated.py")
source("tests/test_p0_twin_consolidated.py")

check("simulator rejects LIVE", "if mode not in ('DEMO','REPLAY','STORY')" in sim)
check("simulator launch creates incident and run",
      all(x in sim for x in ("'/api/incidents'", "'/api/runs'", "/execute")))
check("worker synthetic policy command non-effect",
      "'command':('OBSERVE' if mode in ('DEMO','REPLAY','STORY') else 'EXECUTE')" in worker)
check("worker records synthetic provenance without observed_at",
      "'observed_at':None" in worker and "'observed':False" in worker)
check("worker invokes Analyst and Critic",
      "/api/intelligence/analyze" in worker and "/api/intelligence/critic" in worker)
check("worker persists Policy verdict", "/api/runs/{rid}/policy-record" in worker)
check("policy retains LIVE effect deny",
      "LIVE_EFFECTS_NOT_QUALIFIED" in policy)
check("policy requires independent Critic and confidence threshold",
      "if not x.critic_validated:" in policy and "if x.confidence < 0.90:" in policy)
check("policy synthetic verdict is SIMULATE",
      '"decision": "SIMULATE"' in policy)
check("core persists proposals but does not authorize execution",
      "/api/runs/{rid}/proposals" in core and "'execution_allowed':False" in core)
check("chaos and smoke preview exists",
      'MODES=("simple","complex","chaos","smoke_screen")' in qualification)
check("runtime E2E script exists", (ROOT / "tests/runtime-e2e.sh").is_file())
check("ACME offline demo documentation exists",
      (ROOT / "docs/ACME-DEMO-RUNBOOK-V2114.md").is_file())
check("evidence Prometheus endpoint exists", '@app.get("/metrics")' in evidence or "@app.get('/metrics')" in evidence)
check("Twin impact marks runtime state unknown",
      "'runtime_impact_state':'UNKNOWN'" in twin or "'runtime_impact_state': 'UNKNOWN'" in twin)
print()
print("NOTE | Static source checks only. No running container, real AI, GLPI,")
print("NOTE | remediation simulation, database, Temporal or E2E verified.")
failed = sum(not ok for _, ok, _ in checks)
print(f"ACME_OFFLINE_PREFLIGHT={'FAIL' if failed else 'PASS'} | checks={len(checks)} | failed={failed}")
sys.exit(1 if failed else 0)
