"""Static product BOM preflight, separate from synthetic fixture. No Docker calls."""
import json
import re
import sys
from pathlib import Path

REQUIRED = {"gamma", "core", "temporal", "worker", "policy", "hitl", "evidence"}
DIGEST = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$")
PROFILES = {"default", "demo", "enterprise"}

def validate(bom):
    if not isinstance(bom, dict) or set(bom) != {"schema", "services"} or bom["schema"] != 1:
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
    if not any(item["migration"] for item in services.values()):
        raise ValueError("no migration ownership")
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
