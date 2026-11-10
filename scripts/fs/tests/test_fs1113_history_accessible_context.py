#!/usr/bin/env python3
"""Fail-closed static regression for history chart accessible naming.

This is a source contract check, not Chromium or Debian E2E qualification.
"""
from pathlib import Path

source = Path(__file__).resolve().parents[1].joinpath("fs1097_patch.py").read_text(encoding="utf-8")
start = source.index("async function loadHistory(){")
end = source.index('$("history-refresh").addEventListener', start)
load = source[start:end]
assert 'chart.setAttribute("aria-busy","true")' in load
assert 'chart.setAttribute("aria-label","Historique Prometheus · "+(metric===' in load
assert '+" · "+windowSize+" · chargement")' in load
assert '+" · "+windowSize+" · "+series.length+" séries")' in load
assert 'error?.historyAuthDenied?"Historique Prometheus · accès refusé":"Historique Prometheus · données indisponibles"' in load
assert load.index('const metric=$("history-metric").value') < load.index('+" · "+windowSize+" · chargement")')
assert load.index('if(requestId!==historyRequestId)return;', load.index("const data=await")) < load.index('+" · "+windowSize+" · "+series.length+" séries")')
assert 'if(requestId!==historyRequestId||' in load
print("FS1113_HISTORY_ACCESSIBLE_CONTEXT_STATIC=PASS")
