#!/usr/bin/env python3
"""Read-only candidate source qualification; NEVER builds or deploys.

Compare release-critical sources against an explicit Git commit using Git blobs
and hash of deployment files. Output is a local non-secret manifest.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

COMPONENTS = ("core", "twin", "evidence", "policy", "intelligence", "copilot",
              "worker", "simulator", "portal")


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, stderr=subprocess.PIPE)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path("/home/aiops/git/aiops"))
    p.add_argument("--kit", type=Path, default=Path("/home/aiops/aiops2-rebuild-kit"))
    p.add_argument("--commit", required=True, help="Full 40-character commit SHA")
    p.add_argument("--output-dir", type=Path, default=Path("/home/aiops/aiops2-audit"))
    args = p.parse_args()
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
            raise ValueError("full 40-character SHA is mandatory")
        repo, kit = args.repo.resolve(), args.kit.resolve()
        commit = run("git", "rev-parse", "--verify", args.commit+"^{commit}", cwd=repo).decode().strip()
        if commit != args.commit:
            raise ValueError("git commit mismatch")
        paths = run("git", "ls-tree", "-r", "--name-only", commit, cwd=repo).decode().splitlines()
        selected = [name for name in paths if name == "compose.yml" or
                    name.startswith(("app/", "deploy/", "db/migrations/"))]
        result = {"identical": [], "modified": [], "missing": []}
        for name in selected:
            candidate = kit / name
            if not candidate.is_file() or candidate.is_symlink():
                result["missing"].append(name)
                continue
            tracked = run("git", "show", commit+":"+name, cwd=repo)
            key = "identical" if sha(candidate.read_bytes()) == sha(tracked) else "modified"
            result[key].append(name)
        untracked = []
        # Never scan env files or runtime data.
        for directory in ("app", "deploy", "db/migrations"):
            d = kit / directory
            if d.is_dir():
                for file in d.rglob("*"):
                    if file.is_file() and not file.is_symlink():
                        rel = file.relative_to(kit).as_posix()
                        if rel not in paths and not any(part in ("__pycache__", ".git", ".venv") for part in file.parts):
                            if not file.name.startswith(".env") and file.suffix not in (".key", ".pem", ".db", ".sqlite"):
                                untracked.append(rel)
        ok = not result["modified"] and not result["missing"]
        report = {
            "schema": "aiops-candidate-source-qualification-v1",
            "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "reference_commit": commit,
            "status": "PASS" if ok else "FAIL",
            "counts": {k:len(v) for k,v in result.items()},
            "differences": {k:v[:150] for k,v in result.items() if k != "identical"},
            "extra_local_files": sorted(untracked)[:150],
            "limitation": "Hash equality of selected files does not attest running image provenance, or validate dependencies, build context, secrets, or runtime behavior.",
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        destination = args.output_dir / ("source-qualification-"+stamp+".json")
        with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),"w") as f:
            json.dump(report,f,indent=2)
            f.write("\n")
        print("SOURCE_QUALIFICATION=",report["status"])
        print("REFERENCE_COMMIT=",commit)
        print("IDENTICAL=",len(result["identical"]))
        print("MODIFIED=",len(result["modified"]))
        print("MISSING=",len(result["missing"]))
        print("EXTRA_LOCAL_FILES=",len(untracked))
        print("REPORT_PATH=",destination)
        return 0 if ok else 1
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print("SOURCE_QUALIFICATION=FAIL",type(exc).__name__,file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
