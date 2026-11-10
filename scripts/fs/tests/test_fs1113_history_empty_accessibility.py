#!/usr/bin/env python3
"""Regression: an empty Prometheus history must not retain its loading name."""
import ast
from pathlib import Path

patch = Path(__file__).resolve().parents[1] / "fs1097_patch.py"
source = patch.read_text(encoding="utf-8")
ast.parse(source)
assert 'if(!points.length)' in source
empty = source.split('if(!points.length)', 1)[1].split('const width=900', 1)[0]
assert 'Aucune série avec points disponibles.' in empty
assert 'chart.setAttribute("aria-label"' in empty
assert 'aucune donnée disponible' in empty
assert 'metric==="availability"' in empty
assert 'windowSize' in empty
assert 'return}' in empty
assert 'if(requestId===historyRequestId){chart.setAttribute("aria-busy","false")' in source
print("PASS: empty history accessible name reflects metric/window/empty state")
