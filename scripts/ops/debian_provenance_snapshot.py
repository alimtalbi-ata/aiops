#!/usr/bin/env python3
"""Read-only Debian runtime provenance snapshot. No credentials, env, or file contents.

This is a candidate for review, NOT installed in Debian cron. Run manually only
after operator review; it never changes Docker, Git, services or databases.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

UTC = dt.timezone.utc
LABEL_KEYS = (
    "com.docker.compose.project",
    "com.docker.compose.service",
    "com.docker.compose.project.config_files",
    "com.docker.compose.project.working_dir",
    "com.docker.compose.config-hash",
    "com.docker.compose.version",
)
# Configuration file paths may be included; NEVER collect environment variables,
# bind-mount file contents, container logs, labels beyond the allowlist or secrets.
MAX_CONTAINERS = 300
MAX_IMAGE_IDS = 300


def run(*args, timeout=20):
    try:
        p = subprocess.run(args, text=True, capture_output=True,
                           timeout=timeout, check=False)
        if p.returncode:
            return None, "command_failed:" + str(p.returncode)
        return p.stdout, None
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, type(exc).__name__


def docker_json(*args, timeout=30):
    out, err = run("docker", *args, timeout=timeout)
    if err:
        return None, err
    try:
        return json.loads(out), None
    except (ValueError, TypeError):
        return None, "invalid_json"


def sha256_file(path):
    try:
        p = Path(path)
        if not p.is_file() or p.is_symlink() or p.stat().st_size > 4 * 1024 * 1024:
            return None
        with p.open("rb") as f:
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def collect():
    now = dt.datetime.now(UTC)
    result = {
        "schema": "aiops2-debian-provenance-v1",
        "captured_at_utc": now.isoformat(),
        "window_start_utc": (now - dt.timedelta(hours=48)).isoformat(),
        "host": "SRV-DEB-05",
        "scope": "read_only_current_state_not_deployment_history",
        "warnings": [
            "Container Created and image Created are not proof of deployment time.",
            "No data or volume backup is performed by this script.",
            "No feature or integration test is executed by this script.",
            "Host identity and Git/source mapping require separate verification.",
        ],
        "containers": [],
        "images": [],
        "errors": [],
    }
    names_out, err = run("docker", "ps", "-a", "--format", "{{.Names}}")
    if err:
        result["errors"].append("docker_ps:" + err)
        return result
    names = [x for x in names_out.splitlines() if x]
    if len(names) > MAX_CONTAINERS:
        result["errors"].append("container_limit_exceeded")
        names = names[:MAX_CONTAINERS]
    image_ids = set()
    for name in names:
        obj, err = docker_json("inspect", "--type", "container", name)
        if err or not isinstance(obj, list) or len(obj) != 1:
            result["errors"].append("inspect_container:" + name + ":" + str(err))
            continue
        c = obj[0]
        labels = c.get("Config", {}).get("Labels") or {}
        image_id = c.get("Image") or None
        if image_id:
            image_ids.add(image_id)
        mounts = []
        for m in c.get("Mounts") or []:
            # Do not read files inside mounts. Names and paths only.
            mounts.append({
                "type": m.get("Type"),
                "name": m.get("Name"),
                "source": m.get("Source"),
                "destination": m.get("Destination"),
                "rw": m.get("RW"),
            })
        result["containers"].append({
            "name": c.get("Name", "").lstrip("/"),
            "id": c.get("Id"),
            "created": c.get("Created"),
            "image_id": image_id,
            "configured_image": (c.get("Config") or {}).get("Image"),
            "state": (c.get("State") or {}).get("Status"),
            "started_at": (c.get("State") or {}).get("StartedAt"),
            "finished_at": (c.get("State") or {}).get("FinishedAt"),
            "health": ((c.get("State") or {}).get("Health") or {}).get("Status"),
            "compose": {k: labels.get(k) for k in LABEL_KEYS if k in labels},
            "mounts": mounts,
            "networks": sorted(((c.get("NetworkSettings") or {}).get("Networks") or {}).keys()),
        })
    for image_id in sorted(image_ids)[:MAX_IMAGE_IDS]:
        obj, err = docker_json("image", "inspect", image_id)
        if err or not isinstance(obj, list) or len(obj) != 1:
            result["errors"].append("inspect_image:" + image_id + ":" + str(err))
            continue
        im = obj[0]
        result["images"].append({
            "id": im.get("Id"),
            "created": im.get("Created"),
            "repo_tags": im.get("RepoTags") or [],
            "repo_digests": im.get("RepoDigests") or [],
        })
    if len(image_ids) > MAX_IMAGE_IDS:
        result["errors"].append("image_limit_exceeded")
    # Hash only existing regular Compose files named by Docker's own allowlisted
    # Compose metadata. Never read .env, secrets, private keys or arbitrary files.
    seen = set()
    result["compose_files"] = []
    for c in result["containers"]:
        cfg = c["compose"].get("com.docker.compose.project.config_files", "")
        for path in cfg.split(","):
            path = path.strip()
            if not path or path in seen:
                continue
            seen.add(path)
            p = Path(path)
            if p.suffix.lower() not in (".yaml", ".yml"):
                continue
            result["compose_files"].append({"path": path, "sha256": sha256_file(path)})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON file (default: stdout)")
    args = parser.parse_args()
    report = collect()
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        # Explicit opt-in local output; never write to GitHub, Docker or cron.
        dest = Path(args.output)
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        print("created:" + str(dest))
    else:
        sys.stdout.write(payload)
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
