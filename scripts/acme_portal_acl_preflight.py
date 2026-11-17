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
