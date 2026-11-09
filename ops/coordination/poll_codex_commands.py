#!/usr/bin/env python3
"""Read-only GitHub queue poller for the allowlisted Codex one-shot adapter.

Run from a pinned clean checkout; no deployment poller changes. One command per run.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys
from dispatch_codex_once import REPO, ISSUE, parse_command, execute

PREFIX = "AIOPS2_CODEX_DISPATCH_V1 "
def candidates(comments, now, sha, authorized_login, state_dir):
    valid = []
    for c in comments:
        if not isinstance(c, dict) or not isinstance(c.get("id"), int):
            continue
        if (c.get("user") or {}).get("login") != authorized_login:
            continue
        if c.get("html_url", "").split("#")[0] != f"https://github.com/{REPO}/issues/{ISSUE}":
            continue
        if not isinstance(c.get("body"), str) or not c["body"].startswith(PREFIX):
            continue
        try:
            parse_command(c["body"], now, sha)
        except ValueError:
            continue
        if not (state_dir / f"comment-{c['id']}.json").exists():
            valid.append(c["id"])
    return sorted(valid)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sha", required=True)
    p.add_argument("--checkout", type=Path, required=True)
    p.add_argument("--state-dir", type=Path, default=Path.home()/".local/state/aiops2-codex-dispatch")
    p.add_argument("--authorized-login", default="alimtalbi-ata")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        p.error("invalid SHA")
    # GitHub paginates; fail closed if queue is too large for a bounded scan.
    proc = subprocess.run(["gh", "api", f"repos/{REPO}/issues/{ISSUE}/comments",
                           "-f", "per_page=100", "-f", "page=1", "--method", "GET"],
                          text=True, capture_output=True, timeout=45)
    if proc.returncode:
        print("QUEUE_UNAVAILABLE", file=sys.stderr)
        return 2
    try:
        comments = json.loads(proc.stdout)
        if not isinstance(comments, list) or len(comments) >= 100:
            raise ValueError("queue pagination boundary; refusing incomplete scan")
        ready = candidates(comments, dt.datetime.now(dt.timezone.utc), args.sha,
                           args.authorized_login, args.state_dir)
    except (ValueError, TypeError):
        print("QUEUE_UNVERIFIED", file=sys.stderr)
        return 2
    if args.dry_run:
        print(json.dumps({"status":"DRY_RUN", "eligible_ids":ready}))
        return 0
    if not ready:
        print("NO_ELIGIBLE_COMMAND")
        return 0
    # Exactly one per invocation; one-shot adapter re-fetches and revalidates it.
    return execute(ready[0], args.sha, args.state_dir, args.checkout, args.authorized_login)

if __name__ == "__main__":
    sys.exit(main())
