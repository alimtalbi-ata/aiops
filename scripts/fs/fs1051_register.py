"""Append an additive route registration; fail closed on unexpected main source."""
from pathlib import Path
p=Path("/app/portal/main.py")
s=p.read_text()
if "fs1051_visual" in s:
    raise SystemExit("FS1051_ALREADY_REGISTERED")
if "FastAPI(" not in s or "app =" not in s or "include_router" not in s:
    raise SystemExit("FS1051_UNKNOWN_PORTAL_MAIN")
s += "\n# FS.1051: additive read-only visual dashboard\nfrom portal.fs1051_visual import router as fs1051_visual_router\napp.include_router(fs1051_visual_router)\n"
p.write_text(s)
print("FS1051_REGISTERED=PASS")
