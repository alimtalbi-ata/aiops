#!/usr/bin/env python3
"""Read-only Docker rootless inventory for AIOPS2. Never reads container env or secrets."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

SAFE_LABELS = (
    "com.docker.compose.project",
    "com.docker.compose.service",
    "com.docker.compose.project.config_files",
    "com.docker.compose.project.working_dir",
)
TEST_PROJECTS = {
    "aiops2-e2e-v1", "aiops2-v27-qual", "aiops2-demo-observability"
}
CORE_PROJECTS = {"aiops2-rebuild", "aiops2-metrics-cutover"}


def docker(*args):
    result = subprocess.run(
        ["docker", *args], text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(f"docker {args[0]} failed (exit {result.returncode}): "
                           "check the rootless context and permissions")
    return result.stdout


def inspect(kind, identifiers):
    if not identifiers:
        return []
    return json.loads(docker(kind, "inspect", *identifiers))


def lifecycle(project):
    if project in TEST_PROJECTS:
        return "STOP_CANDIDATE_AFTER_VALIDATION"
    if project in CORE_PROJECTS:
        return "RUN_CANDIDATE_VERIFY"
    return "UNKNOWN"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Local directory for sanitized reports")
    args = parser.parse_args()

    if os.geteuid() == 0:
        sys.exit("Refusing root execution; run as the aiops rootless user")
    context = docker("context", "show").strip()
    info = json.loads(docker("info", "--format", "{{json .}}"))
    root = info.get("DockerRootDir", "")
    if context != "rootless" or root != str(Path.home() / ".local/share/docker"):
        sys.exit("Refusing non-rootless context or unexpected DockerRootDir")

    ids = docker("ps", "-aq").split()
    containers = inspect("container", ids)
    volume_names = docker("volume", "ls", "-q").split()
    volumes = inspect("volume", volume_names)
    networks = inspect("network", docker("network", "ls", "-q").split())

    result = {
        "captured_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "docker_context": context,
        "docker_root_dir": root,
        "containers": [],
        "volumes": [],
        "networks": [],
    }
    volume_uses = {}
    for c in containers:
        labels = c.get("Config", {}).get("Labels") or {}
        project = labels.get("com.docker.compose.project", "")
        mounts = []
        for m in c.get("Mounts", []):
            item = {
                "type": m.get("Type"),
                "name": m.get("Name"),
                "source": m.get("Source"),
                "destination": m.get("Destination"),
                "rw": m.get("RW"),
            }
            mounts.append(item)
            if m.get("Type") == "volume" and m.get("Name"):
                volume_uses.setdefault(m["Name"], []).append({
                    "container": c.get("Name", "").lstrip("/"),
                    "destination": m.get("Destination"),
                    "running": c.get("State", {}).get("Running", False),
                })
        result["containers"].append({
            "name": c.get("Name", "").lstrip("/"),
            "id": c.get("Id"),
            "image_reference": c.get("Config", {}).get("Image"),
            "image_id": c.get("Image"),
            "status": c.get("State", {}).get("Status"),
            "health": (c.get("State", {}).get("Health") or {}).get("Status"),
            "created": c.get("Created"),
            "labels": {k: labels.get(k, "") for k in SAFE_LABELS},
            "networks": sorted((c.get("NetworkSettings", {}).get("Networks") or {}).keys()),
            "published_ports": [
                {"container_port": p.get("PrivatePort"), "host_port": p.get("PublicPort"),
                 "protocol": p.get("Type")}
                for p in (c.get("NetworkSettings", {}).get("Ports") or {}).values()
                if p for p in p if p.get("HostPort")
            ],
            "mounts": mounts,
            "lifecycle_candidate": lifecycle(project),
        })

    for v in volumes:
        name = v.get("Name")
        result["volumes"].append({
            "name": name,
            "driver": v.get("Driver"),
            "compose_project": (v.get("Labels") or {}).get("com.docker.compose.project", ""),
            "uses": volume_uses.get(name, []),
            "unused_by_existing_containers": not bool(volume_uses.get(name)),
        })

    for n in networks:
        result["networks"].append({
            "name": n.get("Name"),
            "id": n.get("Id"),
            "driver": n.get("Driver"),
            "internal": n.get("Internal"),
            "compose_project": (n.get("Labels") or {}).get("com.docker.compose.project", ""),
        })

    out = Path(args.out).expanduser().resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    data_file = out / "inventory.json"
    data_file.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    os.chmod(data_file, 0o600)

    lines = [
        "# AIOPS2 rootless Docker inventory",
        "",
        f"Captured UTC: {result['captured_utc']}",
        "",
        f"Containers: {len(result['containers'])}; volumes: {len(result['volumes'])}; networks: {len(result['networks'])}",
        "",
        "| Container | State | Compose project | Service | Proposed classification |",
        "|---|---|---|---|---|",
    ]
    for c in sorted(result["containers"], key=lambda x: x["name"]):
        labels = c["labels"]
        cells = [c["name"], c["status"],
                 labels.get("com.docker.compose.project") or "unlabeled",
                 labels.get("com.docker.compose.service") or "unlabeled",
                 c["lifecycle_candidate"]]
        lines.append("| " + " | ".join(str(x).replace("|", "/").replace("\n", " ")
                                      for x in cells) + " |")
    lines += [
        "",
        "## Important",
        "",
        "- Classification is provisional; never use this report as an automatic stop list.",
        "- Check dependencies, volume backups, FS bridge and Prometheus mounts before changes.",
        "- JSON excludes environment values, secret values and raw Docker labels.",
        "- Paths, container names and topology may still be sensitive: review before GitHub publication.",
        "- No Docker start/stop/up/down/rm/prune commands were executed.",
    ]
    md_file = out / "inventory.md"
    md_file.write_text("\n".join(lines) + "\n")
    os.chmod(md_file, 0o600)
    print(f"Inventory written to {out} ({len(containers)} containers).")
    print("Review and redact both files before sharing; do not commit them blindly.")


if __name__ == "__main__":
    main()
