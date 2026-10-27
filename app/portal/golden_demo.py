"""Read-only Golden Demo journey contract; no execution or LIVE effects."""
import json
from pathlib import Path

_PATH = Path(__file__).with_name("golden_demo_scenario.json")
def scenario():
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    if data["mode"] != "DEMO" or data["synthetic"] is not True:
        raise ValueError("Golden Demo contract must be synthetic DEMO")
    return data

def journey(runs):
    contract = scenario()
    matches = [r for r in runs if r.get("scenario_id") == contract["scenario_id"]
               and r.get("mode") == "DEMO"]
    recent = matches[0] if matches else None
    return {
        "scenario": contract,
        "execution": {
            "state": "NOT_STARTED" if recent is None else "RUN_RECORDED",
            "run_id": recent.get("run_id") if recent else None,
            "run_status": recent.get("status") if recent else None,
            "evidence_qualified": False,
            "human_approval_executed": False,
            "remediation_executed": False,
            "live_integrations_qualified": False,
        },
    }
