"""Static product BOM preflight. No Docker calls or runtime claims."""
import json
import re
import sys
from pathlib import Path

REQUIRED = {"gamma", "core", "temporal", "worker", "policy", "hitl", "evidence"}
DIGEST = re.compile(r"^[a-z0-9][a-z0-9._:/-]*@sha256:[0-9a-f]{64}$")
PROFILES = {"default", "demo", "enterprise"}
# V3 preliminary contract: core is the sole schema migration owner.
# Other services must not claim migration ownership until a versioned
# per-schema migration contract is approved and tested.
MIGRATION_OWNER = "core"

def validate(bom):
    if not isinstance(bom, dict) or set(bom) != {"schema", "services"} or type(bom["schema"]) is not int or bom["schema"] != 1:
        raise ValueError("invalid BOM schema")
    services = bom["services"]
    if not isinstance(services, dict) or not REQUIRED <= set(services):
        raise ValueError("missing product services")
    for name, item in services.items():
        if not isinstance(name, str) or not isinstance(item, dict) or set(item) != {"image", "profile", "secrets", "migration"}:
            raise ValueError("invalid service entry")
        if not isinstance(item["image"], str) or not DIGEST.fullmatch(item["image"]):
            raise ValueError("mutable or missing OCI digest")
        if item["profile"] not in PROFILES or (name in REQUIRED and item["profile"] != "default"):
            raise ValueError("invalid profile")
        secrets = item["secrets"]
        if not isinstance(secrets, list) or any(not isinstance(s, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", s) for s in secrets) or len(set(secrets)) != len(secrets):
            raise ValueError("invalid external secret references")
        if not isinstance(item["migration"], bool):
            raise ValueError("invalid migration flag")
        if item["migration"] != (name == MIGRATION_OWNER):
            raise ValueError("invalid migration owner: core must be sole owner")
    return {"status": "STATIC_PASS", "services": len(services), "runtime_attested": False}

def main(argv=None):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("bom", type=Path)
    args = p.parse_args(argv)
    try:
        print(json.dumps(validate(json.loads(args.bom.read_text(encoding="utf-8"))), sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"status": "STATIC_FAIL", "reason": str(exc)}))
        return 2

if __name__ == "__main__":
    sys.exit(main())
