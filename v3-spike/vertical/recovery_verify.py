"""Read-only E17 verification adapter for the future confined Temporal action.

Both readers MUST be server-owned: read_context calls dynamic_context with
include_signals=True; read_action_receipt resolves an authenticated persisted
Worker result, never a request body. A hash is an integrity check, not an
authorization. This module neither measures nor acts/publishes; the independent
collector must publish fresh measured samples using existing ingestion.
"""
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime
from statistics import median

from evidence_retrieval import index_references
from rca_preview import preview


def digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def stamp(value):
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("noncanonical timestamp")
    return parsed


def _snapshot(read_context, run_id, refs, scope):
    if not isinstance(run_id, str) or not re.fullmatch(r"RUN-[A-F0-9]{16}", run_id):
        raise ValueError("invalid run")
    core, context = deepcopy(read_context(run_id))
    run = core["run"]
    expected = index_references(refs)
    if (run["run_id"] != run_id or run["mode"] != "DEMO"
        or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}", run["incident_id"])
        or core.get("production_authorized") is not False
        or context.get("run_id") != run_id
        or context.get("classification") != "SYNTHETIC_LAB_CONTEXT"
        or context.get("production_authorized") is not False
        or context.get("policy") != "DENY" or context.get("root") != scope[0]
        or index_references(context["evidence"]) != expected):
        raise ValueError("unverified run or evidence binding")
    rows = context["verified_signals"]
    if index_references(rows) != expected:
        raise ValueError("incomplete signal projection")
    signals = {}
    for row in rows:
        sig = row["signal"]
        ent = sig["enterprise"]
        event_id = sig.get("event_id")
        # The persisted correlation projection contains event_id/source/sha256,
        # not raw tenant/resource/id. The trusted dynamic_context reader checks
        # the enclosing synthetic provenance, run, incident, resource and hash.
        if (set(sig) - {"event_id", "source", "sha256", "enterprise", "observation"}
            or not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", event_id)
            or not isinstance(sig.get("source"), str)
            or not re.fullmatch(r"(metric|log|event):[^:]+", sig["source"])
            or not isinstance(sig.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", sig["sha256"])
            or [ent["asset_id"], ent.get("application_id")] != scope[1:]
            or event_id in signals):
            raise ValueError("invalid normalized signal or duplicate scope")
        signals[event_id] = row
        stamp(ent["occurred_at"])
    return run, signals


def verify_recovery(*, read_context, read_action_receipt, original_run_id,
                    comparison_run_id, scope, original_refs, comparison_refs,
                    action_receipt_id, action_receipt_sha256):
    """Return measured outcome, never an action permission or causal verdict.

    Proposed C/B receipt contract: SYNTHETIC_LAB_ACTION_RECEIPT with status
    SIMULATED, receipt_id, binding (same as HITL reservation), completed_at
    canonical UTC seconds, operational DENY, host/production flags False.
    The existing E17 harness must be adapted by C; legacy client hash does not
    qualify. The comparison event message binds the trusted receipt digest.
    """
    if (original_run_id == comparison_run_id or not isinstance(scope, list)
        or len(scope) != 3 or not all(isinstance(s, str) and
                                      re.fullmatch(r"NODE-CI-[A-Z0-9-]{1,80}", s) for s in scope)):
        raise ValueError("distinct runs and lab scope required")
    # Detach caller-owned inputs before invoking any reader callback.
    scope = list(scope)
    original_refs = list(index_references(original_refs).values())
    comparison_refs = list(index_references(comparison_refs).values())
    before, old = _snapshot(read_context, original_run_id, original_refs, scope)
    after, new = _snapshot(read_context, comparison_run_id, comparison_refs, scope)
    if before["incident_id"] == after["incident_id"]:
        raise ValueError("comparison must be a new incident/run")
    if any(k not in new or new[k]["signal"] != row["signal"] for k, row in old.items()):
        raise ValueError("original observations changed or missing")
    added = [row for k, row in new.items() if k not in old]
    if len(added) != 2 or set(index_references(original_refs)) & set(index_references(comparison_refs)):
        raise ValueError("fresh comparison evidence required")
    if (not isinstance(action_receipt_id, str)
        or not re.fullmatch(r"ACT-[a-f0-9]{32}", action_receipt_id)
        or not isinstance(action_receipt_sha256, str)
        or not re.fullmatch(r"[a-f0-9]{64}", action_receipt_sha256)):
        raise ValueError("invalid receipt reference")
    receipt = deepcopy(read_action_receipt(action_receipt_id))
    binding = receipt["binding"]
    action = binding["lab_action"]
    refs = index_references(original_refs)
    context_hash = digest([before["incident_id"], original_run_id,
                           [refs[k] for k in sorted(refs)]])
    if (digest(receipt) != action_receipt_sha256
        or receipt.get("receipt_id") != action_receipt_id
        or receipt.get("classification") != "SYNTHETIC_LAB_ACTION_RECEIPT"
        or receipt.get("status") != "SIMULATED"
        or receipt.get("executed_on_host") is not False
        or receipt.get("production_authorized") is not False
        or receipt.get("operational_decision") != "DENY"
        or binding.get("run_id") != original_run_id
        or binding.get("workflow_id") != original_run_id
        or binding.get("incident_id") != before["incident_id"]
        or binding.get("context_sha256") != context_hash
        or action.get("action") != "RESET_LAB_HTTP_DELAY"
        or action.get("resource") != scope[0]
        or not re.fullmatch(r"[a-f0-9]{32}", action.get("target_id", ""))
        or not re.fullmatch(r"HITL-[a-f0-9]{32}", binding.get("receipt_id", ""))
        or not re.fullmatch(r"[a-f0-9]{64}", binding.get("receipt_sha256", ""))):
        raise ValueError("unverified action receipt")
    completed = stamp(receipt["completed_at"])
    observations = []
    action_events = []
    for row in new.values():
        signal = row["signal"]
        ent = signal["enterprise"]
        obs = signal.get("observation")
        if obs is not None:
            measurement = ent["measurement"]
            samples = measurement["samples_ms"]
            if (measurement["classification"] != "MEASURED_SYNTHETIC_LAB"
                or measurement["method"] != "HTTP_MONOTONIC_MEDIAN_5"
                or len(samples) != 5 or obs["value"] != round(median(samples), 3)):
                raise ValueError("invalid measured samples")
            if (obs["phase"] == "recovery") != (signal["event_id"] not in old):
                raise ValueError("recovery must be new evidence")
            observations.append(dict(obs, synthetic=True, evidence_id=row["evidence_id"],
                                     measurement_scope=scope, occurred_at=ent["occurred_at"]))
        elif signal["event_id"] not in old:
            action_events.append(signal)
    if len(observations) != 3 or len(action_events) != 1:
        raise ValueError("expected three measured phases and one new action event")
    event = action_events[0]
    times = {row["phase"]: stamp(row["occurred_at"]) for row in observations}
    if (not event["source"].startswith("event:")
        or event["enterprise"].get("message") !=
            "Temporal lab action receipt " + action_receipt_sha256 + "; original run " + original_run_id
        or not times["incident"] < completed <= stamp(event["enterprise"]["occurred_at"]) < times["recovery"]):
        raise ValueError("unbound or out-of-order action and recovery")
    comparison = preview(observations)["recovery"]
    # Re-read both projections and the persisted receipt. Detached snapshots
    # prevent a mutable reader cache from rewriting our comparison baseline.
    # This detects observed changes; it is not an atomic multi-store snapshot.
    final_run, final_old = _snapshot(read_context, original_run_id, original_refs, scope)
    if final_run != before or final_old != old:
        raise ValueError("original run changed during verification")
    final_comparison, final_new = _snapshot(read_context, comparison_run_id, comparison_refs, scope)
    if final_comparison != after or final_new != new:
        raise ValueError("comparison run changed during verification")
    if deepcopy(read_action_receipt(action_receipt_id)) != receipt:
        raise ValueError("action receipt changed during verification")
    return {"classification": "SYNTHETIC_LAB_VERIFY",
            "status": "RECOVERED" if comparison["within_baseline_tolerance"] else "NOT_RECOVERED",
            "original_run_id": original_run_id, "comparison_run_id": comparison_run_id,
            "action_receipt_id": action_receipt_id, "action_receipt_sha256": action_receipt_sha256,
            "original_evidence": original_refs, "comparison_evidence": comparison_refs,
            "recovery_observed_at": times["recovery"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "measurements": comparison, "causality_established": False,
            "operational_decision": "DENY", "production_authorized": False}
