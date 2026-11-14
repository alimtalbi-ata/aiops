"""Cross-check canonical synthetic customer package with offline Docker smoke.

This is consistency verification, not runtime attestation or artifact signing.
"""
import argparse
import json
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
        return (manifest.get("git_revision") == head_sha
                and manifest.get("incident_id") == cockpit.get("incident_id")
                == smoke.get("incident_id")
                and manifest.get("source_sha256") == cockpit.get("source_sha256")
                == smoke.get("source_sha256")
                and manifest.get("runtime_execution_attested") is False
                and manifest.get("live_remediation_authorized") is False)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("smoke_dir", type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    args = parser.parse_args()
    if not verify_bundle(args.package_dir, args.smoke_dir,
                         repository=args.repository, head_sha=args.head_sha,
                         run_id=args.run_id, run_attempt=args.run_attempt):
        print("BLOCKED: customer package and Docker smoke do not share a qualified synthetic fixture/run", file=sys.stderr)
        return 1
    print("PASS: canonical synthetic package and offline Docker smoke agree; runtime UNKNOWN, LIVE BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
