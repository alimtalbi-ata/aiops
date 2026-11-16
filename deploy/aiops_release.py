#!/usr/bin/env python3
"""Read-only rootless AIOps 2.0 deployment audit.

Writes only a local JSON report. No container, image, network, volume or DB changes.
Never serializes Docker environment variables or resolved Compose environment.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.PIPE).strip()


def docker_guard():
    expected = "/home/aiops/.local/share/docker"
    if os.environ.get("DOCKER_HOST") != "unix:///run/user/1001/docker.sock":
        raise RuntimeError("REFUSED: DOCKER_HOST must select isolated rootless socket")
    if os.environ.get("XDG_RUNTIME_DIR") != "/run/user/1001":
        raise RuntimeError("REFUSED: XDG_RUNTIME_DIR must select isolated rootless user")
    actual = run("docker", "info", "--format", "{{.DockerRootDir}}")
    opts = json.loads(run("docker", "info", "--format", "{{json .SecurityOptions}}"))
    if actual != expected or "name=rootless" not in opts:
        raise RuntimeError("REFUSED: Docker rootless identity check failed")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(1048576), b""):
            h.update(piece)
    return h.hexdigest()


def audit(kit, repo, override):
    docker_guard()
    if not all(p.is_file() for p in [kit / "compose.yml", kit / ".env", override]):
        raise RuntimeError("REFUSED: compose, env or override absent")
    # stdout is never emitted: Compose contains resolved secret values.
    raw = run("docker", "compose", "-f", str(kit / "compose.yml"),
              "-f", str(override), "--env-file", str(kit / ".env"),
              "config", "--format", "json", cwd=str(kit))
    config = json.loads(raw)
    service_names = set(config["services"])
    ids = run("docker", "ps", "-q", "--filter", "label=com.docker.compose.project=aiops2-rebuild").splitlines()
    if not ids:
        raise RuntimeError("REFUSED: isolated stack not found")
    containers = json.loads(run("docker", "inspect", *ids))
    image_ids = sorted({item["Image"] for item in containers})
    image_objects = json.loads(run("docker", "image", "inspect", *image_ids))
    image_by_id = {obj["Id"]: obj for obj in image_objects}
    entries = []
    problems = []
    for item in containers:
        labels = item.get("Config", {}).get("Labels") or {}
        service = labels.get("com.docker.compose.service")
        name = item["Name"].lstrip("/")
        if service not in service_names:
            problems.append("unexpected_service:" + name)
            continue
        expected = {config["networks"][n].get("name") or
                    (config.get("name", "aiops2-rebuild") + "_" + n)
                    for n in config["services"][service].get("networks", {})}
        observed = set(item["NetworkSettings"]["Networks"])
        if expected != observed:
            problems.append("network_mismatch:" + service)
        image_labels = (image_by_id[item["Image"]].get("Config", {}).get("Labels") or {})
        declared_revision = image_labels.get("org.opencontainers.image.revision")
        source = image_labels.get("org.opencontainers.image.source")
        image_match = image_by_id[item["Image"]]["Id"] == item["Image"]
        if not image_match:
            problems.append("image_identity_mismatch:" + service)
        entries.append({
            "name": name, "service": service,
            "state": item["State"]["Status"],
            "health": item["State"].get("Health", {}).get("Status", "not_defined"),
            "image_reference": item["Config"]["Image"],
            "image_id": item["Image"],
            "oci_revision": declared_revision,
            "oci_source": source,
            "oci_version": image_labels.get("org.opencontainers.image.version"),
            "image_identity_match": image_match,
            "provenance_status": "DECLARED_UNVERIFIED" if declared_revision else "MISSING",
            "network_expected": sorted(expected),
            "network_observed": sorted(observed),
            "network_match": expected == observed,
        })
    if len(containers) != len(entries):
        problems.append("container_inventory_incomplete")
    path_hashes = {}
    for rel in ("compose.yml", "app/intelligence/main.py",
                "app/worker/main.py", "app/core/main.py"):
        path = kit / rel
        if path.is_file():
            path_hashes[rel] = sha256(path)
    path_hashes["connectivity_override"] = sha256(override)
    # The Git commit describes reference code, not provenance of the running images.
    try:
        git_head = run("git", "rev-parse", "HEAD", cwd=str(repo))
        git_branch = run("git", "branch", "--show-current", cwd=str(repo))
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_head, git_branch = None, None
    return {
        "schema": "aiops-release-audit-v1",
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "environment": "aiops2-rebuild rootless isolated",
        "repo_reference_branch": git_branch,
        "repo_reference_commit": git_head,
        "deployed_git_commit": None,
        "source_digests_sha256": path_hashes,
        "containers": sorted(entries, key=lambda x: x["name"]),
        "container_count": len(entries),
        "provenance_summary": {
            "oci_revision_present": sum(bool(e["oci_revision"]) for e in entries),
            "oci_revision_missing": sum(not e["oci_revision"] for e in entries),
            "meaning": "OCI revisions are declared metadata, not verified build-to-source attestations."
        },
        "validation": {"network_alignment": "PASS" if not problems else "FAIL",
                       "problems": sorted(problems)},
        "limitations": [
            "Manifest is observational, not cryptographically signed.",
            "Git reference is not proof of deployed image provenance.",
            "OCI labels, even when present, do not independently attest build provenance.",
            "Application/API/DGX connectivity and backups are not validated.",
            "Only running containers are inventoried; stopped services need separate review."
        ]
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["audit", "qualify", "deploy", "rollback"])
    p.add_argument("--kit", type=Path, default=Path("/home/aiops/aiops2-rebuild-kit"))
    p.add_argument("--repo", type=Path, default=Path("/home/aiops/git/aiops"))
    p.add_argument("--override", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("/home/aiops/aiops2-audit"))
    args = p.parse_args()
    if args.action != "audit":
        print("REFUSED: only read-only audit is implemented; no deployment permitted", file=sys.stderr)
        return 2
    try:
        data = audit(args.kit.resolve(), args.repo.resolve(), args.override.resolve())
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = args.output_dir / ("release-audit-" + stamp + ".json")
        # restrictive mode; no secrets are intentionally included.
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        print("AUDIT_PATH=", path)
        print("CONTAINERS=", data["container_count"])
        print("NETWORK_ALIGNMENT=", data["validation"]["network_alignment"])
        print("OCI_REVISION_PRESENT=", data["provenance_summary"]["oci_revision_present"])
        print("OCI_REVISION_MISSING=", data["provenance_summary"]["oci_revision_missing"])
        print("DEPLOYED_GIT_COMMIT=UNVERIFIED")
        return 0 if data["validation"]["network_alignment"] == "PASS" else 1
    except (RuntimeError, OSError, subprocess.CalledProcessError, ValueError, KeyError) as exc:
        print("AUDIT=FAIL", type(exc).__name__, str(exc)[:180] if isinstance(exc, RuntimeError) else "", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
