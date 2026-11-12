#!/usr/bin/env python3
"""AIOPS2 host telemetry only; no business read models or mutations."""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import time

BASE = Path(os.environ.get("AIOPS_COLLECT_DIR", "/home/aiops/.local/state/aiops2-observe"))
UID = 1001
TIMEOUT = 5
KEEP = 24
def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()
def cmd(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT,
                           env={"PATH": "/usr/local/bin:/usr/bin:/bin",
                                "HOME": "/home/aiops",
                                "XDG_RUNTIME_DIR": "/run/user/1001",
                                "DOCKER_HOST": "unix:///run/user/1001/docker.sock"})
        if p.returncode:
            return {"state": "UNKNOWN", "reason": "COMMAND_FAILED", "exit_code": p.returncode}
        return {"state": "OBSERVED", "value": p.stdout.strip()[:12000]}
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return {"state": "UNKNOWN", "reason": "COMMAND_UNAVAILABLE"}
def inventory_count(args):
    """Count metadata identifiers without persisting raw names or command output."""
    try:
        p = subprocess.run(args, capture_output=True, timeout=TIMEOUT,
                           env={"PATH": "/usr/local/bin:/usr/bin:/bin",
                                "HOME": "/home/aiops",
                                "XDG_RUNTIME_DIR": "/run/user/1001",
                                "DOCKER_HOST": "unix:///run/user/1001/docker.sock"})
        if p.returncode:
            return {"state": "UNKNOWN", "reason": "COUNT_FAILED", "exit_code": p.returncode}
        return {"state": "OBSERVED", "count": len(p.stdout.splitlines())}
    except (OSError, subprocess.TimeoutExpired):
        return {"state": "UNKNOWN", "reason": "COUNT_UNAVAILABLE"}

def inventory(result, count, limit=150):
    if result["state"] != "OBSERVED" or count["state"] != "OBSERVED":
        return {"state": "UNKNOWN", "reason": "INVENTORY_UNVERIFIED", "items": [],
                "count": count}
    # Fail closed on malformed/untrusted count envelopes, not TypeError/false completeness.
    n = count.get("count")
    if type(n) is not int or n < 0 or type(limit) is not int or limit < 1 or not isinstance(result.get("value"), str):
        return {"state": "UNKNOWN", "reason": "INVENTORY_COUNT_INVALID",
                "items": [], "complete": False}
    rows = result["value"].splitlines()
    if len(rows) > limit or n != len(rows):
        reason = "INVENTORY_COUNT_MISMATCH" if count["count"] < len(rows) else "INVENTORY_TRUNCATED"
        return {"state": "UNKNOWN", "reason": reason,
                "items": [], "count": count["count"], "complete": False}
    return {"state": "OBSERVED", "items": rows, "count": count["count"], "complete": True}

def safe_lines(result, limit=100):
    if result["state"] != "OBSERVED":
        return result
    return {"state": "OBSERVED", "value": result["value"].splitlines()[:limit]}
def has_symlink_ancestor(path):
    """Reject symlink components before creating or writing output files."""
    return any(part.is_symlink() for part in (path, *path.parents))

def main():
    if os.getuid() != UID:
        print("collector must run as aiops UID 1001", file=sys.stderr)
        return 3
    os.umask(0o077)
    if has_symlink_ancestor(BASE):
        print("unsafe output path", file=sys.stderr)
        return 3
    BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if has_symlink_ancestor(BASE):
        print("unsafe output path", file=sys.stderr)
        return 3
    if BASE.is_symlink() or BASE.stat().st_uid != UID or BASE.stat().st_mode & 0o077:
        print("unsafe output directory", file=sys.stderr)
        return 3
    # Refuse symlinked or foreign-owned lockfiles before attempting flock.
    try:
        lock_fd = os.open(BASE / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != UID or lock_stat.st_mode & 0o077:
            os.close(lock_fd)
            print("unsafe lockfile", file=sys.stderr)
            return 3
    except OSError:
        print("unsafe lockfile", file=sys.stderr)
        return 3
    with os.fdopen(lock_fd, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 4
        report = {"schema": "aiops2.host-observation.v1", "collected_at": stamp(),
                  "host_uid": UID, "scope": "host_telemetry_not_business_read_model",
                  "sections": {}}
        s = report["sections"]
        # Explicitly select only metadata fields. No env, mounts, labels, commands, IPs or logs.
        # IDs and state only; never persist image repositories/tags or container names.
        s["containers"] = inventory(
            cmd(["docker", "ps", "-a", "--format", "{{.ID}}|{{.State}}"]),
            inventory_count(["docker", "ps", "-aq"]))
        s["images"] = inventory(
            cmd(["docker", "image", "ls", "-q", "--no-trunc"]),
            inventory_count(["docker", "image", "ls", "-q", "--no-trunc"]))
        s["docker_version"] = cmd(["docker", "version", "--format", "{{.Client.Version}}"])
        # Unit names and descriptions are free text; store only an aggregate count.
        # Failed systemctl remains UNKNOWN, not a fabricated zero.
        s["user_units"] = inventory_count(["systemctl", "--user", "list-units",
             "--type=service", "--all", "--no-legend", "--plain", "--no-pager"])
        # Only cron schedule presence, not command contents (may contain secrets).
        cron = cmd(["crontab", "-l"])
        s["cron"] = {"state": cron["state"], "entries": sum(
            bool(x.strip()) and not x.lstrip().startswith("#")
            for x in cron.get("value", "").splitlines())} if cron["state"] == "OBSERVED" else cron
        s["kernel"] = cmd(["uname", "-r"])
        s["uptime"] = cmd(["uptime", "-p"])
        s["memory"] = safe_lines(cmd(["free", "-b"]), 5)
        s["disk"] = safe_lines(cmd(["df", "-P", "-B1", "/"]), 3)
        s["cpu_load"] = {"state": "OBSERVED", "value": list(os.getloadavg())}
        # No raw journal, docker events, or application logs: unsafe free text.
        s["events"] = {"state": "UNKNOWN", "reason": "SAFE_EVENT_SOURCE_NOT_CONFIGURED"}
        s["logs"] = {"state": "UNKNOWN", "reason": "REDACTED_LOG_SOURCE_NOT_CONFIGURED"}
        s["health_endpoints"] = {"state": "UNKNOWN", "reason": "ALLOWLIST_NOT_CONFIGURED"}
        report["state"] = "OBSERVED" if all(
            v.get("state") == "OBSERVED" for v in s.values()) else "UNKNOWN"
        name = "host-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
        fd, tmp = tempfile.mkstemp(prefix=".host-", dir=BASE)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(report, f, sort_keys=True, separators=(",", ":"))
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, BASE / name)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        for old in sorted(BASE.glob("host-*.json"), reverse=True)[KEEP:]:
            if old.is_file() and not old.is_symlink():
                old.unlink()
        print(str(BASE / name))
        return 0 if report["state"] == "OBSERVED" else 2
if __name__ == "__main__":
    sys.exit(main())
