"""Build-time patch of exact deployed explorer module. No runtime monkeypatch."""
import ast
import hashlib
from pathlib import Path

target = Path("/app/portal/explorer_api.py")
expected = "222439c2b81877d1cb5925f817263270629985d1de41e38be8db72ee7f2b9dc4"
source = target.read_text()
actual = hashlib.sha256(source.encode()).hexdigest()
if actual != expected:
    raise SystemExit(f"FS1040_SOURCE_PARITY=FAIL actual={actual}")
tree = ast.parse(source)
functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_safe_query"]
if len(functions) != 1:
    raise SystemExit("FS1040_SAFE_QUERY_NOT_UNIQUE")
fn = functions[0]
if len(fn.args.args) != 1 or fn.args.args[0].arg != "sql":
    raise SystemExit("FS1040_SAFE_QUERY_SIGNATURE_MISMATCH")
lines = source.splitlines(keepends=True)
replacement = (
    "def _safe_query(sql):\n"
    "    from portal.sql_readonly_guard import validate_select\n"
    "    try:\n"
    "        return validate_select(sql)\n"
    "    except ValueError:\n"
    "        raise HTTPException(400, \"only_single_select_allowed\")\n"
)
patched = "".join(lines[:fn.lineno-1]) + replacement + "".join(lines[fn.end_lineno:])
ast.parse(patched)
target.write_text(patched)
print("FS1040_SOURCE_PARITY=PASS")
print("FS1040_PATCHED_SHA256="+hashlib.sha256(patched.encode()).hexdigest())
