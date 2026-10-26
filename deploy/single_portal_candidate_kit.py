#!/usr/bin/env python3
"""Create an offline, non-deployable single-portal candidate kit from a pinned Git tree.

Only an explicitly reviewed source subset is embedded. All other eligible
tracked source paths are represented by SHA-256 references to the pinned commit.
No Docker, network, runtime, or application APIs are called.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

APPROVED = (
    ".github/workflows/acme-v21315-fixture-validation.yml",
    "demo/integrations/v21315/README.md",
    "demo/integrations/v21315/acme-fixtures.json",
    "demo/integrations/v21315/validate_fixture.py",
    "docs/demo/AIOPS-V21315-FIXTURE-GRAPH-VALIDATION-20261026.md",
    "docs/demo/AIOPS-V21315-PORTAL-IMPACT-READ-MODEL-20261026.md",
    "tests/test_acme_fixture_validation.py",
    "tests/test_portal_acme_impact_read_model.py",

    ".github/workflows/star-offline-chromium-real-render.yml",
    "app/portal/main.py",
    "app/portal/acme_impact_read_model.py",
    "app/portal/platform_registry.py",
    "app/portal/platform_registry_router.py",
    "app/portal/portal_demo_public_v21310.py",
    "app/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html",
    "deploy/single_portal_candidate_kit.py",
    "deploy/verify_single_portal_candidate_kit.py",
    "demo/noc_browser_evidence_gate.py",
    "demo/noc_evidence_index.py",
    "demo/noc_platform_registry.py",
    "demo/noc_portal_integration.py",
    "demo/noc_star_cue_map.py",
    "demo/noc_star_event_binding.py",
    "demo/noc_star_trace_bundle.py",
    "demo/star_capture_identity_guard.py",
    "demo/star_n8n_identity_gate.py",
    "demo/star_png_integrity.py",
    "demo/star_snapshot_browser.py",
    "docs/architecture/AIOPS-SINGLE-PORTAL-COMPONENT-CONSOLIDATION.md",
    "docs/architecture/AIOPS-SINGLE-PORTAL-RUNTIME-DEMO-INTEGRATION.md",
    "docs/release/AIOPS-SINGLE-PORTAL-CANDIDATE-20261025.md",
    "docs/release/AIOPS-PORTAL-ROUTE-INVENTORY-20261025.md",
    "docs/recovery/HISTORICAL-CODE-REGISTRY-20261023.md",
    "docs/recovery/OCTOBER-2026-ARCHIVE-CONTEXT-AND-REUSE.md",
    "tests/test_noc_browser_workflow_contract.py",
    "tests/test_noc_portal_integration.py",
    "tests/test_portal_demo_public_v21310.py",
    "tests/test_platform_registry_portal_route.py",
    "tests/test_star_n8n_identity_gate.py",
)
ROOTS = {"app", "demo", "deploy", "recovery", "integration", "tests", "docs",
         "config", "schemas", "db", "tools", ".github"}
EXTENSIONS = {".py", ".sh", ".md", ".yml", ".yaml", ".toml", ".sql", ".json", ".html"}
EXCLUDED_PARTS = {".git", "backups", "secrets", "sessions", "exports", "captures",
                  "screenshots", "credentials", "__pycache__", "node_modules",
                  "dist", "reports", ".venv", "venv"}
SENSITIVE = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    rb"(?i:ghp_[a-z0-9]{20,}|github_pat_[a-z0-9_]{30,}|"
    rb"sk-[a-z0-9]{24,}|xox[baprs]-[a-z0-9-]{20,}|"
    rb"AKIA[0-9A-Z]{16})"
)
FIXED_TIME = (2026, 10, 25, 0, 0, 0)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(name: str) -> bool:
    p = PurePosixPath(name)
    return (not p.is_absolute() and ".." not in p.parts and "\\" not in name
            and len(p.parts) >= 2 and p.parts[0] in ROOTS
            and not (set(p.parts) & EXCLUDED_PARTS)
            and p.suffix.lower() in EXTENSIONS and not p.name.startswith(".env")
            and not any(part.startswith(".env.") for part in p.parts))


def source_paths(root: Path) -> tuple[str, list[str]]:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("unverified Git commit")
    for args in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(args, cwd=root, check=False).returncode:
            raise ValueError("tracked source is dirty; refuse ambiguous provenance")
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    paths = sorted(p.decode("utf-8") for p in raw.split(b"\0") if p)
    return commit, paths


def registry_routes(source: bytes) -> list[dict]:
    module = ast.parse(source.decode("utf-8"))
    assignments = [node for node in module.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "COMPONENTS"
                           for t in node.targets)]
    if len(assignments) != 1:
        raise ValueError("missing static portal component registry")
    components = ast.literal_eval(assignments[0].value)
    if len(components) != 20:
        raise ValueError("unexpected component registry size")
    ids = set()
    paths = set()
    routes = []
    for ident, label, path, category in components:
        if (not all(isinstance(value, str) for value in (ident, label, path, category))
                or not re.fullmatch(r"[a-z][a-z0-9-]*", ident)
                or not re.fullmatch(r"/[a-z][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)*", path)
                or not label.strip() or not label.isprintable()
                or category not in {"portal", "monitoring", "observability", "integration", "engine"}
                or ident in ids or path in paths):
            raise ValueError("unsafe or duplicate planned route")
        ids.add(ident)
        paths.add(path)
        routes.append({"id": ident, "name": label, "path": path, "category": category,
                       "state": "UNKNOWN", "route_mounted": False,
                       "runtime_authenticated": False, "integration_required": True})
    return routes


def candidate_readme() -> str:
    """Canonical non-deployable candidate notice; verifier checks exact bytes."""
    return (
        "# AIOps 2.0 — CANDIDATE ONLY / NO PRODUCTION DEPLOYMENT\n\n"
        "GET /api/platform/components returns a static plan only: all 20 service routes "
        "remain PLANNED, UNKNOWN, unmounted and unauthenticated. The optional "
        "portal_get_path_present field is an exact in-process GET-path match only; it "
        "does not attest service integration, identity, network access, or runtime. The sole target "
        "entrypoint is :17777; this archive starts no server and opens no ports.\n\n"
        "Embedded sources are a reviewed subset. Recover the remaining sources "
        "from the exact Git commit in metadata/source-manifest.json and verify "
        "each file's SHA-256 before use. Do not use an unpinned branch.\n\n"
        "Preflight (READ-ONLY): inspect actual portal route table, auth, existing "
        "service bindings and backups. Do not contact Debian from CI.\n"
        "Qualification: isolated synthetic ACME SAN P1 / Payments P2, identity "
        "02->03 fail-closed, offline Chromium PNG/SHA, Temporal and Policy tests. "
        "A CI PASS is not production attestation.\n"
        "Deployment: BLOCKED pending authenticated real-runtime E2E, backup "
        "verification and explicit human approval.\n"
        "Rollback: no deployment was made by this kit. For a separately approved "
        "future change, restore the previous portal image/config/routes from "
        "verified backups and requalify without touching V1/containerd.\n"
    )

def build(root: Path, output: Path, expected_commit: str | None = None) -> dict:
    root = root.resolve(strict=True)
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("create-only output: destination already exists")
    commit, tracked = source_paths(root)
    if expected_commit and expected_commit != commit:
        raise ValueError("pinned commit mismatch")
    included = {}
    inventory = []
    for name in tracked:
        if not safe_path(name):
            continue
        file = root / name
        if file.is_symlink() or not file.is_file() or root not in file.resolve().parents:
            raise ValueError("unsafe tracked source path")
        data = file.read_bytes()
        if len(data) > 4_000_000:
            raise ValueError("oversized tracked source")
        inventory.append({"path": name, "sha256": sha256(data), "bytes": len(data),
                          "embedded": name in APPROVED})
        if name in APPROVED:
            if len(data) > 120_000 or SENSITIVE.search(data) or b"\0" in data:
                raise ValueError("unreviewed or sensitive embedded source")
            included["sources/" + name] = data
    if set(APPROVED) != {item["path"] for item in inventory if item["embedded"]}:
        raise ValueError("approved source missing from pinned tree")
    routes = registry_routes(included["sources/app/portal/platform_registry.py"])
    manifest = {"schema": "aiops-single-portal-candidate-kit-v1", "commit": commit,
                "production_qualified": False, "runtime_e2e_qualified": False,
                "source_mode": "reviewed_subset_plus_pinned_git_sha256_references",
                "source_inventory": inventory, "embedded_count": len(included),
                "route_count": len(routes)}
    readme = candidate_readme()
    included["metadata/source-manifest.json"] = (
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    included["metadata/planned-routes.json"] = (
        json.dumps({"entrypoint": "http://10.79.94.202:17777/",
                    "routes": routes, "all_unverified": True}, sort_keys=True,
                   indent=2, ensure_ascii=False) + "\n").encode()
    included["metadata/README.md"] = readme.encode()
    sums = "".join(f"{sha256(data)}  {name}\n" for name, data in sorted(included.items()))
    included["metadata/SHA256SUMS"] = sums.encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(included.items()):
                info = zipfile.ZipInfo(name, FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {"commit": commit, "sha256": sha256(output.read_bytes()),
            "files": len(included), "sources": len(inventory), "routes": len(routes),
            "production_qualified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.output, args.commit), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
