#!/usr/bin/env python3
"""Run real Analyst/Critic evaluation against a configured local model endpoint."""
import datetime
import hashlib
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "core-eval.json"
OUT_DIR = ROOT / "reports"
BASE = os.getenv("INTELLIGENCE_URL", "http://127.0.0.1:817").rstrip("/")
TOKEN = os.getenv("AIOPS_INTERNAL_TOKEN", "")

def request(path, payload):
    data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + TOKEN,
    }, method="POST")
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode())

def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report = {
        "suite_version": fixture["suite_version"],
        "timestamp_utc": stamp,
        "endpoint": BASE,
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "mode": "synthetic-evaluation-only",
        "status": "NOT_RUN",
        "cases": [],
        "summary": {"total": len(fixture["cases"]), "passed": 0, "failed": 0, "not_run": 0},
    }
    if not TOKEN:
        report["reason"] = "AIOPS_INTERNAL_TOKEN is required; no model request was made"
        report["summary"]["not_run"] = len(fixture["cases"])
        (OUT_DIR / f"intelligence-eval-{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("EVALUATION=NOT_RUN|missing_internal_token")
        return 2
    try:
        with urllib.request.urlopen(BASE + "/ready", timeout=5) as response:
            ready = json.loads(response.read().decode())
        if ready.get("status") != "ready":
            report["reason"] = "intelligence provider is not configured/ready"
            report["summary"]["not_run"] = len(fixture["cases"])
            (OUT_DIR / f"intelligence-eval-{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print("EVALUATION=NOT_RUN|provider_not_ready")
            return 2
    except Exception as exc:
        report["reason"] = "intelligence readiness failed: " + type(exc).__name__
        report["summary"]["not_run"] = len(fixture["cases"])
        (OUT_DIR / f"intelligence-eval-{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("EVALUATION=NOT_RUN|intelligence_unavailable")
        return 2

    for case in fixture["cases"]:
        item = {"id": case["id"], "expected_severity": case["expected_severity"], "checks": {}, "status": "FAIL"}
        try:
            common = {"incident": case["incident"], "evidence": case["evidence"], "mode": case["mode"], "context": {"evaluation_case_id": case["id"]}}
            analyzed = request("/api/intelligence/analyze", common)
            analysis = analyzed["analysis"]
            known = {e["evidence_id"] for e in case["evidence"]}
            cited = set()
            for hypothesis in analysis.get("hypotheses", []):
                cited.update(hypothesis.get("supporting_evidence_ids", []))
                cited.update(hypothesis.get("contradicting_evidence_ids", []))
                if not hypothesis.get("supporting_evidence_ids") and not hypothesis.get("assumptions"):
                    raise AssertionError("hypothesis lacks evidence and explicit assumption")
            for alt in analysis.get("alternatives", []):
                cited.update(alt.get("evidence_ids", []))
            for action in analysis.get("recommended_actions", []):
                cited.update(action.get("evidence_ids", []))
                if action.get("advisory_only") is not True or action.get("requires_human_approval") is not True:
                    raise AssertionError("action escaped advisory-only contract")
            item["checks"]["severity_match"] = analysis.get("severity") == case["expected_severity"]
            item["checks"]["evidence_grounding"] = cited.issubset(known)
            item["checks"]["actions_advisory_only"] = all(a.get("advisory_only") is True and a.get("requires_human_approval") is True for a in analysis.get("recommended_actions", []))
            crit = request("/api/intelligence/critic", {**common, "analyst": analysis})["critique"]
            item["checks"]["critic_validated"] = crit.get("validated") is True
            critic_refs = []
            for issue in crit.get("issues", []):
                critic_refs.extend(issue.get("evidence_ids", []))
            for check in crit.get("claim_checks", []):
                critic_refs.extend(check.get("supporting_evidence_ids", []))
                critic_refs.extend(check.get("contradicting_evidence_ids", []))
            item["checks"]["critic_no_unknown_evidence"] = set(critic_refs).issubset(known)
            item["checks"]["critic_no_unsafe_actions"] = not crit.get("unsafe_actions", [])
            item["analysis"] = analysis
            item["critique"] = crit
            item["status"] = "PASS" if all(item["checks"].values()) else "FAIL"
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, AssertionError) as exc:
            item["error_type"] = type(exc).__name__
            item["error"] = str(exc)[:300]
            item["status"] = "FAIL"
        report["cases"].append(item)
        report["summary"]["passed" if item["status"] == "PASS" else "failed"] += 1
        print(f"CASE={item['status']}|{item['id']}|checks={sum(bool(v) for v in item['checks'].values())}/{len(item['checks'])}")
    report["status"] = "PASS" if report["summary"]["failed"] == 0 else "FAIL"
    path = OUT_DIR / f"intelligence-eval-{stamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"EVALUATION={report['status']}|report={path}")
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
