"""Read-only migration audit for the legacy F20.13 Playwright manifest.

A historical PASS and hash cannot authenticate a current runtime session.
No external file access, network, browser, credentials or implicit migration.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

_SHA = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")
_APPS = {"grafana", "n8n", "glpi"}

def audit_legacy_manifest(document: dict) -> dict:
    if not isinstance(document, dict) or document.get("browser") != "Chromium" or document.get("automation") != "Playwright":
        raise ValueError("unsupported legacy manifest")
    results = document.get("results", document.get("captures"))
    if not isinstance(results, list) or len(results) > 128:
        raise ValueError("invalid capture collection")
    entries = []
    for item in results:
        if not isinstance(item, dict):
            raise ValueError("invalid legacy entry")
        name = item.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("invalid capture name")
        service = item.get("service")
        if not isinstance(service, str):
            service = "ucp"
        status = item.get("status")
        if status not in ("PASS", "FAIL"):
            raise ValueError("invalid legacy status")
        digest = item.get("sha256")
        # Historical manifests with no SHA are still inventoried, never verified.
        hash_format_valid = isinstance(digest, str) and bool(_SHA.fullmatch(digest))
        app = service.strip().lower()
        if app not in _APPS:
            app = "ucp" if app in ("ucp", "") else "other"
        # A login page, PASS, and a bare SHA are never evidence of the business state.
        entries.append({
            "name": name,
            "application": app,
            "legacy_status": status,
            "sha256_declared": hash_format_valid,
            "capture_file_available": False,
            "integrity_verified": False,
            "runtime_authenticated": False,
            "business_state_verified": False,
            "eligible_for_star_proof": False,
        })
    return {
        "schema": "aiops-legacy-playwright-audit-v1",
        "source_version": str(document.get("version", "unknown"))[:120],
        "entry_count": len(entries),
        "entries": entries,
        "migration_status": "AUDIT_ONLY",
        "needs_original_png_and_authenticated_runtime": True,
    }

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("legacy_manifest", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a=p.parse_args()
    data=json.loads(a.legacy_manifest.read_text(encoding="utf-8"))
    report=audit_legacy_manifest(data)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x",encoding="utf-8") as stream:
        json.dump(report, stream, indent=2,ensure_ascii=False)
    print("LEGACY_PLAYWRIGHT_AUDIT_ONLY;NO_RUNTIME_ATTESTATION")

if __name__ == "__main__":
    main()
