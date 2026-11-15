"""Cross-check canonical synthetic customer package with offline Docker smoke.

This is consistency verification, not runtime attestation or artifact signing.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from package_aiops2_demo_evidence import verify_package
from verify_aiops2_docker_smoke_artifact import verify as verify_smoke


def verify_bundle(package_dir: Path, smoke_dir: Path, *,
                  repository: str, head_sha: str,
                  run_id: str, run_attempt: str) -> bool:
    try:
        if not verify_package(package_dir):
            return False
        manifest = json.loads((package_dir / "manifest.json").read_text("utf-8"))
        cockpit = json.loads((package_dir / "cockpit.json").read_text("utf-8"))
        smoke = json.loads((smoke_dir / "aiops2-packaged-demo-smoke.json").read_text("utf-8"))
        provenance = json.loads(
            (smoke_dir / "aiops2-packaged-demo-smoke-provenance.json").read_text("utf-8"))
        if not verify_smoke(smoke, provenance, repository=repository,
                            head_sha=head_sha, run_id=run_id,
                            run_attempt=run_attempt):
            return False
        # Validate shared identifiers independently: equal missing/invalid fields
        # must not pass even if a lower-level validator is accidentally bypassed.
        incident = manifest.get("incident_id")
        digest = manifest.get("source_sha256")
        revision = manifest.get("git_revision")
        if (not isinstance(incident, str) or not incident.strip()
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or not isinstance(revision, str)
                or re.fullmatch(r"[0-9a-f]{40}", revision) is None):
            return False
        return (manifest.get("git_revision") == provenance.get("commit_sha")
                and manifest.get("incident_id") == cockpit.get("incident_id")
                == smoke.get("incident_id")
                and manifest.get("source_sha256") == cockpit.get("source_sha256")
                == smoke.get("source_sha256")
                and manifest.get("runtime_execution_attested") is False
                and manifest.get("live_remediation_authorized") is False)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return False



def build_qualification_report(package_dir: Path, smoke_dir: Path, *,
                               repository: str, head_sha: str,
                               run_id: str, run_attempt: str) -> dict:
    """Report offline artifact consistency; never assert GitHub CI or LIVE."""
    passed = verify_bundle(package_dir, smoke_dir, repository=repository,
                           head_sha=head_sha, run_id=run_id,
                           run_attempt=run_attempt)
    return {
        "schema": "aiops2.customer-demo-qualification.v1",
        "scope": "LOCAL_SYNTHETIC_ARTIFACT_CONSISTENCY_ONLY",
        "repository": repository,
        "pr_head_sha": head_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "artifact_consistency": "PASS" if passed else "BLOCKED",
        "ci_run_verified": False,
        "browser_rehearsal_verified": False,
        "runtime_attested": False,
        "independent_postcheck_verified": False,
        "live_remediation_authorized": False,
        "customer_demo_qualification": "PENDING_INDEPENDENT_CI_AND_BROWSER_REVIEW"
        if passed else "BLOCKED",
        "live_qualification": "NO_GO",
        "trust_boundary": "UNSIGNED_LOCAL_REPORT_NOT_CI_OR_RUNTIME_ATTESTATION",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("smoke_dir", type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--report", type=Path, help="Write a fail-closed offline JSON qualification report")
    args = parser.parse_args()
    report = build_qualification_report(args.package_dir, args.smoke_dir,
                                        repository=args.repository, head_sha=args.head_sha,
                                        run_id=args.run_id, run_attempt=args.run_attempt)
    if args.report is not None:
        try:
            args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"BLOCKED: cannot write qualification report: {exc.__class__.__name__}", file=sys.stderr)
            return 1
    if report["artifact_consistency"] != "PASS":
        print("BLOCKED: customer package and Docker smoke do not share a qualified synthetic fixture/run", file=sys.stderr)
        return 1
    print("PASS: canonical synthetic package and offline Docker smoke agree; runtime UNKNOWN, LIVE BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
