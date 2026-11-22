"""Fail-closed synthetic kit command planner; never invokes Docker or mutates hosts."""
import argparse
import json
import os
import re
from pathlib import Path

import yaml

ACTIONS = ("preflight", "install", "health", "upgrade", "rollback", "backup", "restore")
COMPOSE = "docker-compose.yml"
DIGEST = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}\Z")
IMAGE_VARIABLES = {"gamma": "GAMMA_IMAGE", "core": "CORE_IMAGE", "demo": "DEMO_IMAGE"}

class UniqueLoader(yaml.SafeLoader):
    pass

def _unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise ValueError("duplicate or non-string YAML mapping key")
        result[key] = loader.construct_object(value_node)
    return result

UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)

def _safe_root(kit_dir):
    path = Path(kit_dir).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("symlink in kit directory ancestry")
    root = path.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("kit path is not a directory")
    compose = root / COMPOSE
    if compose.is_symlink() or not compose.is_file():
        raise ValueError("missing canonical compose or symlink")
    return root, compose

def validate_compose(compose, environ=None):
    """Restricted source gate, not a substitute for docker compose config or runtime."""
    env = os.environ if environ is None else environ
    source = compose.read_text(encoding="utf-8")
    if len(source) > 1024 * 1024 or any(token in source for token in ("!!python",)):
        raise ValueError("unsafe compose source")
    try:
        doc = yaml.load(source, Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        raise ValueError("invalid compose YAML") from exc
    if not isinstance(doc, dict) or not set(doc) <= {"services", "networks", "volumes", "name"}:
        raise ValueError("unsupported compose root")
    services = doc.get("services")
    if not isinstance(services, dict) or not {"gamma", "core"} <= set(services) or not set(services) <= set(IMAGE_VARIABLES):
        raise ValueError("missing or unexpected services")
    if (not isinstance(doc.get("networks"), dict) or set(doc["networks"]) != {"edge", "backend"}
            or not isinstance(doc["networks"].get("backend"), dict)
            or doc["networks"]["backend"].get("internal") is not True
            or doc["networks"].get("edge") != {}
            or doc["networks"]["backend"] != {"internal": True}):
        raise ValueError("unsafe networks")
    if "demo" not in services:
        raise ValueError("missing demo profile service")
    for name, svc in services.items():
        if not isinstance(svc, dict):
            raise ValueError("invalid service")
        allowed = {"user", "environment", "command", "volumes", "image", "ports", "networks", "depends_on", "healthcheck", "read_only", "cap_drop", "security_opt", "profiles"}
        if not set(svc) <= allowed:
            raise ValueError("unexpected service fields: " + name)
        if svc.get("volumes") != ["./fixture.py:/fixture.py:ro"] or svc.get("command") != ["python", "/fixture.py"] or svc.get("environment") != {"FIXTURE_ROLE": name}:
            raise ValueError("unsafe fixture service: " + name)
        if svc.get("profiles", []) != (["demo"] if name == "demo" else []):
            raise ValueError("unsafe service profiles")
        image = svc.get("image")
        variable = IMAGE_VARIABLES[name]
        expected = ("${DEMO_IMAGE:-${CORE_IMAGE}}" if name == "demo" else "${" + variable + ":?verified digest required}")
        if image != expected:
            raise ValueError("unsafe image declaration: " + name)
        image_value = (env.get("CORE_IMAGE") if name == "demo" and variable not in env
                       else env.get(variable))
        if not isinstance(image_value, str) or not DIGEST.fullmatch(image_value):
            raise ValueError("missing or mutable image digest: " + name)
        if svc.get("read_only") is not True or svc.get("cap_drop") != ["ALL"] or svc.get("user") != "65532:65532":
            raise ValueError("missing isolation: " + name)
        if svc.get("security_opt") != ["no-new-privileges:true"]:
            raise ValueError("missing no-new-privileges: " + name)
        if svc.get("networks") != (["edge", "backend"] if name == "gamma" else ["backend"]):
            raise ValueError("unsafe service networks: " + name)
        if name != "gamma" and svc.get("ports"):
            raise ValueError("unexpected exposed port")
        if name == "gamma" and svc.get("ports") != ["127.0.0.1::8080"]:
            raise ValueError("unsafe gamma port")
        if name == "gamma" and svc.get("depends_on") != {"core": {"condition": "service_healthy"}}:
            raise ValueError("unsafe dependency")
        if not isinstance(svc.get("healthcheck"), dict) or not svc["healthcheck"].get("test"):
            raise ValueError("missing healthcheck")
    return {"validated_services": sorted(services), "source_gate": "restricted_synthetic_only"}

def plan(action, kit_dir, environ=None):
    if action not in ACTIONS:
        raise ValueError("unsupported action")
    root, compose = _safe_root(kit_dir)
    validation = validate_compose(compose, environ)
    base = ["docker", "compose", "--file", str(compose)]
    operations = {
        "preflight": [base + ["config", "--quiet"]],
        "install": [base + ["config", "--quiet"], base + ["up", "--detach", "--wait"]],
        "health": [base + ["ps", "--format", "json"]],
        "upgrade": [base + ["config", "--quiet"], base + ["pull"], base + ["up", "--detach", "--wait"]],
        "rollback": [], "backup": [], "restore": [],
    }
    blocked = action in ("rollback", "backup", "restore")
    return {"schema": 2, "action": action, "mode": "DRY_RUN_ONLY",
            "kit": str(root), "compose": str(compose),
            "validation": validation, "commands_not_executed": operations[action],
            "blocked": blocked,
            "reason": "requires verified snapshot, retention and restore contract" if blocked else None,
            "runtime_attested": False, "host_mutated": False}

def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic kit planner: never runs Docker")
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("--kit-dir", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args(argv)
    try:
        receipt = plan(args.action, args.kit_dir)
    except (ValueError, OSError) as exc:
        parser.exit(2, "PLAN_FAIL: " + str(exc) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 3 if receipt["blocked"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
