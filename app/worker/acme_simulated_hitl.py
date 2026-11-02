"""Strict, no-effect ACME Twin-simulated HITL receipt for a disposable sandbox.

Only independently authenticated Core/Twin/Policy readbacks may qualify this
receipt. The caller supplies IDs, never an approval document or human rights.
Temporal history contains nonsecret IDs and a redacted result, not credentials.
"""
from datetime import datetime, timedelta, timezone
import re

TENANT = "ACME-TEST"
SCENARIO = "ACME-SAN-PAYMENTS"
ISSUER = "TWIN_ACME_SIMULATED"
SCHEMA = "aiops.worker-acme-simulated-no-effect.v1"
CAPABILITY_SCHEMA = "aiops.acme-sandbox-capabilities.v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,99}\Z", re.ASCII)
_KEYS = frozenset((
    "attempt_id", "tenant_id", "scenario_id", "mode", "approval_issuer",
    "incident_id", "run_id", "proposal_id", "approval_id", "ticket_id",
    "idempotency_key", "human_approved", "execution_allowed", "effect_allowed",
))


class SandboxDenied(ValueError):
    """Fail closed without echoing untrusted service responses."""


def _id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def validate_intent(intent):
    if (type(intent) is not dict or frozenset(intent) != _KEYS
            or not all(_id(intent.get(k)) for k in (
                "attempt_id", "incident_id", "run_id", "proposal_id",
                "approval_id", "ticket_id"))
            or intent.get("tenant_id") != TENANT
            or intent.get("scenario_id") != SCENARIO
            or intent.get("mode") != "SIMULATION"
            or intent.get("approval_issuer") != ISSUER
            or intent.get("idempotency_key") != intent.get("attempt_id")
            or intent.get("human_approved") is not False
            or intent.get("execution_allowed") is not False
            or intent.get("effect_allowed") is not False
            or not intent["ticket_id"].startswith("SIM-GLPI-")
            or not intent["approval_id"].startswith("SIM-APP-")):
        raise SandboxDenied("sandbox_intent_unqualified")
    return dict(intent)


def capability():
    return {
        "schema": CAPABILITY_SCHEMA, "component": "worker",
        "tenant_id": TENANT, "mode": "SIMULATION", "isolated": True,
        "approval_issuer": ISSUER, "human_approval_claimed": False,
        "live_effects_allowed": False, "real_glpi_writes_allowed": False,
    }


def _utc(value):
    if type(value) is not str:
        raise SandboxDenied("approval_time_unqualified")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise SandboxDenied("approval_time_unqualified") from None
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise SandboxDenied("approval_time_unqualified")
    return dt.astimezone(timezone.utc)


def _bound(document, intent):
    if type(document) is not dict or any(
            document.get(k) != intent[k] for k in (
                "attempt_id", "tenant_id", "incident_id", "run_id")):
        raise SandboxDenied("sandbox_readback_binding_unqualified")


