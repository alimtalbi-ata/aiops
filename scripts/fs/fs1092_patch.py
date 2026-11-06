#!/usr/bin/env python3
"""FS1092: register history as a separate router, preserving FS1051's 3-route invariant."""
import ast,pathlib
main=pathlib.Path("/app/portal/main.py")
history=pathlib.Path("/app/portal/fs1092_history.py")
source=main.read_text()
assert "FS1051_ROUTE_REGISTRATION_MISMATCH" in source
assert "fs1092_history" not in source
assert not history.exists()
body=pathlib.Path("/tmp/fs1089_history_api.py").read_text()
body=body.replace('"""FS1089 read-only bounded Prometheus historical series API."""','"""FS1092 separate bounded Prometheus historical series router."""')
body=body.replace('from fastapi import HTTPException, Request','from fastapi import APIRouter, HTTPException, Request\nfrom portal.fs1051_visual import _check, _fetch, _PROM\nimport urllib.parse\nrouter = APIRouter()')
ast.parse(body)
history.write_text(body)
registration="\n# FS1092: separate history router; FS1051 original route invariant remains intact.\nfrom portal.fs1092_history import router as fs1092_history_router\napp.include_router(fs1092_history_router)\n"
updated=source+registration
ast.parse(updated)
main.write_text(updated)
print("FS1092_ROUTE_SEPARATION=PASS")
