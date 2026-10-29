#!/usr/bin/env python3
"""Offline fail-closed preflight for the *narrow* Demo Studio V2 stable deployer.

No network, no deployment, no writes. Passing is NOT a GO or a runtime attestation.
The currently reviewed deployer copies only demo_v2.py and test_demo_v2.py;
portal/main.py is patched by a narrow anchor injection, not deployed as a file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

SHA = re.compile(r"[0-9a-f]{40}\Z")
COPY_PATHS = frozenset({"app/portal/demo_v2.py", "tests/test_demo_v2.py"})
# Executable deployment controls require separate qualification; never auto-approve.
DEPLOY_PATHS = frozenset({
    "deploy/deploy-demo-studio-v2.sh",
    "deploy/poll-approved-deploy.sh",
    "deploy/install-approved-cron.sh",
})
REQUIRED = ("app/portal/demo_v2.py", "deploy/deploy-demo-studio-v2.sh")
SCHEMA = "aiops.demo-stable-deployment-coverage.v1"


class Blocked(ValueError):
    pass


def git(repo: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True,
            check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked("git_unavailable") from None
    if result.returncode:
        raise Blocked("git_ref_or_history_unavailable")
    return result.stdout


def is_metadata(path: str) -> bool:
    return (path in {"README.md", "VERSION", ".gitignore"}
            or path.startswith(("docs/", "tests/"))
            )



def deployment_plan(path: str, status: str) -> dict:
    """Static narrow-deployer transport contract; NOT a runtime attestation."""
    if path == "app/portal/demo_v2.py":
        fields = ("PORTAL_MODULE", "COPY_TO_PORTAL_SOURCE", "PORTAL_IMAGE",
                  "PORTAL_CONTAINER", "PORTAL_REGRESSION_NOT_RUN_HERE",
                  "SOURCE_AND_DOCKER_ROLLBACK_NOT_TESTED")
        supported = True
    elif path == "tests/test_demo_v2.py":
        fields = ("DEPLOYED_PORTAL_TEST", "COPY_TO_PORTAL_TESTS",
                  "NO_DIRECT_REBUILD", "NO_DIRECT_RESTART",
                  "PORTAL_REGRESSION_NOT_RUN_HERE", "SOURCE_RESTORE_NOT_TESTED")
        supported = True
    elif path in DEPLOY_PATHS or path.startswith(("deploy/", ".github/")):
        fields = ("RELEASE_CONTROL_REQUALIFICATION_REQUIRED", "NOT_QUALIFIED",
                  "NOT_QUALIFIED", "NOT_QUALIFIED", "NOT_TESTED", "NOT_QUALIFIED")
        supported = False
    elif is_metadata(path):
        fields = ("REPOSITORY_ONLY", "NO_RUNTIME_COPY", "NO_RUNTIME_REBUILD",
                  "NO_RUNTIME_RESTART", "CI_NOT_ATTESTED_HERE", "NOT_APPLICABLE")
        supported = True
    else:
        fields = ("UNTRANSPORTED_APPLICATION_OR_CONFIG", "NOT_TRANSPORTED",
                  "NOT_QUALIFIED", "NOT_QUALIFIED", "NOT_TESTED", "NOT_QUALIFIED")
        supported = False
    return dict(zip(("category", "copy", "rebuild", "restart", "tests", "rollback"), fields),
                path=path, git_status=status,
                decision="REVIEWABLE" if supported and status in ("A", "M") else "BLOCKED")

def qualify(repo: Path, stable_sha: str, candidate_sha: str) -> dict:
    """Check history, required deploy files, and every changed file, fail closed."""
    if not SHA.fullmatch(stable_sha) or not SHA.fullmatch(candidate_sha):
        raise Blocked("invalid_sha")
    if stable_sha == candidate_sha:
        raise Blocked("no_new_candidate")
    root = git(repo, "rev-parse", "--show-toplevel").decode("utf-8", "strict").strip()
    if Path(root).resolve() != repo.resolve():
        raise Blocked("repository_root_mismatch")
    for sha in (stable_sha, candidate_sha):
        if git(repo, "rev-parse", "--verify", sha + "^{commit}").strip().decode() != sha:
            raise Blocked("invalid_commit_ref")
    try:
        git(repo, "merge-base", "--is-ancestor", stable_sha, candidate_sha)
    except Blocked:
        raise Blocked("non_fast_forward_or_diverged") from None
    for path in (*REQUIRED, "tests/test_demo_v2.py"):
        git(repo, "cat-file", "-e", candidate_sha + ":" + path)
    raw = git(repo, "diff", "--name-status", "-z", "--no-renames",
              stable_sha, candidate_sha)
    fields = raw.split(b"\0")
    if not fields or fields[-1] != b"":
        raise Blocked("malformed_git_diff")
    fields.pop()
    if len(fields) % 2:
        raise Blocked("malformed_git_diff")
    changed = []
    blocked = []
    matrix = []
    for status_raw, path_raw in zip(fields[::2], fields[1::2]):
        try:
            status = status_raw.decode("ascii")
            path = path_raw.decode("utf-8")
        except UnicodeError:
            raise Blocked("invalid_changed_path") from None
        if not path or any(ord(ch) < 32 for ch in path) or path.startswith("/"):
            raise Blocked("invalid_changed_path")
        if status not in ("A", "M", "D", "T"):
            raise Blocked("unexpected_diff_status")
        changed.append(path)
        plan = deployment_plan(path, status)
        matrix.append(plan)
        if plan["decision"] == "BLOCKED":
            blocked.append(path)
    if not changed:
        raise Blocked("empty_diff")
    return {
        "schema": SCHEMA,
        "stable_sha": stable_sha,
        "candidate_sha": candidate_sha,
        "assessment": "BLOCKED" if blocked else "READY_FOR_REVIEW",
        "overall": "NO_GO",
        "provenance": "OFFLINE_GIT_DIFF_NOT_RUNTIME",
        "deployer_contract": "DEMO_STUDIO_V2_NARROW_COPY_AND_MAIN_ANCHOR_INJECTION",
        "changed_count": len(changed),
        "module_deployment_matrix": sorted(matrix, key=lambda item: item["path"]),
        "matrix_is_static_contract_not_runtime_evidence": True,
        "unsupported_paths": sorted(blocked)[:30],
        "unsupported_count": len(blocked),
        "field_smoke_tests": "NOT_TESTED",
        "rollback_test": "NOT_TESTED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--stable-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args(argv)
    try:
        result = qualify(args.repo, args.stable_sha, args.candidate_sha)
    except (Blocked, UnicodeError) as exc:
        result = {"schema": SCHEMA, "assessment": "BLOCKED", "overall": "NO_GO",
                  "reason": str(exc), "field_smoke_tests": "NOT_TESTED",
                  "rollback_test": "NOT_TESTED"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["assessment"] == "READY_FOR_REVIEW" else 2


if __name__ == "__main__":
    sys.exit(main())
