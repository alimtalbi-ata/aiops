"""AIOPS V3 kit command planner. Synthetic-only; never executes host commands."""
import argparse
import json
from pathlib import Path

ACTIONS = ("preflight", "install", "health", "upgrade", "rollback", "backup", "restore")
COMPOSE = "docker-compose.yml"

def plan(action, kit_dir):
    if action not in ACTIONS:
        raise ValueError("unsupported action")
    root = Path(kit_dir).resolve(strict=True)
    compose = root / COMPOSE
    if not compose.is_file() or compose.is_symlink():
        raise ValueError("missing canonical compose or symlink")
    # A plan is NOT a validated install, health result or successful backup.
    base = ["docker", "compose", "--file", str(compose)]
    operations = {
        "preflight": [base + ["config", "--quiet"]],
        "install": [base + ["config", "--quiet"], base + ["up", "--detach", "--wait"]],
        "health": [base + ["ps", "--format", "json"]],
        "upgrade": [base + ["config", "--quiet"], base + ["pull"], base + ["up", "--detach", "--wait"]],
        "rollback": [],
        "backup": [],
        "restore": [],
    }
    return {"schema": 1, "action": action, "mode": "DRY_RUN_ONLY",
            "kit": str(root), "compose": str(compose),
            "commands_not_executed": operations[action],
            "blocked": action in ("rollback", "backup", "restore"),
            "reason": ("requires verified snapshot, retention and restore contract"
                       if action in ("rollback", "backup", "restore") else None),
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