def validate_readbacks(intent, *, core, twin, policy, now=None):
    """Never use caller-provided readbacks as authority in a runtime route.

    The Worker activity obtains each over its own authenticated service GET.
    """
    validate_intent(intent)
    for document in (core, twin, policy):
        _bound(document, intent)
    if (core.get("incident_status") != "RESOLVED"
            or core.get("run_status") != "RESOLVED"
            or core.get("ticket_id") != intent["ticket_id"]
            or core.get("ticket_authority") != "SIMULATED_ONLY"
            or core.get("ticket_status") != "RESOLVED"
            or core.get("source") != "SYNTHETIC_SIMULATOR"
            or core.get("analysis_validated") is not True
            or core.get("critic_validated") is not True
            or type(core.get("evidence_count")) is not int
            or core["evidence_count"] < 2
            or core.get("proposal_id") != intent["proposal_id"]):
        raise SandboxDenied("core_resolution_unqualified")
    if (twin.get("approval_id") != intent["approval_id"]
            or twin.get("proposal_id") != intent["proposal_id"]
            or twin.get("approval_issuer") != ISSUER
            or twin.get("approval_actor") != ISSUER
            or twin.get("approval_kind") != "SIMULATED"
            or twin.get("approval_status") != "SIMULATED"
            or twin.get("mode") != "SIMULATION"
            or twin.get("human_approved") is not False
            or twin.get("execution_allowed") is not False
            or twin.get("effect_allowed") is not False
            or twin.get("live_effects_allowed") is not False
            or twin.get("real_glpi_writes_allowed") is not False
            or twin.get("impact_root") != "ACME-SAN-FABRIC-A"
            or type(twin.get("impacted_cis")) is not list
            or "ACME-SVC-PAYMENTS" not in twin["impacted_cis"]
            or not _id(twin.get("approval_nonce"))):
        raise SandboxDenied("twin_simulated_approval_unqualified")
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise SandboxDenied("approval_clock_unqualified")
    issued, expires = _utc(twin.get("issued_at")), _utc(twin.get("expires_at"))
    now = now.astimezone(timezone.utc)
    if (issued > now + timedelta(seconds=30)
            or expires <= now
            or expires <= issued
            or expires - issued > timedelta(minutes=5)
            or now - issued > timedelta(minutes=5)):
        raise SandboxDenied("twin_approval_expired_or_future")
    if (policy.get("decision") != "SIMULATE"
            or policy.get("approval_kind") != "SIMULATED"
            or policy.get("approval_issuer") != ISSUER
            or policy.get("mode") != "SIMULATION"
            or policy.get("human_approved") is not False
            or policy.get("execution_allowed") is not False
            or policy.get("effect_allowed") is not False
            or policy.get("live_effects_allowed") is not False
            or policy.get("real_glpi_writes_allowed") is not False
            or policy.get("proposal_id") != intent["proposal_id"]
            or policy.get("approval_id") != intent["approval_id"]):
        raise SandboxDenied("policy_simulation_unqualified")
    return True


async def simulate_no_effect(intent, *, get, now=None):
    """Read Core/Twin/Policy twice; never POST, signal, approve or mutate."""
    intent = validate_intent(intent)
    path = "/api/sandbox/acme/e2e/" + intent["attempt_id"]
    try:
        first = {component: await get(component, path)
                 for component in ("core", "twin", "policy")}
        validate_readbacks(intent, **first, now=now)
        second = {component: await get(component, path)
                  for component in ("core", "twin", "policy")}
        validate_readbacks(intent, **second, now=now)
    except SandboxDenied:
        raise
    except Exception:
        raise SandboxDenied("sandbox_independent_readback_unavailable") from None
    if (first["twin"]["approval_nonce"] != second["twin"]["approval_nonce"]
            or first["twin"]["issued_at"] != second["twin"]["issued_at"]
            or first["twin"]["expires_at"] != second["twin"]["expires_at"]):
        raise SandboxDenied("sandbox_approval_replay_or_rotation")
    return {
        "schema": SCHEMA, "attempt_id": intent["attempt_id"],
        "tenant_id": TENANT, "incident_id": intent["incident_id"],
        "run_id": intent["run_id"], "proposal_id": intent["proposal_id"],
        "approval_id": intent["approval_id"],
        "action": "SIMULATE", "receipt_status": "SIMULATED_NO_EFFECT",
        "approval_issuer": ISSUER, "approval_kind": "SIMULATED",
        "human_approved": False, "execution_allowed": False,
        "effect_allowed": False, "live_effects_allowed": False,
        "real_glpi_writes_allowed": False, "effect_receipts": 0,
        "audit_transitions": [
            "TWIN_SIMULATED_APPROVAL_VALIDATED",
            "WORKER_NO_EFFECT",
            "CORE_RESOLVED_INDEPENDENTLY_VERIFIED",
        ],
        "audit_authority": "TEMPORAL_WORKFLOW_HISTORY_ONLY",
        "core_014_015_written": False, "glpi_write": False,
    }
