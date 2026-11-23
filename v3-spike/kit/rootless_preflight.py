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


def validate_compose(graph, root, profile, env):
    if not isinstance(graph, dict) or not isinstance(graph.get("services"), dict):
        raise ValueError("invalid normalized Compose graph")
    required = set(k.lower() for k in IMAGE_KEYS)
    expected = required | ({"demo"} if profile == "demo" else set())
    if set(graph["services"]) != expected:
        raise ValueError("unexpected service set")
    # Bind every active normalized service image to its expected immutable OCI digest.
    validate_images(env, profile)
    for name, service in graph["services"].items():
        expected_image = env[name.upper() + "_IMAGE"]
        if not isinstance(service, dict) or not isinstance(service.get("image"), str):
            raise ValueError("missing normalized image for " + name)
        if not DIGEST.fullmatch(service["image"]) or service["image"] != expected_image:
            raise ValueError("normalized image digest mismatch for " + name)
    # Fail closed on the normalized graph, not on hand-picked YAML fragments.
    declared = graph.get("volumes", {})
    if not isinstance(declared, dict):
        raise ValueError("invalid declared volumes")
    for name, config in declared.items():
        if not isinstance(config, dict) or config.get("external") or config.get("driver_opts"):
            raise ValueError("external/driver-configured volume forbidden")
    for name, service in graph["services"].items():
        if not isinstance(service, dict) or service.get("privileged") or service.get("network_mode") == "host":
            raise ValueError("unsafe container privileges")
        # Deny namespace sharing, device injection and privilege additions even
        # when Compose normalizes them into explicit service keys.
        forbidden = ("network_mode", "pid", "ipc", "devices", "volumes_from",
                     "cap_add", "device_cgroup_rules", "device_requests",
                     "security_opt_extra", "cgroup_parent", "uts", "userns_mode")
        for key in forbidden:
            if key in service and service[key] not in (None, [], ""):
                raise ValueError("forbidden isolation setting: " + key)
        if str(service.get("user", "")).strip().lower() in ("root", "0", "0:0", "root:root", "0:root", "root:0"):
            raise ValueError("root container user forbidden")
        if service.get("user") is not None and not re.fullmatch(r"[1-9][0-9]*(?::[1-9][0-9]*)?", str(service["user"])):
            raise ValueError("container user must be numeric non-root")
        if service.get("read_only") is not True:
            raise ValueError("read_only required for " + name)
        if not isinstance(service.get("cap_drop"), list) or "ALL" not in [str(v).upper() for v in service["cap_drop"]]:
            raise ValueError("cap_drop ALL required for " + name)
        opts = service.get("security_opt")
        if not isinstance(opts, list) or "no-new-privileges:true" not in [str(v).lower() for v in opts]:
            raise ValueError("no-new-privileges required for " + name)
        ports = service.get("ports", [])
        if not isinstance(ports, list):
            raise ValueError("invalid ports")
        if name != "gamma" and ports:
            raise ValueError("only GAMMA may publish a port")
        if name == "gamma":
            if len(ports) != 1 or not isinstance(ports[0], dict):
                raise ValueError("GAMMA loopback port required")
            port = ports[0]
            if str(port.get("host_ip")) != "127.0.0.1" or str(port.get("published")) != "18080" or int(port.get("target", -1)) != 8080:
                raise ValueError("GAMMA port must be loopback-only")
        mounts = service.get("volumes", [])
        if not isinstance(mounts, list):
            raise ValueError("invalid mounts")
        for mount in mounts:
            if not isinstance(mount, dict):
                raise ValueError("invalid mount")
            if mount.get("type") == "bind":
                source = Path(mount.get("source", ""))
                if not source.is_absolute() or not source.resolve(strict=False).is_relative_to(root):
                    raise ValueError("bind mount escapes installation root")
                if mount.get("read_only") is not True:
                    raise ValueError("bind mount must be read-only")
            elif mount.get("type") == "volume":
                if mount.get("source") not in declared:
                    raise ValueError("undeclared named volume")
            else:
                raise ValueError("unsupported mount type")


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
    validate_compose(json.loads(config_result.stdout), root, profile, env)
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
