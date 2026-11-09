#!/usr/bin/env python3
"""One-shot, fail-closed GitHub -> Debian Codex CLI -> GitHub adapter.

No cron installation, deployment, production writes or arbitrary task prompts.
Run manually under aiops with gh and codex authenticated.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPO = "alimtalbi-ata/aiops"
ISSUE = 464
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
COMMAND_RE = re.compile(r"^AIOPS2_CODEX_DISPATCH_V1 ([0-9a-f]{40}) ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)$")
TASK = ("Read-only Agent 8 mission. Inspect ops/coordination and existing GitHub/ Debian "
        "integration; report the minimum safe inbound dispatcher requirements. "
        "Do not change any files, crons, stacks, databases, tickets or GitHub state. "
        "Do not claim automatic dispatch is working.")

def parse_command(body, now, expected_sha):
    if not isinstance(body, str):
        raise ValueError("missing command")
    match = COMMAND_RE.fullmatch(body.strip())
    if not match:
        raise ValueError("command must match strict allowlisted format")
    sha, expiry = match.groups()
    if sha != expected_sha or not SHA_RE.fullmatch(sha):
        raise ValueError("unexpected exact source SHA")
    expires = dt.datetime.strptime(expiry, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if expires <= now or expires > now + dt.timedelta(hours=2):
        raise ValueError("expired or excessive TTL")
    return sha

def run(args, cwd=None, timeout=120):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)

def execute(comment_id, expected_sha, state_dir, checkout, authorized_login):
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)
    lock_path = state_dir / "dispatch.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = state_dir / ("comment-" + str(comment_id) + ".json")
        if receipt.exists():
            raise ValueError("already attempted; refusing duplicate")
        raw = run(["gh", "api", f"repos/{REPO}/issues/comments/{comment_id}"])
        if raw.returncode:
            raise RuntimeError("cannot fetch GitHub command")
        comment = json.loads(raw.stdout)
        if (comment.get("user") or {}).get("login") != authorized_login:
            raise ValueError("untrusted author")
        if comment.get("html_url", "").split("#")[0] != f"https://github.com/{REPO}/issues/{ISSUE}":
            raise ValueError("wrong issue")
        now = dt.datetime.now(dt.timezone.utc)
        parse_command(comment.get("body"), now, expected_sha)
        if not (checkout / ".git").exists():
            raise ValueError("checkout missing")
        sha = run(["git", "rev-parse", "HEAD"], cwd=checkout)
        if sha.returncode or sha.stdout.strip() != expected_sha:
            raise ValueError("checkout SHA mismatch")
        dirty = run(["git", "status", "--porcelain"], cwd=checkout)
        if dirty.returncode or dirty.stdout.strip():
            raise ValueError("checkout dirty")
        # Reserve the one-shot before running; a failure must not silently retry.
        receipt.write_text(json.dumps({"status":"STARTED", "comment_id":comment_id,
                                       "source_sha":expected_sha, "started_at":now.isoformat()})+"\n")
        os.chmod(receipt, 0o600)
        with tempfile.TemporaryDirectory(prefix="aiops2-codex-", dir=state_dir) as folder:
            output = Path(folder) / "result.txt"
            events = Path(folder) / "events.jsonl"
            with events.open("w") as stream:
                try:
                    process = subprocess.run(["codex", "exec", "--sandbox", "read-only",
                                              "--json", "-o", str(output), "-"],
                                             input=TASK, text=True, stdout=stream,
                                             stderr=subprocess.PIPE, cwd=checkout, timeout=600)
                    code = process.returncode
                except subprocess.TimeoutExpired:
                    code = 124
            session = None
            for line in events.read_text().splitlines():
                try:
                    event = json.loads(line)
                    if event.get("type") == "thread.started":
                        session = event.get("thread_id")
                except (ValueError, AttributeError):
                    continue
            result = output.read_text()[:8000] if output.exists() else ""
            finish = dt.datetime.now(dt.timezone.utc)
            data = {"status":"CODEX_OK" if code == 0 and result else "CODEX_FAILED",
                    "comment_id":comment_id, "source_sha":expected_sha,
                    "started_at":now.isoformat(), "finished_at":finish.isoformat(),
                    "session_id":session, "exit_code":code}
            receipt.write_text(json.dumps(data, indent=2)+"\n")
            # Never publish raw logs, environment variables or model-generated secrets.
            # Only publish fixed metadata. Keep model output local for review.
            body = ("## AIOps2 Codex inbound receipt (manual one-shot)\n\n"
                    f"- Command comment: #{comment_id}\n- SHA: `{expected_sha}`\n"
                    f"- Session: `{session or 'NOT_RECORDED'}`\n- Exit: `{code}`\n"
                    f"- Status: **{data['status']}**\n"
                    "- Result retained locally for review; not automatically published.\n"
                    "- This proves manual inbound polling, not unattended scheduling.\n")
            posted = run(["gh", "issue", "comment", str(ISSUE), "--repo", REPO,
                          "--body", body], timeout=45)
            if posted.returncode:
                raise RuntimeError("local receipt saved but GitHub publication failed")
            print(json.dumps({**data, "github_comment":posted.stdout.strip()}))
            return 0 if code == 0 and result else 2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comment-id", required=True, type=int)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path.home()/".local/state/aiops2-codex-dispatch")
    parser.add_argument("--authorized-login", default="alimtalbi-ata")
    args = parser.parse_args()
    try:
        if not SHA_RE.fullmatch(args.sha) or args.comment_id < 1:
            raise ValueError("invalid SHA or comment ID")
        return execute(args.comment_id, args.sha, args.state_dir, args.checkout, args.authorized_login)
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired, BlockingIOError) as exc:
        print("DISPATCH_NOT_VERIFIED:", exc, file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
