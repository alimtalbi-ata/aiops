"""Join STAR identity readiness and historical screenshot gap plans, offline only."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def join_capture_plans(identity: dict, historical: dict) -> dict:
    if not isinstance(identity, dict) or identity.get("schema") != "star-capture-identity-plan-v1":
        raise ValueError("invalid identity plan")
    if not isinstance(historical, dict) or historical.get("schema") != "star-legacy-capture-gap-plan-v1":
        raise ValueError("invalid historical plan")
    if identity.get("run_id") != historical.get("run_id") or not isinstance(identity.get("run_id"), str):
        raise ValueError("STAR run_id mismatch")
    a, b = identity.get("steps"), historical.get("steps")
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != 9 or len(b) != 9:
        raise ValueError("invalid STAR cue sequence")
    if identity.get("runtime_proof_count") != 0 or historical.get("missing_runtime_captures") != 9:
        raise ValueError("untrusted plan claims runtime evidence")
    from demo.star_snapshot_choreography import CUES
    steps = []
    for index, cue in enumerate(CUES):
        left, right = a[index], b[index]
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise ValueError("malformed STAR step")
        if any(left.get(k) != v or right.get(k) != v for k, v in
               (("cue", cue.cue), ("application", cue.service))):
            raise ValueError("STAR cue/app alignment mismatch")
        if left.get("expected_view") != cue.view or right.get("expected_view") != cue.view:
            raise ValueError("STAR view mismatch")
        if left.get("authenticated_runtime_proof") is not False or right.get("runtime_evidence_status") != "MISSING":
            raise ValueError("historical captures cannot attest runtime")
        if left.get("live_action_authorized") is not False:
            raise ValueError("LIVE action forbidden")
        ready = left.get("capture_ready_for_attempt")
        if not isinstance(ready, bool):
            raise ValueError("invalid readiness flag")
        steps.append({
            "cue": cue.cue, "application": cue.service, "expected_view": cue.view,
            "status": "READY_FOR_READ_ONLY_CAPTURE" if ready else "MISSING_IDENTIFIERS",
            "missing_identifiers": left.get("missing_identifiers"),
            "historical_png_matches": right.get("legacy_png_byte_matches_for_application"),
            "runtime_proof": False,
        })
    return {"schema": "star-capture-execution-worklist-v1",
            "run_id": identity["run_id"], "steps": steps,
            "ready_for_attempt": sum(x["status"] == "READY_FOR_READ_ONLY_CAPTURE" for x in steps),
            "runtime_proof_count": 0, "read_only": True, "live_action_authorized": False}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("identity_plan", type=Path)
    parser.add_argument("historical_gap_plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = join_capture_plans(
        json.loads(args.identity_plan.read_text(encoding="utf-8")),
        json.loads(args.historical_gap_plan.read_text(encoding="utf-8")))
    if args.output.is_symlink():
        raise ValueError("output symlink forbidden")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(f'STAR_READY={output["ready_for_attempt"]};RUNTIME_PROOF=0')

if __name__ == "__main__":
    main()
