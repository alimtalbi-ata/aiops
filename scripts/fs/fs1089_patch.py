#!/usr/bin/env python3
"""Append bounded history endpoint to the existing registered visual router."""
import ast,pathlib
p=pathlib.Path("/app/portal/fs1051_visual.py")
extra=pathlib.Path("/tmp/fs1089_history_api.py").read_text()
source=p.read_text()
assert '"/api/fs1089/prometheus/history"' not in source
assert 'router = APIRouter()' in source
updated=source+"\n\n"+extra
ast.parse(updated)
p.write_text(updated)
print("FS1089_API_PATCH=PASS")
