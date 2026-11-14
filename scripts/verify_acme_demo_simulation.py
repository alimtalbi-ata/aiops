#!/usr/bin/env python3
"""Verify a saved ACME DEMO JSON artifact against independently recomputed output.

Strictly offline; does not accept arbitrary evidence as runtime attestation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_demo_simulation_pipeline import run_acme_demo_simulation

MAX_BYTES = 128 * 1024


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def verify_saved_demo_artifact(path: Path, *, expected_tenant: str) -> bool:
    if not isinstance(expected_tenant, str) or not expected_tenant:
        return False
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
            return False
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES:
            return False
        artifact = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                              parse_constant=lambda _: (_ for _ in ()).throw(
                                  ValueError("nonfinite_json_number")))
        if type(artifact) is not dict:
            return False
        # The reference is derived from the local, validated incident fixture,
        # not from any tenant, incident or digest asserted by the saved file.
        expected = run_acme_demo_simulation(tenant_id=expected_tenant)
        return artifact == expected
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError):
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline verification of saved ACME DEMO JSON")
    parser.add_argument("artifact", type=Path, help="saved output from run_acme_demo_simulation.py")
    parser.add_argument("--expected-tenant", required=True,
                        help="tenant from independent operator context, not from JSON")
    args = parser.parse_args(argv)
    if verify_saved_demo_artifact(args.artifact, expected_tenant=args.expected_tenant):
        print("DEMO_ARTIFACT_MATCHES_LOCAL_FIXTURE; RUNTIME_RECOVERY_UNKNOWN; LIVE_DENIED")
        return 0
    print("DEMO_ARTIFACT_REJECTED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
