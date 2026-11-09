#!/usr/bin/env python3
"""Opt-in development pilot, NOT connected to the production cron.

One fixed test-only task. A verified GitHub command authorizes a single attempt.
No merge, deployment, live services, or writes outside a disposable checkout.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPO = "alimtalbi-ata/aiops"
ISSUE = 464
LOGIN = "alimtalbi-ata"
PREFIX = "AIOPS2_CODEX_PILOT_V1"
ALLOWED = "tests/test_codex_pilot_smoke.py"
TASK = (
    "In this disposable checkout, create ONLY tests/test_codex_pilot_smoke.py. "
    "Write Python unittest tests for the pure parse_command function from "
    "ops/coordination/dispatch_codex_once.py: accept a valid future UTC command "
    "with exact SHA and reject expired and mismatched SHA commands. "
    "Use sys.path insertion if needed for imports. Do not modify any other file. "
    "Do not access networks, secrets, Docker, databases, GLPI, crons, or deploy."
)

def call(args, **kw):
    return subprocess.run(args, text=True, capture_output=True, timeout=120, **kw)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--comment-id", type=int, required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--checkout", type=Path, required=True)
    p.add_argument("--state-dir", type=Path, default=Path.home()/".local/state/aiops2-codex-pilot")
    args = p.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.sha) or args.comment_id < 1:
        p.error("invalid SHA/comment")
    state = args.state_dir
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state, 0o700)
    receipt = state / f"pilot-{args.comment_id}.json"
    with (state / "pilot.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if receipt.exists():
            raise RuntimeError("already attempted")
        response = call(["gh", "api", f"repos/{REPO}/issues/comments/{args.comment_id}"])
        if response.returncode:
            raise RuntimeError("cannot read command")
        comment = json.loads(response.stdout)
        if (comment.get("user") or {}).get("login") != LOGIN or comment.get("html_url", "").split("#")[0] != f"https://github.com/{REPO}/issues/{ISSUE}":
            raise RuntimeError("untrusted command")
        pattern = rf"^{PREFIX} {args.sha} (\d{{4}}-\d\d-\d\dT\d\d:\d\d:\d\dZ)$"
        match = re.fullmatch(pattern, comment.get("body", "").strip())
        if not match:
            raise RuntimeError("invalid command")
        expiry = dt.datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        now = dt.datetime.now(dt.timezone.utc)
        if not now < expiry <= now + dt.timedelta(hours=2):
            raise RuntimeError("expired/oversized TTL")
        checkout = args.checkout.resolve()
        if call(["git", "rev-parse", "HEAD"], cwd=checkout).stdout.strip() != args.sha:
            raise RuntimeError("checkout SHA mismatch")
        if call(["git", "status", "--porcelain"], cwd=checkout).stdout.strip():
            raise RuntimeError("checkout dirty")
        receipt.write_text(json.dumps({"status":"STARTED", "comment_id":args.comment_id})+"\n")
        branch = f"codex/pilot-tests-{args.comment_id}"
        outcome = {"status":"PILOT_FAILED", "comment_id":args.comment_id, "branch":branch}
        try:
            with tempfile.TemporaryDirectory(prefix="aiops2-pilot-", dir=state) as tmp:
                work = Path(tmp) / "repo"
                # Clone from the already verified local checkout; never modify it.
                check = call(["git", "clone", "--no-hardlinks", "--quiet", str(checkout), str(work)])
                if check.returncode:
                    raise RuntimeError("clone failed")
                for cmd in (["git", "checkout", "--detach", args.sha],
                            ["git", "checkout", "-b", branch]):
                    if call(cmd, cwd=work).returncode:
                        raise RuntimeError("checkout failed")
                # A local clone may have origin set to the local checkout; push explicitly to GitHub.
                result = subprocess.run(
                    ["codex", "exec", "--sandbox", "workspace-write", "--skip-git-repo-check",
                     "-o", str(Path(tmp)/"codex-result.txt"), "-"],
                    input=TASK, text=True, capture_output=True, cwd=work, timeout=600)
                if result.returncode:
                    raise RuntimeError(f"Codex exit {result.returncode}")
                changed = call(["git", "status", "--porcelain", "--untracked-files=all"], cwd=work)
                paths = [line[3:] for line in changed.stdout.splitlines()]
                if changed.returncode or paths != [ALLOWED]:
                    raise RuntimeError(f"unexpected file changes: {paths}")
                if not (work / ALLOWED).is_file():
                    raise RuntimeError("expected test missing")
                test = call(["python3", "-B", "-m", "unittest", "discover", "-s", "tests",
                             "-p", "test_codex_pilot_smoke.py", "-v"], cwd=work)
                if test.returncode:
                    raise RuntimeError("pilot tests failed: " + test.stderr[-1500:])
                if call(["git", "add", "--", ALLOWED], cwd=work).returncode:
                    raise RuntimeError("git add failed")
                if call(["git", "-c", "user.name=AIOps2 Codex Pilot",
                         "-c", "user.email=aiops2-codex-pilot@users.noreply.github.com",
                         "commit", "-m", "test: add Codex pilot command parser coverage"], cwd=work).returncode:
                    raise RuntimeError("commit failed")
                remote = f"https://github.com/{REPO}.git"
                push = call(["git", "push", remote, f"HEAD:refs/heads/{branch}"], cwd=work)
                if push.returncode:
                    raise RuntimeError("push failed: " + push.stderr[-1000:])
                pr = call(["gh", "pr", "create", "--repo", REPO,
                           "--base", "design/coordination-bus-20261109",
                           "--head", branch, "--draft",
                           "--title", f"test: Codex pilot parser coverage (#{args.comment_id})",
                           "--body", "Isolated Codex development pilot. One allowlisted test file; local unittest passed. Human review required; no auto-merge."], cwd=work)
                if pr.returncode:
                    raise RuntimeError("PR creation failed: " + pr.stderr[-1000:])
                outcome = {"status":"PILOT_PR_CREATED", "comment_id":args.comment_id,
                           "branch":branch, "pr_url":pr.stdout.strip()}
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            outcome["error"] = str(exc)[:1500]
        receipt.write_text(json.dumps(outcome, indent=2)+"\n")
        os.chmod(receipt, 0o600)
        print(json.dumps(outcome))
        return 0 if outcome["status"] == "PILOT_PR_CREATED" else 2

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired, BlockingIOError) as exc:
        print("PILOT_NOT_VERIFIED:", exc, file=sys.stderr)
        sys.exit(2)
