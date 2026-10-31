#!/usr/bin/env python3
"""Fail-closed source/CI gate for clean Debian first-install dispatch."""
from __future__ import annotations

import json
import os
import re
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

REQUIRED_WORKFLOWS = {
    "AIOps quality gates": ".github/workflows/quality.yml",
    "Debian 12 and 13 installation and runtime qualification":
        ".github/workflows/debian12-qualification.yml",
}


def github_get(repo: str, token: str, path: str) -> dict:
    request = Request(
        f"https://api.github.com/repos/{repo}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read(2_000_000))


def verify_source(repo: str, sha: str, token: str, get_json=github_get) -> list[str]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("invalid_repository")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("source_sha_must_be_full_40_character_commit")
    if not token or any(ch.isspace() for ch in token):
        raise ValueError("github_token_missing_or_invalid")

    comparison = get_json(
        repo, token, f"/compare/{sha}...{quote('main', safe='')}"
    )
    if comparison.get("status") not in ("ahead", "identical"):
        raise ValueError("source_sha_not_ancestor_of_main")

    associated_prs = get_json(repo, token, f"/commits/{sha}/pulls")
    if not isinstance(associated_prs, list):
        raise ValueError("invalid_commit_pull_requests_response")
    merged_main_prs = [
        pr for pr in associated_prs
        if isinstance(pr, dict)
        and pr.get("state") == "closed"
        and pr.get("merged_at")
        and pr.get("draft") is False
        and (pr.get("base") or {}).get("ref") == "main"
        and ((pr.get("head") or {}).get("repo") or {}).get("full_name") == repo
    ]
    if not merged_main_prs:
        raise ValueError("source_sha_not_from_merged_same_repo_main_pr")

    runs = get_json(repo, token, f"/actions/runs?head_sha={sha}&per_page=100")
    workflow_runs = runs.get("workflow_runs", [])
    if not isinstance(workflow_runs, list):
        raise ValueError("invalid_workflow_runs_response")

    for name, path in REQUIRED_WORKFLOWS.items():
        candidates = [
            run for run in workflow_runs
            if isinstance(run, dict)
            and run.get("name") == name
            and run.get("path") == path
            and run.get("head_sha") == sha
            and (run.get("head_repository") or {}).get("full_name") == repo
        ]
        if not candidates:
            raise ValueError("missing_exact_head_ci:" + name)
        latest = max(
            candidates,
            key=lambda item: (
                item.get("created_at", ""),
                int(item.get("run_attempt", 1) or 1),
            ),
        )
        if latest.get("status") != "completed" or latest.get("conclusion") != "success":
            raise ValueError(
                "exact_head_ci_not_success:" + name + ":" +
                str(latest.get("status")) + ":" + str(latest.get("conclusion"))
            )
    return list(REQUIRED_WORKFLOWS)


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("SOURCE_SHA", "")
    token = os.environ.get("GH_TOKEN", "")
    try:
        passed = verify_source(repo, sha, token)
    except Exception as exc:
        # Do not print request URLs, response bodies or credentials.
        reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print("BLOCKED|clean_debian_source_gate|" + reason, file=sys.stderr)
        return 2
    for name in passed:
        print("EXACT_HEAD_CI=PASS|" + name)
    print("APPROVED_SOURCE_ANCESTRY=PASS|main")
    print("MERGED_MAIN_PR=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
