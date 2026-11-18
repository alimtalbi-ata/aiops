"""Offline source inspection only: never import or execute proposed modules."""
import ast
import hashlib
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "docs/qualification/int10c/source-review-manifest.json").read_text())
EXPECTED = {
    "runner_composition.py.proposed", "linux_child_supervision.py.proposed",
    "watchdog_policy.py.proposed", "cgroup_cleanup.py.proposed",
    "placement_admission.py.proposed", "source_static_check.py.proposed",
}

def test_manifest_coverage():
    assert MANIFEST["commit"] == "1116aecb133c24395420eebd2035fafff5ef22df"
    assert len(MANIFEST["inputs"]) == len(EXPECTED)
    assert {Path(i["path"]).name for i in MANIFEST["inputs"]} == EXPECTED

@pytest.mark.parametrize("entry", MANIFEST["inputs"], ids=lambda e: Path(e["path"]).name)
def test_exact_bytes_and_ast(entry):
    path = Path(entry["path"])
    assert path.parent == Path("docs/qualification/int10c")
    assert path.name in EXPECTED
    raw = (ROOT / path).read_bytes()
    assert len(raw) == entry["bytes"]
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
    assert hashlib.sha1(f"blob {len(raw)}".encode() + bytes([0]) + raw).hexdigest() == entry["blob"]
    tree = ast.parse(raw.decode("ascii"), filename=str(path))
    assert all(isinstance(n, (ast.Expr, ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))
               for n in tree.body)
    assert all(isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
               for n in tree.body if isinstance(n, ast.Expr))
