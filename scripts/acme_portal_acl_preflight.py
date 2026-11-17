"""Fail-closed authorization readiness check for ACME Portal presentation.

Source inspection only. It does not prove runtime ACL or protect routes.
"""
from __future__ import annotations
import ast
from pathlib import Path

REQUIRED = ("tenant_id", "attempt_id", "run_id")


def assess_portal_acl(source: str, *, tenant_authority_attested: bool = False):
    """Never infer viewer authorization from an internal bearer or a source route."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"status": "NO_GO", "reason": "PORTAL_SOURCE_INVALID"}
    # Directly importing the offline-only policy/read seam into a Portal
    # entrypoint is an unsafe integration signal, not ACL qualification.
    offline_modules = ("scripts.acme_evidence_read_seam",
                       "scripts.acme_viewer_access_policy")
    unsafe_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            unsafe_imports.update(alias.name for alias in node.names
                                  if alias.name in offline_modules)
        elif isinstance(node, ast.ImportFrom):
            if node.module in offline_modules:
                unsafe_imports.add(node.module)
    get_routes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (isinstance(decorator, ast.Call) and
                    isinstance(decorator.func, ast.Attribute) and
                    decorator.func.attr == "get" and decorator.args and
                    isinstance(decorator.args[0], ast.Constant) and
                    isinstance(decorator.args[0].value, str)):
                get_routes.append(decorator.args[0].value)
    # A code-level boolean supplied by a caller is NOT an attestation of an
    # actual authenticated actor+tenant+exact-run decision.
    return {
        "status": "NO_GO",
        "reason": "VIEWER_TENANT_RUN_ACL_NOT_ATTESTED",
        "source_get_routes": sorted(set(get_routes)),
        "requirements": list(REQUIRED),
        "internal_bearer_is_viewer_acl": False,
        "unsafe_offline_policy_imports": sorted(unsafe_imports),
        "attestation_claim_ignored": bool(tenant_authority_attested),
    }


def main():
    import json
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("app/portal/main.py")
    print(json.dumps(assess_portal_acl(path.read_text(encoding="utf-8")),
                     sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
