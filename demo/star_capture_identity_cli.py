"""Offline CLI to turn operator-provided STAR IDs into a capture readiness plan."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from demo.star_capture_identity_plan import plan_capture_identity

def build_from_manifest(payload: dict) -> dict:
    if not isinstance(payload, dict) or set(payload) != {'run_id', 'identifiers'}:
        raise ValueError('manifest must contain only run_id and identifiers')
    return plan_capture_identity(payload['run_id'], payload['identifiers'])

def main() -> None:
    parser = argparse.ArgumentParser(description='Build read-only STAR capture identity readiness plan')
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    plan = build_from_manifest(json.loads(args.manifest.read_text(encoding='utf-8')))
    if args.output.is_symlink():
        raise ValueError('output symlink not allowed')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(f'STAR_CAPTURE_READY={plan["capture_attempt_ready_count"]};RUNTIME_PROOF={plan["runtime_proof_count"]}')

if __name__ == '__main__':
    main()
