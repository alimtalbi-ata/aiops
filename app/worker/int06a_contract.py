"""Offline qualification predicates; never a runtime authority or an orchestrator."""
from datetime import datetime, timezone
import hashlib
import json
import re
from worker.acme_simulated_hitl import validate_intent, verify_no_effect_receipt

IDENTITY = ("tenant_id", "incident_id", "run_id", "attempt_id", "proposal_id", "ticket_id", "approval_id")
STAGES = ("NORMALIZE", "CORRELATE", "CMDB", "OBSERVE", "RAG", "DGX_ANALYST", "DGX_CRITIC", "POLICY", "HITL", "REMEDIATE", "VERIFY", "RECONCILE", "LEARN")

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()

def utc(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value), "utc_required")
    return datetime.fromisoformat(value[:-1] + "+00:00")

def sandbox_mode(core_mode, intent):
    validate_intent(intent)
    require(core_mode == "DEMO" and intent["mode"] == "SIMULATION", "mode_not_qualified")
    return "SIMULATION"  # contract mapping only, grants no permission

def validate_postcheck(*, intent, independently_read):
    validate_intent(intent)
    identity = {k: intent[k] for k in IDENTITY}
    require(type(independently_read) is dict and independently_read.get("identity") == identity, "missing_independent_read")
    require(independently_read.get("critic_decision") == "ALLOW" and independently_read.get("twin_state") == "QUALIFIED" and independently_read.get("policy_decision") == "SIMULATE" and independently_read.get("hitl_valid") is True, "gate_unqualified")
    require(type(independently_read.get("external_effect_count")) is int and independently_read["external_effect_count"] == 0 and independently_read.get("postcheck_verified") is True, "postcheck_unqualified")
    return {"qualification": "CONTRACT_ONLY", "runtime_attested": False, "finish_authorized": False}

def validate_manifest(manifest, *, expected_sha, intent, independently_read):
    """Compare to separately supplied observations, never trust manifest claims.
    Caller must establish authority outside this pure function. No runtime PASS.
    """
    validate_intent(intent)
    require(type(expected_sha) is str and re.fullmatch("[0-9a-f]{40}", expected_sha), "sha_required")
    require(type(manifest) is dict and type(independently_read) is dict, "missing_independent_read")
    require(manifest.get("scope") == "RUNTIME_SANDBOX" and manifest.get("executed_sha") == expected_sha, "scope_or_sha")
    require(manifest.get("runtime_attested") is False, "self_attestation")
    identity = {k: intent[k] for k in IDENTITY}
    require(manifest.get("identity") == identity and independently_read.get("identity") == identity, "identity_mismatch")
    require(independently_read.get("executed_sha") == expected_sha and independently_read.get("scope") == "RUNTIME_SANDBOX", "independent_scope")
    require(manifest.get("images") == independently_read.get("images"), "image_mismatch")
    images = manifest.get("images")
    require(type(images) is dict and set(images) == {"core","twin","policy","worker","evidence","postgres","temporal","temporal_postgres"} and all(type(x) is str and re.fullmatch("sha256:[0-9a-f]{64}", x) for x in images.values()), "image_digest_required")
    receipt = manifest.get("worker_receipt")
    require(verify_no_effect_receipt(receipt, identity), "worker_receipt_invalid")
    require(independently_read.get("worker_receipt_sha256") == receipt["receipt_sha256"], "history_receipt_mismatch")
    require(manifest.get("history_sha256") == independently_read.get("history_sha256") and type(manifest.get("history_sha256")) is str and re.fullmatch("[0-9a-f]{64}", manifest["history_sha256"]), "history_missing")
    rows = manifest.get("transitions")
    require(type(rows) is list and len(rows) == len(STAGES), "stage_set")
    require(independently_read.get("transitions_sha256") == digest(rows), "transition_provenance")
    v = seq = -1
    previous = datetime.min.replace(tzinfo=timezone.utc)
    for stage, row in zip(STAGES, rows):
        require(type(row) is dict and row.get("identity") == identity and row.get("stage") == stage and row.get("status") == "PASS", "transition_binding")
        require(type(row.get("version")) is int and row["version"] > v and type(row.get("sequence")) is int and row["sequence"] > seq, "transition_order")
        ts = utc(row.get("observed_at"))
        require(ts >= previous and row.get("source") == "CORE", "transition_time_or_source")
        v, seq, previous = row["version"], row["sequence"], ts
    require(independently_read.get("critic_decision") == "ALLOW" and independently_read.get("twin_state") == "QUALIFIED" and independently_read.get("policy_decision") == "SIMULATE" and independently_read.get("hitl_valid") is True, "gate_unqualified")
    require(type(independently_read.get("external_effect_count")) is int and independently_read["external_effect_count"] == 0 and independently_read.get("postcheck_verified") is True, "postcheck_unqualified")
    terminal = independently_read.get("terminal")
    require(type(terminal) is dict and terminal == manifest.get("terminal") and terminal.get("identity") == identity and terminal.get("source") == "CORE" and terminal.get("status") == "RESOLVED" and type(terminal.get("version")) is int and terminal["version"] > v and type(terminal.get("sequence")) is int and terminal["sequence"] > seq and utc(terminal.get("observed_at")) >= previous, "terminal_unqualified")
    require(independently_read.get("terminal_readback_sha256") == digest(terminal), "terminal_readback_missing")
    return {"qualification": "CONTRACT_ONLY", "runtime_attested": False, "resolution_authorized": False}

def refuse_unattested_context(context):
    """Actual no-effect activity boundary. No positive authorization exists in INT-06A."""
    if type(context) is not dict:
        raise ValueError("context_missing")
    if (context.get("schema") != "aiops.acme.runtime-context.v1"
            or context.get("scope") != "RUNTIME_SANDBOX"
            or context.get("binding_status") != "UNBOUND"
            or context.get("runtime_freshness") != "UNKNOWN"
            or context.get("runtime_attested") is not False
            or context.get("live_remediation_authorized") is not False
            or context.get("qualification") not in ("BLOCK", "REJECT")):
        raise ValueError("context_unqualified")
    raise ValueError("context_" + context["qualification"].lower())
