#!/usr/bin/env python3
"""Offline join of Debian runtime identities and operator-reviewed GitHub candidates.

This is a preservation report, NOT a release selector. No network/Docker access.
Candidate records are explicit claims supplied by an operator; never inferred
from image tags, branch names, timestamps or matching component names.
"""
import argparse
import json
from pathlib import Path


def assess(snapshot, manifest):
    if snapshot.get("schema") != "aiops2-debian-provenance-v1":
        raise ValueError("invalid snapshot schema")
    if manifest.get("schema") != "aiops2-component-candidates-v1":
        raise ValueError("invalid candidate schema")
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    seen = set()
    entries = []
    for c in candidates:
        if not isinstance(c, dict):
            raise ValueError("invalid candidate entry")
        name, component, sha = c.get("name"), c.get("component"), c.get("github_sha")
        if not all(isinstance(v, str) and v.strip() for v in (name, component, sha)):
            raise ValueError("candidate name/component/github_sha required")
        if name in seen:
            raise ValueError("duplicate candidate name")
        seen.add(name)
        expected = c.get("verified_runtime_image_id")
        if expected is not None and (not isinstance(expected, str) or not expected.startswith("sha256:")):
            raise ValueError("verified_runtime_image_id must be a sha256 image identity")
        matches = []
        if expected:
            matches = [
                {"name": x.get("name"), "image_id": x.get("image_id"),
                 "compose_project": (x.get("compose") or {}).get("com.docker.compose.project"),
                 "compose_service": (x.get("compose") or {}).get("com.docker.compose.service")}
                for x in snapshot.get("containers", [])
                if x.get("image_id") == expected
            ]
        # Explicit identity match is NOT proof that this GitHub SHA built the
        # image. The manifest claim must be independently supported.
        entries.append({
            "name": name, "component": component, "github_sha": sha,
            "runtime_identity_claim": expected,
            "matching_runtime_containers": matches,
            "runtime_match": "IMAGE_ID_MATCH_CLAIMED" if matches else "NOT_ATTESTED",
            "source_to_image_provenance": "NOT_INDEPENDENTLY_VERIFIED",
            "features": c.get("features", []),
            "ci_evidence": c.get("ci_evidence", []),
            "integration_evidence": c.get("integration_evidence", []),
            "missing_evidence": c.get("missing_evidence", []),
            "decision": "PRESERVE_AND_QUALIFY",
        })
    return {
        "schema": "aiops2-component-evidence-join-v1",
        "snapshot_captured_at_utc": snapshot.get("captured_at_utc"),
        "snapshot_errors": snapshot.get("errors", []),
        "candidates": entries,
        "backup_restoration": "NOT_ATTESTED",
        "release_decision": "HOLD",
        "note": "No candidate is selected or promoted; GitHub SHA and runtime image identity require independent build provenance.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime_snapshot", type=Path)
    parser.add_argument("candidate_manifest", type=Path)
    args = parser.parse_args()
    snapshot = json.loads(args.runtime_snapshot.read_text(encoding="utf-8"))
    manifest = json.loads(args.candidate_manifest.read_text(encoding="utf-8"))
    print(json.dumps(assess(snapshot, manifest), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
