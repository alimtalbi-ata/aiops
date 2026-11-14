"""Offline consistency check for downloaded SAN→Payments Docker smoke evidence.

No cryptographic signature: compare provenance with the trusted GitHub Actions UI.
"""
import argparse
import json
import re
import sys
from pathlib import Path

EXPECTED_SMOKE = {
    "schema", "accepted", "scope", "runtime_attested",
    "live_actions_authorized", "incident_id", "source_sha256",
}
EXPECTED_PROVENANCE = {
    "schema", "repository", "commit_sha", "pr_head_sha", "ref",
    "run_id", "run_attempt", "workflow", "event_name", "trust_boundary",
}
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def verify(smoke: object, provenance: object, *, repository: str,
           head_sha: str, run_id: str, run_attempt: str) -> bool:
    """Fail closed on malformed fields, unqualified claims and mismatched run IDs."""
    if not isinstance(smoke, dict) or not isinstance(provenance, dict):
        return False
    if set(smoke) != EXPECTED_SMOKE or set(provenance) != EXPECTED_PROVENANCE:
        return False
    if (smoke["schema"] != "aiops2.packaged-demo-smoke.v1"
            or smoke["accepted"] is not True
            or smoke["scope"] != "LOCAL_SYNTHETIC_ONLY"
            or smoke["runtime_attested"] is not False
            or smoke["live_actions_authorized"] is not False
            or not isinstance(smoke["incident_id"], str)
            or not smoke["incident_id"].strip()
            or not isinstance(smoke["source_sha256"], str)
            or DIGEST.fullmatch(smoke["source_sha256"]) is None):
        return False
    if (provenance["schema"] != "aiops2.github-actions-smoke-provenance.v1"
            or provenance["trust_boundary"]
            != "UNSIGNED_GITHUB_ACTIONS_RUN_METADATA_NOT_RUNTIME_ATTESTATION"
            or provenance["repository"] != repository
            or not isinstance(provenance["commit_sha"], str)
            or SHA.fullmatch(provenance["commit_sha"]) is None
            or provenance["pr_head_sha"] != head_sha
            or not isinstance(head_sha, str)
            or SHA.fullmatch(head_sha) is None
            or provenance["run_id"] != run_id
            or provenance["run_attempt"] != run_attempt
            or not isinstance(run_id, str) or not run_id.isdecimal()
            or not isinstance(run_attempt, str) or not run_attempt.isdecimal()
            or int(run_id) < 1 or int(run_attempt) < 1
            or not isinstance(provenance["workflow"], str)
            or provenance["workflow"] != "AIOps quality gates"
            or not isinstance(provenance["event_name"], str)
            or provenance["event_name"] not in {"push", "pull_request", "workflow_dispatch"}
            or not isinstance(provenance["ref"], str)
            or not provenance["ref"].startswith("refs/")):
        return False
    if provenance["event_name"] != "pull_request" and provenance["commit_sha"] != head_sha:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Extracted GitHub Actions artifact")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    args = parser.parse_args()
    try:
        smoke = json.loads((args.directory / "aiops2-packaged-demo-smoke.json").read_text())
        provenance = json.loads((args.directory / "aiops2-packaged-demo-smoke-provenance.json").read_text())
        accepted = verify(smoke, provenance, repository=args.repository,
                          head_sha=args.head_sha, run_id=args.run_id,
                          run_attempt=args.run_attempt)
    except (OSError, ValueError, UnicodeError):
        accepted = False
    if not accepted:
        print("BLOCKED: smoke or GitHub Actions provenance mismatch", file=sys.stderr)
        return 1
    print("PASS: synthetic-only artifact internally consistent; origin and runtime NOT attested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
