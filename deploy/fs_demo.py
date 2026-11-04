#!/usr/bin/env python3
"""Synthetic-only filesystem remediation; never operates on real logs or filesystems."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path("/home/aiops/.local/state/aiops2-demo-filesystem")
RUN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
ACTIONS = {"cleanup-logs", "expand-fs"}

def safe_dir(path):
    if path.is_symlink():
        raise ValueError("symlink forbidden")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("unsafe directory")

def atomic(path, data):
    if path.is_symlink():
        raise ValueError("symlink forbidden")
    tmp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    try:
        with open(tmp, "x", encoding="utf-8") as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()

def dump(value):
    return json.dumps(value, sort_keys=True, indent=2) + "\n"

def operate(args):
    if os.environ.get("AIOPS_FS_DEMO_TEST_ROOT"):
        # Tests only: explicitly opt in; never usable as a production override.
        if os.environ.get("AIOPS_FS_DEMO_TEST_MODE") != "YES":
            raise ValueError("test root requires test mode")
        root = Path(os.environ["AIOPS_FS_DEMO_TEST_ROOT"])
    else:
        root = ROOT
        import pwd
        if pwd.getpwuid(os.geteuid()).pw_name != "aiops":
            raise PermissionError("must run as aiops")
    if not RUN.fullmatch(args.run_id):
        raise ValueError("invalid canonical run-id")
    safe_dir(root)
    safe_dir(root / "remediation")
    path = root / "remediation" / args.run_id
    safe_dir(path)
    lock = path / "lock"
    if lock.is_symlink():
        raise ValueError("unsafe lock")
    with open(lock, "a+") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        statefile = path / "state.json"
        if statefile.is_symlink():
            raise ValueError("unsafe state")
        state = json.loads(statefile.read_text()) if statefile.exists() else None
        if args.command == "init":
            if state is not None:
                raise ValueError("run already exists")
            state = dict(run_id=args.run_id, used_mib=11, capacity_mib=12,
                         logs_mib=5, incident="OPEN_SIMULATED", phase="OPEN",
                         proposed=None, action=None, rollback_closed=True)
        elif state is None:
            raise ValueError("run not initialized")
        elif args.command == "propose":
            if state["phase"] != "OPEN" or not state["rollback_closed"]:
                raise ValueError("pending action or rollback")
            state["proposed"] = "cleanup-logs"
        elif args.command in ACTIONS:
            if args.approval != "SYNTHETIC_APPROVED":
                raise PermissionError("explicit synthetic approval required")
            if state["phase"] != "OPEN" or not state["rollback_closed"]:
                raise ValueError("pending action; rollback required")
            if state["proposed"] is None:
                raise ValueError("propose first")
            state["action"] = args.command
            state["rollback_closed"] = False
            state["phase"] = "ACTION_APPLIED"
            if args.command == "cleanup-logs":
                state["used_mib"] = 6
                state["logs_mib"] = 0
            else:
                state["capacity_mib"] = 16
            state["incident"] = "MITIGATED_SIMULATED"
        elif args.command == "rollback":
            if args.approval != "SYNTHETIC_APPROVED" or state["phase"] != "ACTION_APPLIED":
                raise ValueError("rollback requires applied action and synthetic approval")
            state.update(used_mib=11, capacity_mib=12, logs_mib=5,
                         incident="OPEN_SIMULATED", phase="OPEN",
                         proposed=None, action=None, rollback_closed=True)
        elif args.command == "finalize":
            if state["phase"] != "ACTION_APPLIED" or state["rollback_closed"]:
                raise ValueError("no applied synthetic action")
            state["phase"] = "FINALIZED_SIMULATED"
            # Deliberately no second action until explicit rollback.
        elif args.command != "status":
            raise ValueError("unknown command")
        if args.command != "status":
            atomic(statefile, dump(state))
        raw = statefile.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        receipt = dict(run_id=args.run_id, command=args.command,
                       state_sha256=digest, incident=state["incident"],
                       proposed=state["proposed"], action=state["action"],
                       phase=state["phase"], used_mib=state["used_mib"],
                       capacity_mib=state["capacity_mib"], synthetic_only=True,
                       live_effects=False)
        if args.command != "status":
            atomic(path / "receipt.json", dump(receipt))
        print(dump(receipt), end="")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "propose", "status", "cleanup-logs", "expand-fs", "rollback", "finalize"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--approval", default="")
    args = parser.parse_args()
    try:
        operate(args)
    except (ValueError, PermissionError, OSError, KeyError, json.JSONDecodeError) as exc:
        print("FAIL_CLOSED: " + str(exc), file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
