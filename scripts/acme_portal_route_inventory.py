#!/usr/bin/env python3
"""Static inventory of ACME demo Portal routes; no HTTP, browser, or service access.

Routes found in source are NOT proof of deployment, tenant ACL or UI selectors.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys

SCENE_CANDIDATES = {
    "noc": ("/", "/demo-studio"),
    "signals": ("/timeline", "/qualification-lab"),
    "twin": ("/twin", "/demo-studio"),
    "analyst_critic": ("/demo-studio/run/{rid}",),
    "policy_hitl": ("/policy", "/policy-control", "/policy-story"),
    "itsm_worker": (),  # No verified SIM-GLPI worker receipt view.
    "timeline": ("/timeline", "/demo-studio/run/{rid}"),
}
SOURCE = Path("app/portal/main.py")


def routes_from_source(source: str):
    tree = ast.parse(source)
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr != "get" or not decorator.args:
                continue
            root = decorator.func.value
            if not isinstance(root, ast.Name) or root.id != "app":
                continue
            path = decorator.args[0]
            if isinstance(path, ast.Constant) and isinstance(path.value, str):
                found.add(path.value)
    return sorted(found)


def inventory(source: str):
    routes = routes_from_source(source)
    records = []
    for scene, candidates in SCENE_CANDIDATES.items():
        existing = [path for path in candidates if path in routes]
        records.append({
            "scene": scene, "source_routes": existing,
            "source_route_present": bool(existing),
            "selector": "NOT_VERIFIED",
            "browser_execution": "NOT_TESTED",
            "deployed_route": "NOT_VERIFIED",
            "status": "SOURCE_ROUTE_CANDIDATE_ONLY" if existing else "NOT_IMPLEMENTED",
        })
    return {
        "schema": "aiops.acme-portal-route-inventory.v1",
        "source": str(SOURCE),
        "evidence_level": "STATIC_SOURCE_ONLY",
        "scenes": records,
        "workbench_qualification_route_in_source": "/acme-workbench" in routes,
        "workbench_qualification_browser_verified": False,
        "seven_scenes_browser_qualified": False,
        "live": "NO_GO",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    args = parser.parse_args(argv)
    try:
        if args.source.stat().st_size > 2_000_000:
            raise ValueError("source too large")
        result = inventory(args.source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError, ValueError):
        print(json.dumps({"schema": "aiops.acme-portal-route-inventory.v1",
                          "status": "NO_GO", "reason": "SOURCE_UNREADABLE", "live": "NO_GO"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if all(item["source_route_present"] for item in result["scenes"]) else 2


if __name__ == "__main__":
    sys.exit(main())
