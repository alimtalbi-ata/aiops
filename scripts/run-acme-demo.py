#!/usr/bin/env python3
"""Run the canonical ACME SAN -> Payments scenario through real AIOps services.

This is a DEMO-only operator tool. It requires explicit confirmation, checks
service readiness, uses Core's internal service token from the environment,
waits for the Temporal Run, and emits a sanitized evidence summary.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid


def request_json(base: str, path: str, token: str | None = None,
                 payload: dict | None = None, timeout: float = 8.0) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base.rstrip("/") + path, data=body, headers=headers,
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(2_000_000)
            result = json.loads(raw.decode("utf-8"))
            if not isinstance(result, dict):
                raise RuntimeError("non_object_response")
            return result
    except urllib.error.HTTPError as exc:
        # Never echo request headers, credentials or provider error bodies.
        raise RuntimeError(f"http_{exc.code}:{path}") from None
    except Exception as exc:
        raise RuntimeError(f"{type(exc).__name__}:{path}") from None


def health(base: str, path: str, token: str | None = None) -> dict:
    result = request_json(base, path, token=token, timeout=4)
    return result


def usage_summary(records: list[dict]) -> dict:
    invocations = [r.get("model_invocation") for r in records]
    invocations = [x for x in invocations if isinstance(x, dict)]
    usage_complete = bool(invocations) and all(
        x.get("usage_source") == "provider_reported"
        and type(x.get("total_tokens")) is int
        for x in invocations
    )
    return {
        "invocations": len(invocations),
        "total_tokens": sum(x["total_tokens"] for x in invocations) if usage_complete else None,
        "prompt_tokens": sum(x["prompt_tokens"] for x in invocations) if usage_complete and all(type(x.get("prompt_tokens")) is int for x in invocations) else None,
        "completion_tokens": sum(x["completion_tokens"] for x in invocations) if usage_complete and all(type(x.get("completion_tokens")) is int for x in invocations) else None,
        "latency_ms_total": round(sum(x["latency_ms"] for x in invocations), 2) if invocations and all(type(x.get("latency_ms")) in (int, float) for x in invocations) else None,
        "cost_usd": round(sum(x["cost_usd"] for x in invocations), 8) if invocations and all(type(x.get("cost_usd")) in (int, float) for x in invocations) else None,
        "usage_source": "provider_reported" if usage_complete else "unknown",
        "cost_status": "provider_pricing_required" if any(x.get("cost_usd") is None for x in invocations) else "reported",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a guarded synthetic ACME Payments incident demo.")
    parser.add_argument("--confirm-synthetic-demo", action="store_true",
                        help="required acknowledgement that this creates synthetic DEMO records only")
    parser.add_argument("--allow-test-provider", action="store_true",
                        help="allow deterministic TEST_PROVIDER; output will not be classified as a real-model demo")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()

    if not args.confirm_synthetic_demo:
        print("BLOCKED: pass --confirm-synthetic-demo; no request was sent", file=sys.stderr)
        return 2
    if args.timeout_seconds < 30 or args.timeout_seconds > 1800:
        print("BLOCKED: timeout must be between 30 and 1800 seconds", file=sys.stderr)
        return 2

    token = os.getenv("AIOPS_INTERNAL_TOKEN", "")
    if len(token) < 32:
        print("BLOCKED: AIOPS_INTERNAL_TOKEN is missing or too short", file=sys.stderr)
        return 2

    core = os.getenv("CORE_URL", "http://aiops2-core:810")
    worker = os.getenv("WORKER_URL", "http://aiops2-worker:815")
    intelligence = os.getenv("INTELLIGENCE_URL", "http://aiops2-intelligence:817")
    evidence = os.getenv("EVIDENCE_URL", "http://aiops2-evidence:812")
    policy = os.getenv("POLICY_URL", "http://aiops2-policy:813")
    provider_kind = os.getenv("AIOPS_DEMO_PROVIDER_KIND", "UNCONFIGURED").upper()
    model_name = os.getenv("LLM_MODEL", "UNKNOWN")
    scenario_id = "SCN-GOLDEN-PAYMENT-P1"

    if provider_kind not in ("REAL", "TEST_PROVIDER"):
        print("BLOCKED: set AIOPS_DEMO_PROVIDER_KIND=REAL after configuring an isolated model endpoint; no run created", file=sys.stderr)
        return 2
    if provider_kind == "TEST_PROVIDER" and not args.allow_test_provider:
        print("BLOCKED: TEST_PROVIDER requires --allow-test-provider and is not a customer model demo", file=sys.stderr)
        return 2

    try:
        checks = {
            "core": health(core, "/health"),
            "worker": health(worker, "/health"),
            "intelligence": health(intelligence, "/ready"),
            "evidence": health(evidence, "/health"),
            "policy": health(policy, "/health"),
        }
        if checks["intelligence"].get("provider_configured") is not True:
            raise RuntimeError("intelligence_provider_not_configured")
        if checks["intelligence"].get("internal_auth_configured") is not True:
            raise RuntimeError("intelligence_internal_auth_not_configured")
        if checks["worker"].get("status") != "ok":
            raise RuntimeError("temporal_worker_not_ready")
        scenario = request_json(core, "/api/scenarios/" + scenario_id, token=token)
        if not isinstance(scenario.get("scenario"), dict):
            raise RuntimeError("canonical_scenario_not_registered")

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        external_id = "DEMO-ACME-PAYMENTS-" + stamp + "-" + uuid.uuid4().hex[:8]
        incident = request_json(core, "/api/incidents", token=token, payload={
            "external_id": external_id,
            "title": "P1 — Dégradation SAN affectant le service Payments",
            "severity": "P1",
            "service_id": "ACME-SVC-PAYMENTS",
            "source": "acme-demo-runner",
            "synthetic": True,
            "payload": {
                "scenario_id": scenario_id,
                "business_service": "ACME-SVC-PAYMENTS",
                "impact_hypothesis": "latence et erreurs de paiement",
                "demo_runner": "run-acme-demo-v1",
                "synthetic": True,
            },
        })
        incident_id = incident["incident_id"]
        run = request_json(core, "/api/runs", token=token, payload={
            "mode": "DEMO",
            "scenario_id": scenario_id,
            "incident_id": incident_id,
            "idempotency_key": external_id,
        })
        run_id = run["run_id"]
        execution = request_json(core, f"/api/runs/{run_id}/execute", token=token, payload={})
        deadline = time.monotonic() + args.timeout_seconds
        detail = {}
        while time.monotonic() < deadline:
            detail = request_json(core, f"/api/runs/{run_id}", token=token)
            status = detail.get("run", {}).get("status")
            if status in ("RESOLVED", "BLOCKED", "FAILED", "CANCELLED"):
                break
            time.sleep(args.poll_seconds)
        else:
            raise RuntimeError("temporal_run_timeout")

        ledger = request_json(core, f"/api/runs/{run_id}/ai-ledger", token=token)
        proof = request_json(core, f"/api/runs/{run_id}/demo-verification", token=token)
        analyses = ledger.get("analyses", [])
        critiques = ledger.get("critiques", [])
        events = detail.get("events", [])
        stages = detail.get("stages", [])
        policy_gates = [g for g in detail.get("gates", []) if g.get("stage") == "POLICY"]
        analyst_usage = usage_summary(analyses)
        critic_usage = usage_summary(critiques)
        hitl_skipped = any(e.get("event_type") == "HITL_SIMULATION_SKIPPED" for e in events)
        policy_simulate = any(g.get("state") == "PASS" and g.get("decision") == "SIMULATE" for g in policy_gates)
        no_effects = proof.get("no_effects_observed") is True and proof.get("effect_receipts") == 0
        passed = (
            status == "RESOLVED"
            and len(analyses) >= 1
            and len(critiques) >= 1
            and hitl_skipped
            and policy_simulate
            and no_effects
            and proof.get("live_remediation_authorized") is False
        )
        report = {
            "result": "PASS" if passed else "BLOCKED",
            "qualification_class": "REAL_PROVIDER_DEMO" if provider_kind == "REAL" else "TEST_PROVIDER_CONTRACT_DEMO",
            "provider_kind": provider_kind,
            "model": analyses[0].get("model", model_name) if analyses else model_name,
            "scenario_id": scenario_id,
            "incident_id": incident_id,
            "run_id": run_id,
            "temporal_workflow_id": execution.get("workflow_id"),
            "run_status": status,
            "analyst_records": len(analyses),
            "critic_records": len(critiques),
            "analyst_usage": analyst_usage,
            "critic_usage": critic_usage,
            "policy_simulate_pass": policy_simulate,
            "hitl_simulation_skipped": hitl_skipped,
            "no_effects_observed": no_effects,
            "effect_receipts": proof.get("effect_receipts"),
            "approval_records": proof.get("approval_records"),
            "outbox_events": proof.get("outbox_events"),
            "live_remediation_authorized": False,
            "synthetic": True,
            "service_checks": {k: v.get("status", "UNKNOWN") for k, v in checks.items()},
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if passed else 3
    except Exception as exc:
        print(json.dumps({
            "result": "BLOCKED",
            "reason": str(exc)[:160],
            "synthetic": True,
            "live_remediation_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
