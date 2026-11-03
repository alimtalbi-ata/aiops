"""Strict, no-effect ACME Twin-simulated HITL receipt for a disposable sandbox.

Only independently authenticated Core/Twin/Policy readbacks may qualify this
receipt. The caller supplies IDs, never an approval document or human rights.
Temporal history contains nonsecret IDs and a redacted result, not credentials.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
from urllib.parse import urlsplit

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


# The shared internal bearer must never be sent to a caller-configured or
# foreign origin. These are exact service DNS names and fixed service ports,
# not suffix checks or arbitrary private-network destinations.
_SERVICE_ORIGINS = {
    "core": (frozenset(("aiops2-core", "aiops2-rebuild-core",
                         "localhost", "127.0.0.1")), 810),
    "twin": (frozenset(("aiops2-twin", "aiops2-rebuild-twin",
                         "localhost", "127.0.0.1")), 811),
    "policy": (frozenset(("aiops2-policy", "aiops2-rebuild-policy",
                           "localhost", "127.0.0.1")), 813),
}


def validated_service_origin(component, configured):
    """Fence bearer egress before an authenticated sandbox GET."""
    if component not in _SERVICE_ORIGINS or type(configured) is not str:
        raise SandboxDenied("sandbox_service_origin_unqualified")
    allowed, port = _SERVICE_ORIGINS[component]
    try:
        parsed = urlsplit(configured)
        valid = (
            parsed.scheme in ("http", "https")
            and parsed.hostname in allowed and parsed.port == port
            and parsed.username is None and parsed.password is None
            and not parsed.path and not parsed.query and not parsed.fragment
            # urlsplit silently discards embedded TAB/CR/LF and empty ?/#;
            # require the exact canonical origin before sending the bearer.
            and configured == f"{parsed.scheme}://{parsed.hostname}:{port}"
        )
    except ValueError:
        valid = False
    if not valid:
        raise SandboxDenied("sandbox_service_origin_unqualified")
    return configured


class SandboxDenied(ValueError):
    """Fail closed without echoing untrusted service responses."""


def decode_authority_json(body):
    """Parse authenticated readbacks without ambiguous duplicate JSON claims.

    requests.Response.json() silently keeps the last occurrence of a duplicate
    object key, including escaped aliases. That must never establish sandbox
    Core/Twin/Policy authority. No response bytes or credentials are logged.
    """
    if type(body) is not bytes or len(body) > 32768:
        raise SandboxDenied("sandbox_readback_json_unqualified")

    def unique_object(pairs):
        document = {}
        for key, value in pairs:
            if key in document:
                raise SandboxDenied("sandbox_readback_json_unqualified")
            document[key] = value
        return document

    def reject_nonfinite(_value):
        raise SandboxDenied("sandbox_readback_json_unqualified")

    try:
        document = json.loads(
            body.decode("utf-8"), object_pairs_hook=unique_object,
            parse_constant=reject_nonfinite)
    except SandboxDenied:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise SandboxDenied("sandbox_readback_json_unqualified") from None
    if type(document) is not dict:
        raise SandboxDenied("sandbox_readback_json_unqualified")
    return document


def _id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def canonical_source_ids(attempt_id):
    """Recompute Core 015 seven ordered SOURCE IDs, never trust signed claims alone."""
    if not _id(attempt_id) or not attempt_id.startswith("ACME-SIM-"):
        raise SandboxDenied("sandbox_attempt_unqualified")
    return [
        "SYN-EVT-" + hashlib.sha256(
            (TENANT + ":" + attempt_id + ":" + str(index)).encode("ascii")
        ).hexdigest()[:20].upper()
        for index in range(1, 8)
    ]


def validate_intent(intent):
    if (type(intent) is not dict or frozenset(intent) != _KEYS
            or not all(_id(intent.get(k)) for k in (
                "attempt_id", "incident_id", "run_id", "proposal_id",
                "approval_id", "ticket_id"))
            or not intent["attempt_id"].startswith("ACME-SIM-")
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
    # PREPARED is a causal fence: this activity must run BEFORE Core resolution.
    if (core.get("scenario_id") != SCENARIO
            or core.get("mode") != "SIMULATION"
            or core.get("approval_issuer") != ISSUER
            or core.get("glpi_mode") != "SIMULATED_ONLY"
            or core.get("human_approval_claimed") is not False
            or core.get("incident_status") != "PREPARED"
            or core.get("run_status") != "PREPARED"
            or core.get("ticket_id") != intent["ticket_id"]
            or core.get("ticket_authority") != "SIMULATED_ONLY"
            or core.get("ticket_status") != "PREPARED"
            or core.get("source") != "SYNTHETIC_SIMULATOR"
            or type(core.get("source_event_count")) is not int
            or core["source_event_count"] != 7
            or core.get("source_hashes_qualified") is not True
            or core.get("human_approved") is not False
            or core.get("execution_allowed") is not False
            or core.get("effect_allowed") is not False
            or core.get("live_effects_allowed") is not False
            or core.get("real_glpi_writes_allowed") is not False
            or core.get("analysis_validated") is not True
            or core.get("critic_validated") is not True
            or type(core.get("evidence_count")) is not int
            or core["evidence_count"] < 2
            or core.get("proposal_id") != intent["proposal_id"]):
        raise SandboxDenied("core_resolution_unqualified")
    # Bind the Twin-issued approval to the exact Core PREPARED snapshot.
    # Identity and nonce alone cannot detect a stale/replayed SOURCE set.
    source_ids = core.get("source_event_ids")
    request_hash = core.get("request_sha256")
    if (type(request_hash) is not str
            or re.fullmatch(r"[0-9a-f]{64}", request_hash) is None
            or type(source_ids) is not list or len(source_ids) != 7
            or any(type(v) is not str or not v.startswith("SYN-EVT-")
                   or not _id(v) for v in source_ids)
            or len(set(source_ids)) != 7
            or source_ids != canonical_source_ids(intent["attempt_id"])
            or twin.get("core_request_sha256") != request_hash
            or twin.get("core_source_event_ids") != source_ids
            or twin.get("approval_phase") != "PRE_RESOLUTION"
            or twin.get("core_status_at_issuance") != "PREPARED"):
        raise SandboxDenied("twin_core_prepared_snapshot_unqualified")
    if (twin.get("scenario_id") != SCENARIO
            or twin.get("resolution_verified") is not False
            or twin.get("post_resolution_readback_required") is not True
            or twin.get("approval_id") != intent["approval_id"]
            or twin.get("proposal_id") != intent["proposal_id"]
            or twin.get("ticket_id") != intent["ticket_id"]
            or twin.get("issuer_id") != "twin-acme-test"
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
    if (policy.get("state") != "PASS"
            or policy.get("human_approval_claimed") is not False
            or policy.get("decision") != "SIMULATE"
            or policy.get("approval_kind") != "SIMULATED"
            or policy.get("approval_issuer") != ISSUER
            or policy.get("mode") != "SIMULATION"
            or policy.get("human_approved") is not False
            or policy.get("execution_allowed") is not False
            or policy.get("effect_allowed") is not False
            or policy.get("live_effects_allowed") is not False
            or policy.get("real_glpi_writes_allowed") is not False
            or policy.get("proposal_id") != intent["proposal_id"]
            or policy.get("ticket_id") != intent["ticket_id"]
            or policy.get("approval_id") != intent["approval_id"]):
        raise SandboxDenied("policy_simulation_unqualified")
    return True


async def simulate_no_effect(intent, *, get, now=None):
    """Two independent PREPARED reads, then no-effect receipt, never resolution.

    Core alone may transition to RESOLVED *after* the Temporal receipt is
    independently read. A pre-resolved Core record must fail closed.
    """
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
    if (first["core"].get("request_sha256") != second["core"].get("request_sha256")
            or first["core"].get("source_event_ids") != second["core"].get("source_event_ids")
            or first["twin"]["approval_nonce"] != second["twin"]["approval_nonce"]
            or first["twin"]["issued_at"] != second["twin"]["issued_at"]
            or first["twin"]["expires_at"] != second["twin"]["expires_at"]):
        raise SandboxDenied("sandbox_approval_replay_or_rotation")
    # Require the entire independently authenticated snapshot to remain
    # byte-equivalent across both reads. Field-by-field comparisons miss
    # changes to otherwise valid evidence, impact or Policy metadata; Python
    # dict equality also conflates JSON booleans with numbers (True == 1).
    try:
        snapshot_stable = all(
            json.dumps(first[component], sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False)
            == json.dumps(second[component], sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)
            for component in ("core", "twin", "policy")
        )
    except (TypeError, ValueError, UnicodeError):
        raise SandboxDenied("sandbox_readback_snapshot_unqualified") from None
    if not snapshot_stable:
        raise SandboxDenied("sandbox_readback_snapshot_rotated")
    receipt = {
        "schema": SCHEMA, "attempt_id": intent["attempt_id"],
        "tenant_id": TENANT, "incident_id": intent["incident_id"],
        "run_id": intent["run_id"], "proposal_id": intent["proposal_id"],
        "approval_id": intent["approval_id"], "ticket_id": intent["ticket_id"],
        "action": "SIMULATE", "receipt_status": "SIMULATED_NO_EFFECT",
        "approval_issuer": ISSUER, "approval_kind": "SIMULATED",
        "human_approved": False, "execution_allowed": False,
        "effect_allowed": False, "live_effects_allowed": False,
        "real_glpi_writes_allowed": False, "effect_receipts": 0,
        "audit_transitions": [
            "CORE_PREPARED_INDEPENDENTLY_VERIFIED",
            "TWIN_SIMULATED_APPROVAL_VALIDATED",
            "POLICY_SIMULATE_INDEPENDENTLY_VERIFIED",
            "WORKER_NO_EFFECT",
        ],
        "audit_authority": "TEMPORAL_WORKFLOW_HISTORY_ONLY",
        "receipt_phase": "PRE_RESOLUTION",
        "core_status_at_validation": "PREPARED",
        "resolution_verified": False,
        "post_resolution_readback_required": True,
        "core_014_015_written": False, "glpi_write": False,
        # Core terminal must independently compare these to its persisted Run.
        "core_request_sha256": second["core"]["request_sha256"],
        "core_source_event_ids": list(second["core"]["source_event_ids"]),
        "twin_approval_nonce_sha256": hashlib.sha256(
            second["twin"]["approval_nonce"].encode("ascii")
        ).hexdigest(),
    }
    # Stable canonical digest is persisted with the Temporal result. It is NOT
    # a signature, Core authority, or proof of a successful Core RESOLVED write.
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True).encode("ascii")
    ).hexdigest()
    return receipt

_RECEIPT_AUDIT = [
    "CORE_PREPARED_INDEPENDENTLY_VERIFIED",
    "TWIN_SIMULATED_APPROVAL_VALIDATED",
    "POLICY_SIMULATE_INDEPENDENTLY_VERIFIED",
    "WORKER_NO_EFFECT",
]
_RECEIPT_KEYS = frozenset((
    "schema", "attempt_id", "tenant_id", "incident_id", "run_id",
    "proposal_id", "approval_id", "ticket_id", "action", "receipt_status",
    "approval_issuer", "approval_kind", "human_approved",
    "execution_allowed", "effect_allowed", "live_effects_allowed",
    "real_glpi_writes_allowed", "effect_receipts", "audit_transitions",
    "audit_authority", "receipt_phase", "core_status_at_validation",
    "resolution_verified", "post_resolution_readback_required",
    "core_014_015_written", "glpi_write", "core_request_sha256",
    "core_source_event_ids", "twin_approval_nonce_sha256", "receipt_sha256",
))


def receipt_digest_valid(receipt):
    """Fail-closed receipt shape + digest; neither is Core authority.

    A SHA256 checksum is not an authentication signature. Even a correctly
    rehashed object must never turn a no-effect Temporal result into a human
    approval, LIVE permission, or post-resolution claim.
    """
    if type(receipt) is not dict or frozenset(receipt) != _RECEIPT_KEYS:
        return False
    if (receipt.get("schema") != SCHEMA
            or receipt.get("tenant_id") != TENANT
            or receipt.get("action") != "SIMULATE"
            or receipt.get("receipt_status") != "SIMULATED_NO_EFFECT"
            or receipt.get("approval_issuer") != ISSUER
            or receipt.get("approval_kind") != "SIMULATED"
            or receipt.get("receipt_phase") != "PRE_RESOLUTION"
            or receipt.get("core_status_at_validation") != "PREPARED"
            or receipt.get("audit_authority") != "TEMPORAL_WORKFLOW_HISTORY_ONLY"
            or receipt.get("audit_transitions") != _RECEIPT_AUDIT
            or type(receipt.get("effect_receipts")) is not int
            or receipt["effect_receipts"] != 0
            or any(receipt.get(k) is not False for k in (
                "human_approved", "execution_allowed", "effect_allowed",
                "live_effects_allowed", "real_glpi_writes_allowed",
                "resolution_verified", "core_014_015_written", "glpi_write"))
            or receipt.get("post_resolution_readback_required") is not True
            or not all(_id(receipt.get(k)) for k in (
                "incident_id", "run_id", "proposal_id", "approval_id",
                "ticket_id"))
            or not receipt["approval_id"].startswith("SIM-APP-")
            or not receipt["ticket_id"].startswith("SIM-GLPI-")):
        return False
    expected = receipt.get("receipt_sha256")
    if type(expected) is not str or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        return False
    if not _id(receipt.get("attempt_id")) or not receipt["attempt_id"].startswith("ACME-SIM-"):
        return False
    if (type(receipt.get("core_request_sha256")) is not str
            or re.fullmatch(r"[0-9a-f]{64}", receipt["core_request_sha256"]) is None
            or receipt.get("core_source_event_ids") !=
                canonical_source_ids(receipt.get("attempt_id"))
            or type(receipt.get("twin_approval_nonce_sha256")) is not str
            or re.fullmatch(r"[0-9a-f]{64}",
                            receipt["twin_approval_nonce_sha256"]) is None):
        return False
    body = {key: value for key, value in receipt.items()
            if key != "receipt_sha256"}
    try:
        actual = hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")).hexdigest()
    except (TypeError, ValueError, UnicodeError):
        return False
    return hmac.compare_digest(actual, expected)
