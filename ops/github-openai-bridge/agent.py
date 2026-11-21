#!/usr/bin/env python3
"""GitHub issue command queue -> Debian -> GitHub receipt. No Codex dependency.

No OpenAI API, Codex, shell execution, Docker or deployment.
Only comments by BRIDGE_AUTHORIZED_LOGIN on BRIDGE_ISSUE are considered.
"""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPO = "alimtalbi-ata/aiops"
ISSUE = int(os.environ.get("BRIDGE_ISSUE", "464"))
LOGIN = os.environ.get("BRIDGE_AUTHORIZED_LOGIN", "alimtalbi-ata")
PREFIX = "AIOPS2_BRIDGE_V1 "
COMMAND = re.compile(r"^AIOPS2_BRIDGE_V1 (status|acme_receipt_status) ([0-9a-f]{32}) ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)$")
STATE = Path(os.environ.get("BRIDGE_STATE_DIR", str(Path.home()/".local/state/aiops2-github-openai-bridge")))

def gh(*args):
    p = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError("GitHub request failed")
    return json.loads(p.stdout)

def post(body):
    p = subprocess.run(["gh", "issue", "comment", str(ISSUE), "--repo", REPO, "--body", body],
                       capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError("GitHub receipt publication failed")

def parse(comment, now):
    if (comment.get("user") or {}).get("login") != LOGIN:
        return None
    if comment.get("html_url", "").split("#")[0] != f"https://github.com/{REPO}/issues/{ISSUE}":
        return None
    m = COMMAND.fullmatch((comment.get("body") or "").strip())
    if not m:
        return None
    action, correlation, expiry = m.groups()
    deadline = dt.datetime.strptime(expiry, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if not now < deadline <= now + dt.timedelta(hours=2):
        return None
    return action, correlation

def acme_receipt_status():
    """Fixed-path, read-only metadata: never returns identifiers or receipt contents."""
    path = Path("/home/aiops/.local/state/aiops-debian-agent/acme-sim-e2e.json")
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            return {"status": "NOT_AVAILABLE"}
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return {"status": "INVALID"}
        allowed = {"PASS", "FAIL", "BLOCKED"}
        result = value.get("status")
        if type(result) is not str or result not in allowed:
            return {"status": "INVALID"}
        schema_valid = value.get("schema") == "aiops.debian-acme-sim-e2e.v1"
        sandbox_only = (value.get("tenant_id") == "ACME-TEST"
                        and value.get("scenario_id") == "ACME-SAN-PAYMENTS"
                        and value.get("mode") == "SIMULATION"
                        and value.get("approval_issuer") == "TWIN_ACME_SIMULATED"
                        and value.get("human_approval_claimed") is False
                        and value.get("live_effects_allowed") is False
                        and value.get("real_glpi_writes_allowed") is False
                        and value.get("docker_mutations") == 0)
        timestamp = value.get("collected_at")
        fresh = False
        if type(timestamp) is str:
            try:
                observed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if observed.tzinfo is not None:
                    age = dt.datetime.now(dt.timezone.utc) - observed.astimezone(dt.timezone.utc)
                    fresh = dt.timedelta(0) <= age <= dt.timedelta(minutes=60)
            except ValueError:
                pass
        return {"status": "OBSERVED", "e2e_status": result,
                "fresh_60m": fresh,
                "schema_valid": schema_valid,
                "sandbox_only": sandbox_only,
                "note": "Metadata only; not a readiness verdict or deployed-SHA attestation"}
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return {"status": "NOT_AVAILABLE"}


def main():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    with (STATE/"agent.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        now = dt.datetime.now(dt.timezone.utc)
        comments = []
        for page in range(1, 21):
            batch = gh("--method", "GET", f"repos/{REPO}/issues/{ISSUE}/comments",
                       "-f", "per_page=100", "-f", f"page={page}")
            if not isinstance(batch, list) or len(batch) > 100:
                raise ValueError("Invalid GitHub queue")
            comments.extend(batch)
            if len(batch) < 100:
                break
        else:
            raise ValueError("Queue exceeds 2000 comments")
        for comment in sorted(comments, key=lambda c: c.get("id", 0)):
            command = parse(comment, now)
            if command is None:
                continue
            action, correlation = command
            cid = comment["id"]
            receipt = STATE/f"comment-{cid}.json"
            if receipt.exists():
                continue
            # Reserve before side effects; never retry an uncertain execution.
            with receipt.open("x") as f:
                json.dump({"status": "STARTED", "comment_id": cid, "correlation_id": correlation}, f)
            os.chmod(receipt, 0o600)
            try:
                result = ({"status": "OK", "hostname": os.uname().nodename,
                           "utc": now.isoformat()} if action == "status"
                          else acme_receipt_status())
            except Exception as exc:
                result = {"status": "FAILED", "error_type": type(exc).__name__}
            data = {"schema": "aiops2.github-openai-bridge.v1", "comment_id": cid,
                    "correlation_id": correlation, "action": action, "result": result}
            receipt.write_text(json.dumps(data, indent=2) + "\n")
            post("AIOPS2_BRIDGE_RECEIPT_V1\n\n```json\n" +
                 json.dumps(data, indent=2) + "\n```")
            print(json.dumps({"comment_id": cid, "status": result["status"]}))
            return 0
        print("NO_ELIGIBLE_COMMAND")
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("BRIDGE_FAILED:", type(exc).__name__, file=sys.stderr)
        sys.exit(2)
