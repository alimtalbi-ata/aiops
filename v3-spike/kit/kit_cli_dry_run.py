#!/usr/bin/env python3
"""AIOPS-V3 kit command planner. Dry-run only: never invokes Docker or changes hosts.

This is a development gate, NOT a deployable installer. The future installer
must retain this single canonical Compose path and fail closed on OCI provenance.
"""
import argparse
import json
import pathlib
import re
import sys

COMPOSE = pathlib.Path(__file__).resolve().parents[1] / "product" / "docker-compose.yml"
ACTIONS = ("preflight", "install", "health", "upgrade", "rollback", "backup", "restore")
IMAGE_KEYS = ("CORE", "TEMPORAL", "WORKER", "POLICY", "HITL", "EVIDENCE", "GAMMA", "DEMO")
DIGEST = re.compile(r"^[a-z0-9][a-z0-9._:/-]*@sha256:[0-9a-f]{64}$")


def plan(action, profile, images, compose=COMPOSE):
    if action not in ACTIONS:
        raise ValueError("unsupported action")
    if profile not in ("default", "demo"):
        raise ValueError("unsupported profile")
    compose = pathlib.Path(compose)
    if compose.resolve() != COMPOSE.resolve() or not compose.is_file():
        raise ValueError("canonical docker-compose.yml missing")
    required = IMAGE_KEYS if profile == "demo" else IMAGE_KEYS[:-1]
    missing = [key + "_IMAGE" for key in required if not DIGEST.fullmatch(images.get(key + "_IMAGE", ""))]
    if missing:
        raise ValueError("missing or unverified digest-shaped image references: " + ", ".join(missing))
    # Digest syntax is NOT independent provenance; never treat it as promotion proof.
    command = ["docker", "compose", "-f", str(compose)]
    if profile == "demo":
        command += ["--profile", "demo"]
    return {
        "action": action, "profile": profile, "compose": str(compose),
        "command_prefix": command, "mode": "dry-run",
        "executes": False, "runtime_qualified": False,
        "oci_provenance_verified": False, "production_authorized": False,
        "note": "Plan only; OCI license/SBOM/provenance and runtime gates not implemented",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("--profile", choices=("default", "demo"), default="default")
    parser.add_argument("--images-json", required=True, type=pathlib.Path,
                        help="local JSON of image references; never commit secrets")
    args = parser.parse_args(argv)
    try:
        images = json.loads(args.images_json.read_text(encoding="utf-8"))
        if not isinstance(images, dict):
            raise ValueError("images JSON must be an object")
        print(json.dumps(plan(args.action, args.profile, images), indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print("FAIL closed: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
