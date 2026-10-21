#!/usr/bin/env python3
"""Read-only DGX Analyst/Critic contract qualification. Run in an ephemeral Intelligence image.

Requires AIOPS_DGX_BASE_URL and AIOPS_DGX_MODEL; never uses live effects,
Core, Policy, database or operator tokens. The inputs are explicitly synthetic.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
spec = importlib.util.spec_from_file_location("dgx_qualification_intelligence", ROOT / "app/intelligence/main.py")
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/reports/dgx-contract-v281.json")
    args = parser.parse_args()
    url = os.environ.get("AIOPS_DGX_BASE_URL", "").rstrip("/")
    model = os.environ.get("AIOPS_DGX_MODEL", "")
    if not (url and model):
        print("FAIL|missing_dgx_endpoint_or_model")
        return 2
    ai.BASE, ai.MODEL = url, model
    ai.KEY = os.environ.get("AIOPS_DGX_API_KEY", "")
    ai.TIMEOUT = float(os.environ.get("AIOPS_DGX_TIMEOUT", "120"))
    ai.TOKEN = "local-contract-qualification-only"
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    evidence = [
        {"evidence_id": "E-SAN-PORT", "source": "synthetic-fixture",
         "observed_at": now, "claim": "One SAN FC port reports link down",
         "payload": {"port": "fc1/3", "link": "down"}},
        {"evidence_id": "E-SAN-PATHS", "source": "synthetic-fixture",
         "observed_at": now, "claim": "Three of four paths remain operational",
         "payload": {"active_paths": 3, "total_paths": 4}},
    ]
    req = ai.Request(incident={"incident_id": "INC-SYNTH-DGX-QUAL-001",
        "title": "Synthetic SAN port failure with remaining multipath redundancy"},
        evidence=evidence, mode="DEMO", context={"synthetic": True, "effects_allowed": False})
    result = {"qualification": "DGX contract only; no workflow or live effects",
              "synthetic": True, "model": model,
              "generated_at_utc": now, "analyst": {}, "critic": {},
              "result": "FAIL", "live_effects": 0}
    start = time.monotonic()
    try:
        analyst = ai.analyze(req, authorization="Bearer " + ai.TOKEN)
        a = analyst["analysis"]
        result["analyst"] = {"status": "PASS", "latency_seconds": round(time.monotonic()-start, 2),
                             "severity": a["severity"], "hypothesis_count": len(a["hypotheses"]),
                             "confidence": a["confidence"]}
        start = time.monotonic()
        critique = ai.critic(ai.CriticRequest(**req.model_dump(), analyst=a),
                             authorization="Bearer " + ai.TOKEN)
        c = critique["critique"]
        result["critic"] = {"status": "PASS", "latency_seconds": round(time.monotonic()-start, 2),
                            "validated": c["validated"], "recommendation": c["final_recommendation"],
                            "issues_count": len(c["issues"])}
        result["result"] = "PASS"
    except Exception as exc:
        # Avoid leaking provider responses, prompts, evidence or keys.
        result["failure_type"] = type(exc).__name__
        result["failure_http_status"] = getattr(exc, "status_code", None)
        result["failure_code"] = "contract_or_provider_failure"
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print("DGX_CONTRACT=" + result["result"])
    print("DGX_REPORT=" + str(dest))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
