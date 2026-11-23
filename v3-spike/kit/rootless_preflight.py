#!/usr/bin/env python3
"""Fail-closed rootless Docker preflight for an isolated NEW AIOPS-V3 host.

This check never starts containers or mutates Docker/host state. It deliberately
rejects the current draft Compose named-volume topology until persistence is
explicitly confined to the installation root.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

CANONICAL = Path(__file__).resolve().parents[1] / "product" / "docker-compose.yml"
IMAGE_KEYS = ("CORE", "TEMPORAL", "WORKER", "POLICY", "HITL", "EVIDENCE", "GAMMA")
DIGEST = re.compile(r"^[a-z0-9][a-z0-9._:/-]*@sha256:[0-9a-f]{64}$")


def validate_root(root):
    root = Path(root)
    if not root.is_absolute() or str(root) == "/" or ".." in root.parts:
        raise ValueError("installation root must be absolute, non-root and normalized")
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError("installation root and its ancestors must not be symlinks")
    return root.resolve(strict=False)


def validate_daemon(info, docker_host, uid, root):
    if not isinstance(info, dict):
        raise ValueError("docker info must be JSON object")
    opts = info.get("SecurityOptions", [])
    if not isinstance(opts, list) or not any(isinstance(x, str) and x.strip().lower() in ("rootless", "name=rootless") for x in opts):
        raise ValueError("Docker daemon is not attested rootless")
    expected = f"unix:///run/user/{uid}/docker.sock"
    if docker_host != expected:
        raise ValueError("DOCKER_HOST must reference the current user's rootless socket")
    docker_root = Path(info.get("DockerRootDir", ""))
    if not docker_root.is_absolute() or not docker_root.resolve(strict=False).is_relative_to(root):
        raise ValueError("DockerRootDir must be inside installation root")


def validate_images(env, profile):
    keys = IMAGE_KEYS + (("DEMO",) if profile == "demo" else ())
    missing = [k for k in keys if not DIGEST.fullmatch(env.get(k + "_IMAGE", ""))]
    if missing:
        raise ValueError("digest-shaped references missing: " + ", ".join(missing))


def validate_compose(graph, root, profile):
    if not isinstance(graph, dict) or not isinstance(graph.get("services"), dict):
        raise ValueError("invalid normalized Compose graph")
    required = set(k.lower() for k in IMAGE_KEYS)
    expected = required | ({"demo"} if profile == "demo" else set())
    if set(graph["services"]) != expected:
        raise ValueError("unexpected service set")
    # Named volumes are accepted only when the rootless Docker data root is
    # attested inside root. Bind mounts must independently stay within root.
    for service in graph["services"].values():
        if service.get("privileged") or service.get("network_mode") == "host":
            raise ValueError("unsafe container privileges")
        for mount in service.get("volumes", []):
            if mount.get("type") == "bind":
                source = Path(mount.get("source", ""))
                if not source.is_absolute() or not source.resolve(strict=False).is_relative_to(root):
                    raise ValueError("bind mount escapes installation root")
            elif mount.get("type") != "volume":
                raise ValueError("unsupported mount type")
    for config in graph.get("volumes", {}).values():
        if not isinstance(config, dict) or config.get("external") or config.get("driver_opts"):
            raise ValueError("external/driver-configured volume forbidden")


def run(root, profile, env=None, command=None):
    env = os.environ if env is None else env
    root = validate_root(root)
    if profile not in ("default", "demo"):
        raise ValueError("invalid profile")
    validate_images(env, profile)
    if not CANONICAL.is_file():
        raise ValueError("canonical Compose missing")
    if not env.get("DOCKER_HOST"):
        raise ValueError("DOCKER_HOST missing; rootful default forbidden")
    command = subprocess.run if command is None else command
    info_result = command(["docker", "info", "--format", "{{json .}}"], capture_output=True, text=True, check=True, env=env)
    validate_daemon(json.loads(info_result.stdout), env["DOCKER_HOST"], os.getuid(), root)
    cmd = ["docker", "compose", "-f", str(CANONICAL)]
    if profile == "demo":
        cmd += ["--profile", "demo"]
    config_result = command(cmd + ["config", "--format", "json"], capture_output=True, text=True, check=True, env=env)
    validate_compose(json.loads(config_result.stdout), root, profile)
    return {"status": "PASS", "mode": "preflight-only", "root": str(root), "profile": profile,
            "runtime_installed": False, "oci_provenance_verified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", help="new-host root, e.g. /srv/aiops-v3")
    parser.add_argument("--profile", choices=("default", "demo"), default="default")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.root, args.profile)))
    except (ValueError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        parser.exit(2, f"FAIL closed: {exc}\n")


if __name__ == "__main__":
    main()
