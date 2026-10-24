"""Generate read-only capture work plan from an audited historical manifest."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from demo.star_snapshot_choreography import CUES

_RUN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,95}$")

def build_gap_plan(audit: dict, run_id: str) -> dict:
    if not isinstance(audit, dict) or audit.get("schema") != "aiops-legacy-playwright-audit-v1":
        raise ValueError("unsupported audit schema")
    entries = audit.get("entries")
    if not isinstance(entries, list) or len(entries) > 128:
        raise ValueError("invalid audit entries")
    if not isinstance(run_id, str) or not _RUN.fullmatch(run_id):
        raise ValueError("invalid run_id")
    counts = {"grafana": 0, "n8n": 0, "glpi": 0}
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("invalid audit entry")
        service = item.get("application")
        if service not in (*counts, "ucp", "other"):
            raise ValueError("unknown historical application")
        for key in ("integrity_verified", "runtime_authenticated", "business_state_verified", "eligible_for_star_proof"):
            if item.get(key, False) not in (True, False) or not isinstance(item.get(key, False), bool):
                raise ValueError("invalid historical attestation field")
        if any(item.get(key, False) is True for key in ("runtime_authenticated", "business_state_verified", "eligible_for_star_proof")):
            raise ValueError("historical audit cannot assert runtime attestation")
        if service in counts and item.get("integrity_verified") is True:
            counts[service] += 1
    steps = []
    for cue in CUES:
        steps.append({
            "cue": cue.cue,
            "application": cue.service,
            "expected_view": cue.view,
            "expected_state": cue.required_state,
            "legacy_png_byte_matches_for_application": counts[cue.service],
            "runtime_evidence_status": "MISSING",
            "capture_required": True,
            "next_action": "Capture authenticated read-only business view, bind run_id and timestamp, verify event identity and PNG integrity",
        })
    return {"schema": "star-legacy-capture-gap-plan-v1", "run_id": run_id,
            "historical_byte_integrity_is_not_runtime_attestation": True,
            "live_remediation_authorized": False, "steps": steps,
            "missing_runtime_captures": len(steps)}

def main() -> None:
    p = argparse.ArgumentParser(description="Offline STAR gap plan from sanitized Playwright audit")
    p.add_argument("audit", type=Path)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    plan = build_gap_plan(json.loads(a.audit.read_text(encoding="utf-8")), a.run_id)
    if a.output.is_symlink():
        raise ValueError("output symlink forbidden")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f'STAR_GAP_PLAN={len(plan["steps"])};RUNTIME_CAPTURES_MISSING={plan["missing_runtime_captures"]}')

if __name__ == "__main__":
    main()
