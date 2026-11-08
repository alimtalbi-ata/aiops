#!/usr/bin/env python3
"""Offline, loss-aware adapter for the existing Debian reporter v1 JSON.

No network, Docker, host modifications or automatic publication.
Never infer immutable image IDs, Compose identity or source provenance.
"""
import argparse
import json
from pathlib import Path


def adapt(legacy):
    if legacy.get("schema_version") != 1:
        raise ValueError("expected existing Debian reporter schema_version=1")
    docker = legacy.get("docker")
    if not isinstance(docker, dict) or not isinstance(docker.get("containers"), list):
        raise ValueError("missing docker containers")
    errors = []
    if not docker.get("available"):
        errors.append("legacy_docker_unavailable")
    if docker.get("truncated"):
        errors.append("legacy_container_list_truncated")
    containers = []
    seen = set()
    for c in docker["containers"]:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not c["name"]:
            raise ValueError("invalid container entry")
        if c["name"] in seen:
            raise ValueError("duplicate container name")
        seen.add(c["name"])
        if c.get("inspect_ok") is False:
            errors.append("legacy_inspect_failed:" + c["name"])
        containers.append({
            "name": c["name"], "image_id": None,
            "configured_image": c.get("image"),
            "state": c.get("state"), "health": c.get("health"),
            "compose": {}, "mounts": [], "networks": [],
        })
    return {
        "schema": "aiops2-debian-provenance-v1",
        "captured_at_utc": legacy.get("collected_at"),
        "window_start_utc": None,
        "host": (legacy.get("host") or {}).get("reported_name"),
        "scope": "adapted_existing_reporter_v1_no_immutable_provenance",
        "containers": containers, "images": [], "compose_files": [],
        "errors": errors,
        "warnings": [
            "Legacy reporter image is a mutable name/tag, not an immutable image ID.",
            "Legacy report has no Compose project/service labels, mounts, source commit, deployment chronology or backup.",
            "Absence of mounts/Compose data here means UNKNOWN, not absent on Debian.",
            "Adapted data is not a replacement for the read-only provenance collector.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("existing_report", type=Path)
    args = parser.parse_args()
    print(json.dumps(adapt(json.loads(args.existing_report.read_text(encoding="utf-8"))),
                     indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
