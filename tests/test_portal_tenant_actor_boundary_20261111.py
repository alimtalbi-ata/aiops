"""Fail-closed source guard until Core implements server-derived tenant/actor scope.

These assertions intentionally do NOT qualify any live tenant access. A future
positive read contract requires separate authenticated cross-tenant tests.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "app/portal/main.py"
CORE = ROOT / "app/core/main.py"


def _endpoint_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    return ast.get_source_segment(source, node) or ""


def test_portal_bootstrap_remains_denied_without_tenant_actor_contract():
    endpoint = _endpoint_source(PORTAL, "bootstrap")
    assert "_require_portal_read_auth(authorization)" in endpoint
    assert "TENANT_ACL_NOT_QUALIFIED" in endpoint
    assert "status_code=503" in endpoint
    assert "read_portal_snapshot(" not in endpoint
    assert "get_json(" not in endpoint


def test_legacy_core_read_endpoints_are_not_misrepresented_as_tenant_scoped():
    dashboard = _endpoint_source(CORE, "dashboard")
    runs = _endpoint_source(CORE, "list_runs")
    assert "from aiops.runs" in dashboard
    assert "from aiops.runs" in runs
    assert "limit 100" in runs.lower()
    # These legacy functions do not accept actor/tenant identity and must not
    # be used as authorization evidence for the browser read-model.
    for endpoint in (dashboard, runs):
        signature = endpoint.split(":", 1)[0]
        assert "tenant" not in signature.lower()
        assert "actor" not in signature.lower()
