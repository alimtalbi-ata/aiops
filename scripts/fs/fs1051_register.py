"""Register FS1051 visual routes additively; avoid assuming a specific main.py layout."""
import ast
from pathlib import Path

p = Path("/app/portal/main.py")
s = p.read_text(encoding="utf-8")
tree = ast.parse(s)
if "fs1051_visual_router" in s:
    raise SystemExit("FS1051_ALREADY_REGISTERED")

# Only accept a module-level app binding; never replace the existing application.
found = any(
    (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "app" for t in node.targets))
    or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "app")
    for node in tree.body
)
if not found:
    raise SystemExit("FS1051_APP_BINDING_NOT_FOUND")

addition = (
    "\n# FS.1051 — additive read-only dashboard routes\n"
    "from portal.fs1051_visual import router as fs1051_visual_router\n"
    "app.include_router(fs1051_visual_router)\n"
)
ast.parse(s + addition)
p.write_text(s + addition, encoding="utf-8")
print("FS1051_REGISTERED=PASS")
