#!/usr/bin/env python3
"""Offline, read-only comparison of two AIOps2 provenance JSON snapshots.

Conservative: reports runtime identity drift and missing evidence, never declares
a candidate better, deployable or safely removable.
"""
import argparse
import json
from pathlib import Path


def index_containers(snapshot):
    result = {}
    for item in snapshot.get("containers", []):
        if not isinstance(item, dict):
            raise ValueError("container entry is not an object")
        name = item.get("name")
        if not isinstance(name, str) or not name or name in result:
            raise ValueError("missing or duplicate container name")
        result[name] = item
    return result


def identity(container):
    labels = container.get("compose") or {}
    return {
        "image_id": container.get("image_id"),
        "configured_image": container.get("configured_image"),
        "compose_project": labels.get("com.docker.compose.project"),
        "compose_service": labels.get("com.docker.compose.service"),
        "compose_config_hash": labels.get("com.docker.compose.config-hash"),
    }


def compare(before, after):
    if before.get("schema") != "aiops2-debian-provenance-v1" or after.get("schema") != "aiops2-debian-provenance-v1":
        raise ValueError("unsupported snapshot schema")
    old = index_containers(before)
    new = index_containers(after)
    changes = []
    for name in sorted(set(old) | set(new)):
        if name not in old:
            changes.append({"container": name, "kind": "ADDED", "new_identity": identity(new[name])})
        elif name not in new:
            changes.append({"container": name, "kind": "MISSING", "old_identity": identity(old[name])})
        elif identity(old[name]) != identity(new[name]):
            changes.append({"container": name, "kind": "IDENTITY_CHANGED",
                            "old_identity": identity(old[name]), "new_identity": identity(new[name])})
    old_compose = {f.get("path"): f.get("sha256") for f in before.get("compose_files", [])}
    new_compose = {f.get("path"): f.get("sha256") for f in after.get("compose_files", [])}
    compose_changes = []
    for path in sorted(set(old_compose) | set(new_compose)):
        if old_compose.get(path) != new_compose.get(path):
            compose_changes.append({"path": path, "old_sha256": old_compose.get(path),
                                    "new_sha256": new_compose.get(path)})
    errors = list(before.get("errors") or []) + list(after.get("errors") or [])
    return {
        "schema": "aiops2-debian-provenance-diff-v1",
        "before_captured_at_utc": before.get("captured_at_utc"),
        "after_captured_at_utc": after.get("captured_at_utc"),
        "changes": changes,
        "compose_changes": compose_changes,
        "source_mapping": "UNKNOWN",
        "deployment_chronology": "UNKNOWN",
        "backup_restoration": "NOT_ATTESTED",
        "feature_parity": "UNKNOWN",
        "integration_e2e": "NOT_ATTESTED",
        "release_decision": "HOLD",
        "warnings": [
            "A missing container may reflect incomplete Docker permissions or snapshot errors.",
            "A matching image ID does not prove source commit, features, backups or integration.",
            "Image/container timestamps do not prove the time of deployment.",
            "Never delete or replace a component based on this diff.",
        ],
        "snapshot_errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    print(json.dumps(compare(before, after), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
