#!/usr/bin/env python3
"""Existing-host AIOps2 observer. No remote shell, deployments, or arbitrary jobs."""
import datetime as dt
import json
import os
import pathlib
import subprocess
import urllib.request

ROOT = pathlib.Path(os.environ.get("AIOPS_ROOT", "/home/aiops/aiops2"))
REPO = os.environ.get("AIOPS_REPO", "alimtalbi-ata/aiops")
ISSUE = int(os.environ.get("AIOPS_REPORT_ISSUE", "186"))
TOKEN_FILE = pathlib.Path(os.environ.get("AIOPS_TOKEN_FILE", "/etc/aiops2-agent/github-token"))
TIMEOUT = 12

def run(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT, check=False)
        return {"exit_code": p.returncode, "ok": p.returncode == 0}
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "error": "unavailable_or_timeout"}

def collect():
    # Never upload stdout from Docker, systemctl or git: it may contain secrets.
    return {
        "schema": "aiops.existing-host-observer.v1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hostname": "redacted",
        "host_kind": "existing_debian",
        "root_exists": ROOT.is_dir(),
        "docker": run(["docker", "info", "--format", "{{.ServerVersion}}"]),
        "compose": run(["docker", "compose", "version", "--short"]),
        "git": run(["git", "-C", str(ROOT), "rev-parse", "--verify", "HEAD"]) if (ROOT / ".git").exists() else {"ok": False, "error": "no_git_checkout"},
        "services": run(["docker", "compose", "-f", str(ROOT / "compose.yml"), "ps", "--quiet"]) if (ROOT / "compose.yml").is_file() else {"ok": False, "error": "compose_missing"},
    }

def publish(report):
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("empty token")
    body = "AIOps2 Debian observer (read-only; no host commands from GitHub)\n\n```json\n" + json.dumps(report, sort_keys=True, indent=2) + "\n```"
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments"
    req = urllib.request.Request(url, data=json.dumps({"body": body}).encode(), method="POST", headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "aiops2-existing-host-observer",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        if response.status != 201:
            raise RuntimeError("report publication failed")

if __name__ == "__main__":
    report = collect()
    print(json.dumps(report, sort_keys=True))
    if os.environ.get("AIOPS_PUBLISH") == "1":
        publish(report)
