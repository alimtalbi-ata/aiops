#!/usr/bin/env python3
"""Read-only backup inventory and operator manifest. No secrets or backups are created."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REQUIRED = {
    "aiops2-postgres": ("postgresql", "aiops2-postgres-data"),
    "aiops2-temporal-postgres": ("postgresql", "aiops2-temporal-postgres-data"),
    "aiops2-glpi-db": ("mariadb", "aiops2-glpi-db-data"),
}
OTHER_VOLUMES = ("aiops2-glpi-data", "aiops2-n8n-data", "aiops2-grafana-data", "aiops2-prometheus-data")

def assess(config):
    services = config.get("services", {})
    volumes = config.get("volumes", {})
    missing = [name for name in REQUIRED if name not in services]
    for service, (_, volume) in REQUIRED.items():
        if service in services and not any(
            isinstance(v, dict) and v.get("source") == volume or
            isinstance(v, str) and v.split(":")[0] == volume
            for v in services[service].get("volumes", [])
        ):
            missing.append("volume_mapping:" + service + ":" + volume)
    missing.extend("volume:" + v for v in [x[1] for x in REQUIRED.values()] + list(OTHER_VOLUMES) if v not in volumes)
    return {
        "schema": "aiops-debian-backup-plan-v1",
        "qualification": "READ_ONLY_INVENTORY_NOT_BACKUP",
        "status": "BLOCKED" if missing else "READY_FOR_OPERATOR_REVIEW",
        "database_services": [{"service": s, "engine": engine, "volume": volume}
                              for s, (engine, volume) in REQUIRED.items()],
        "other_persistent_volumes": list(OTHER_VOLUMES),
        "missing": sorted(missing),
        "required_procedures": [
            "quiesce writers or use consistent online database-native snapshot with WAL/binlog position",
            "logical and physical database backups including roles and grants",
            "Temporal database and workflow compatibility assessment",
            "GLPI application files and database at a consistent checkpoint",
            "n8n encrypted data plus encryption key stored in a separate restricted secret vault",
            "record pinned source SHA and image digests; checksum every backup artifact",
            "restore test to isolated host and validate functional invariants before approval",
        ],
        "security": "Do not include .env, credentials, secret values, or production DB contents in Git",
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config-file", help="Read a local normalized Compose JSON fixture")
    p.add_argument("--output", help="Write inventory JSON (not a backup) to new file")
    args = p.parse_args()
    if args.config_file:
        config = json.loads(Path(args.config_file).read_text(encoding="utf-8"))
    else:
        run = subprocess.run(["docker", "compose", "--env-file", ".env", "config", "--format", "json"],
                             capture_output=True, text=True, check=False)
        if run.returncode:
            print(json.dumps({"status": "BLOCKED", "reason": "compose_config_failed"}))
            return 2
        config = json.loads(run.stdout)
    result = assess(config)
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        out = Path(args.output)
        if out.exists() or out.is_symlink():
            print("FAIL|inventory_output_must_not_exist", file=sys.stderr)
            return 2
        fd = os.open(out, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        print("INVENTORY_WRITTEN=" + str(out))
        print("INVENTORY_SHA256=" + hashlib.sha256(data.encode()).hexdigest())
    else:
        print(data, end="")
    return 0 if result["status"] == "READY_FOR_OPERATOR_REVIEW" else 2

if __name__ == "__main__":
    sys.exit(main())
