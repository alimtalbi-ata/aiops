#!/usr/bin/env python3
"""Dependency-free FS1132 offline KPI report regression tests."""
import json
import pathlib
import sys
import tempfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from fs1132_kpi_report import analyze,percentile

assert percentile([10,20,30,40,50],.95)==48.0
assert percentile([],.95) is None
with tempfile.TemporaryDirectory() as tmp:
    path=pathlib.Path(tmp)/"FS1130-fixture.jsonl"
    records=[
        {"type":"start","campaign":"FS1130-fixture","target":3},
        {"type":"result","status":"RESOLVED","elapsed_seconds":10,"analysis":1,"critique":1,"policy":1,"evidence":1,"effects":0},
        {"type":"result","status":"BLOCKED","elapsed_seconds":20,"analysis":1,"critique":1,"policy":1,"evidence":1,"effects":0},
        {"type":"result","status":"FAILED","elapsed_seconds":30,"analysis":0,"critique":0,"policy":0,"evidence":1,"effects":0,"error":"upstream timeout"},
        {"type":"summary","campaign":"FS1130-fixture","submitted":3,"completed":3},
    ]
    path.write_text("\n".join(json.dumps(x) for x in records)+"\n")
    report=analyze(path)
    assert report["resolved"]==1 and report["blocked"]==1 and report["failed"]==1
    assert report["median_elapsed_seconds"]==20 and report["p95_elapsed_seconds"]==29
    assert report["with_analysis"]==2 and report["with_evidence"]==3
    assert report["total_tokens"] is None and report["analyst_model_latency_ms"] is None
    path.write_text("\n".join(json.dumps(x) for x in records[:-1]))
    try:analyze(path)
    except ValueError:pass
    else:raise AssertionError("incomplete campaign must fail closed")
print("FS1132_RESULT=PASS")
print("FS1132_ASSERTIONS=P95_STATUS_COVERAGE_TOKENS_MISSING_INCOMPLETE_REJECTED")
