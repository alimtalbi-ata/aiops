"""Read-only presentation contract for an offline ACME Policy/HITL what-if.

Consumes a receipt produced by build_run_remediation_receipt. Never calls Core,
GLPI, Temporal, a remediation adapter, or a database. Not a Policy authorization.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_RUN = re.compile(r"^RUN-[A-Za-z0-9_-]{1,120}$")
_SAFE_REF = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_SIMULATED = frozenset({"SIMULATED_SUCCESS", "SIMULATED_FAILURE", "SIMULATED_NO_RECOVERY"})
_SNAPSHOT_KEYS = frozenset({"target_ci", "health", "service_available"})
_ALLOWED_HEALTH = frozenset({"HEALTHY", "DEGRADED", "FAILED", "UNKNOWN"})
_BLOCKED_REASONS = frozenset({
    "DECISION_FIELDS_INVALID", "HUMAN_DECISION_NOT_APPROVED",
    "APPROVAL_BINDING_MISMATCH", "APPROVER_NOT_VERIFIED",
    "APPROVER_ID_INVALID", "SEPARATION_OF_DUTIES_FAILED",
    "APPROVAL_EXPIRED", "APPROVAL_EXPIRY_INVALID",
    "PRECONDITIONS_MISSING", "PRECONDITIONS_FAILED",
})


# Versioned offline builder shapes. Unknown fields could smuggle assertions
# such as human.approved or runtime_verified into a purported demo receipt.
# Reject them instead of silently accepting a mixed contract.
_ALLOWED_RECEIPT_FIELDS = frozenset({
    "schema", "classification", "run_id", "scenario_id", "evidence_ids",
    "evidence_verified", "core_run_verified", "receipt_digest",
    "projection", "effect_applied", "persisted",
})
_ALLOWED_PROJECTION_FIELDS = frozenset({
    "schema_version", "synthetic", "provenance", "proposal_id",
    "proposal_digest", "target_ci", "mode", "recipe_id",
    "idempotency_key", "effect_applied", "postchecks", "before",
    "after", "rollback", "gate", "status", "reason",
})
_ALLOWED_GATE_FIELDS = frozenset({
    "timestamp", "proposal_id", "proposal_digest", "recipe_id",
    "recipe_version", "target_ci", "parameters", "mode", "executor",
    "effect_applied", "postchecks", "rollback", "timeout_seconds",
    "idempotency_key", "status", "reason", "approval_actor",
    "preconditions", "planned_postchecks", "compensation", "dry_run",
})
_ALLOWED_ROLLBACK_FIELDS = frozenset({
    "status", "projected_state", "effect_applied", "executed",
})


def _canonical_utc_fixture_timestamp(value: Any) -> bool:
    """Require the offline gate builder's canonical UTC timestamp, not an audit attestation."""
    if type(value) is not str:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() == timedelta(0)
        and parsed.isoformat() == value
    )


def _same_snapshot_exact(left: Any, right: Any) -> bool:
    """Avoid Python's bool == int equivalence in rollback state comparisons."""
    return (
        isinstance(left, dict) and isinstance(right, dict)
        and left.keys() == right.keys()
        and all(type(left[key]) is type(right[key]) and left[key] == right[key] for key in left)
    )


def _catalog_redacted_parameters_valid(params: Any, spec: dict[str, Any]) -> bool:
    """Accept only the catalog's no-effect, already-redacted gate parameters.

    The receipt omits the original proposal, so this is shape validation,
    not a cryptographic recheck of its proposal digest or authorization.
    """
    if not isinstance(params, dict) or set(params) != set(spec):
        return False
    for key, meta in spec.items():
        value = params[key]
        kind = meta.get("type")
        if kind == "secret_ref":
            # The simulator must never put a vault reference into a receipt.
            if value != "[REDACTED]":
                return False
        elif kind == "identifier":
            if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", value):
                return False
        elif kind == "integer":
            if type(value) is not int or not meta["min"] <= value <= meta["max"]:
                return False
        elif kind == "enum":
            if type(value) is not str or value not in meta["values"]:
                return False
        else:
            return False
    return True

def present_demo_policy_result(receipt: dict[str, Any]) -> dict[str, Any]:
    """Summarize a *synthetic, unverified* receipt without elevating its claims.

    The caller must build the receipt with the existing offline receipt builder.
    The local SHA-256 binding is not a signature or runtime attestation.
    Neither a matching evidence ID nor a fixture's authenticated=True proves
    a Core record, a tenant-scoped read, or a real human approval.
    """
    if not isinstance(receipt, dict) or receipt.get("schema") != "aiops.acme-remediation-receipt.v1":
        raise ValueError("receipt_schema_invalid")
    if receipt.get("classification") != "SYNTHETIC_UNVERIFIED" or any(
        receipt.get(k) is not False
        for k in ("core_run_verified", "evidence_verified", "effect_applied", "persisted")
    ):
        raise ValueError("receipt_attestation_claim_forbidden")
    if not isinstance(receipt.get("run_id"), str) or not _RUN.fullmatch(receipt["run_id"]):
        raise ValueError("run_identity_invalid")
    if not isinstance(receipt.get("scenario_id"), str) or not _SAFE_REF.fullmatch(receipt["scenario_id"]):
        raise ValueError("scenario_identity_invalid")
    ids = receipt.get("evidence_ids")
    if (
        not isinstance(ids, list) or not 1 <= len(ids) <= 32
        or any(not isinstance(x, str) or not _SAFE_REF.fullmatch(x) for x in ids)
        or len(set(ids)) != len(ids) or ids != sorted(ids)
    ):
        raise ValueError("evidence_refs_invalid")
    digest = receipt.get("receipt_digest")
    if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
        raise ValueError("receipt_digest_invalid")
    projection = receipt.get("projection")
    if not isinstance(projection, dict) or not isinstance(projection.get("gate"), dict):
        raise ValueError("projection_missing")
    gate = projection["gate"]
    if not _canonical_utc_fixture_timestamp(gate.get("timestamp")):
        raise ValueError("gate_fixture_timestamp_invalid")
    if type(projection.get("schema_version")) is not int or projection["schema_version"] != 1:
        raise ValueError("projection_schema_invalid")
    if projection.get("synthetic") is not True or projection.get("provenance") != "WHAT_IF_FIXTURE_NOT_OBSERVED":
        raise ValueError("projection_provenance_invalid")
    if projection.get("mode") not in ("DEMO", "REPLAY", "STORY") or gate.get("mode") != projection["mode"]:
        raise ValueError("mode_not_demo")
    if (
        projection.get("proposal_digest") != gate.get("proposal_digest")
        or not isinstance(projection.get("proposal_digest"), str)
        or not _HEX64.fullmatch(projection["proposal_digest"])
    ):
        raise ValueError("proposal_binding_invalid")
    if projection.get("target_ci") != gate.get("target_ci") or not projection.get("target_ci"):
        raise ValueError("target_binding_invalid")
    # The receipt digest binds the proposal digest, but the presentation must
    # also refuse a mixed projection/gate proposal identity. No runtime proof.
    proposal_id = projection.get("proposal_id")
    if (
        not isinstance(proposal_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", proposal_id)
        or gate.get("proposal_id") != proposal_id
    ):
        raise ValueError("proposal_identity_binding_invalid")
    # Reuse the existing remediation_lab catalog instead of inventing a second
    # policy engine. A syntactically valid receipt digest does not authorize
    # a recipe on a different CI family (e.g. GLPI on a Linux target).
    target = projection["target_ci"]
    if not isinstance(target, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", target):
        raise ValueError("target_identity_invalid")
    from .remediation_lab import load_catalog
    recipe_id, recipe_version = projection.get("recipe_id"), gate.get("recipe_version")
    if not isinstance(recipe_id, str) or not isinstance(recipe_version, str):
        raise ValueError("recipe_not_allowlisted")
    recipe = load_catalog().get((recipe_id, recipe_version))
    if recipe is None or recipe.get("implementation") != "SIMULATOR_ONLY":
        raise ValueError("recipe_not_allowlisted")
    if not target.startswith(recipe["target_prefix"]):
        raise ValueError("recipe_target_scope_invalid")
    # The builder stores catalog-typed, redacted parameters on both SIMULATED
    # and BLOCKED gates. Reject nested approval claims and secret references.
    if not _catalog_redacted_parameters_valid(gate.get("parameters"), recipe["parameters"]):
        raise ValueError("gate_parameters_invalid")
    if (
        gate.get("executor") != "NO_EFFECT_SIMULATOR"
        or gate.get("effect_applied") is not False
        or gate.get("postchecks") != "NOT_RUN"
        or gate.get("rollback") != "NOT_REQUIRED"
    ):
        raise ValueError("gate_no_effect_contract_invalid")
    if (
        gate.get("recipe_id") != projection.get("recipe_id")
        or not isinstance(gate.get("idempotency_key"), str)
        or not _HEX64.fullmatch(gate["idempotency_key"])
        or gate["idempotency_key"] != projection.get("idempotency_key")
    ):
        raise ValueError("gate_binding_invalid")
    if projection.get("effect_applied") is not False or projection.get("postchecks") != "NOT_RUN":
        raise ValueError("projection_effect_claim_forbidden")
    before, after = projection.get("before"), projection.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict) or before.get("target_ci") != projection["target_ci"] or after.get("target_ci") != projection["target_ci"]:
        raise ValueError("snapshot_binding_invalid")
    if (
        set(before) != _SNAPSHOT_KEYS or set(after) != _SNAPSHOT_KEYS
        or type(before["health"]) is not str or before["health"] not in _ALLOWED_HEALTH
        or type(after["health"]) is not str or after["health"] not in _ALLOWED_HEALTH
        or type(before["service_available"]) is not bool
        or type(after["service_available"]) is not bool
    ):
        raise ValueError("snapshot_schema_invalid")
    rollback = projection.get("rollback")
    if (
        not isinstance(rollback, dict)
        or rollback.get("effect_applied") is not False
        or type(rollback.get("status")) is not str
        or rollback["status"] not in {"NOT_REQUIRED", "PROJECTED_ONLY", "AVAILABLE_AS_PROJECTION"}
        or rollback.get("executed", False) is not False
        # The existing projection builder always supplies a no-effect
        # projected rollback state; absence must not be called "available".
        or not _same_snapshot_exact(rollback.get("projected_state"), projection.get("before"))
    ):
        raise ValueError("rollback_effect_claim_forbidden")
    status = projection.get("status")
    # Malformed JSON arrays/objects must fail closed with a stable contract
    # error, not raise TypeError during the status-to-rollback lookup.
    if type(status) is not str or status not in (_SIMULATED | {"BLOCKED"}):
        raise ValueError("projection_status_invalid")
    # The existing projection builder has exactly these no-effect hypotheses.
    # Do not allow a forged receipt to turn FAILURE/BLOCKED into a recovery.
    expected_after = (
        {**before, "health": "HEALTHY", "service_available": True}
        if status == "SIMULATED_SUCCESS" else before
    )
    expected_rollback = {
        "SIMULATED_SUCCESS": "AVAILABLE_AS_PROJECTION",
        "SIMULATED_FAILURE": "PROJECTED_ONLY",
        "SIMULATED_NO_RECOVERY": "NOT_REQUIRED",
        "BLOCKED": "NOT_REQUIRED",
    }.get(status)
    if expected_rollback is not None and (
        after != expected_after or rollback["status"] != expected_rollback
    ):
        raise ValueError("projection_outcome_inconsistent")
    if (
        (status == "SIMULATED_SUCCESS" and projection.get("recipe_id") != "ansible-service-restart")
        or (status == "SIMULATED_NO_RECOVERY" and projection.get("recipe_id") == "ansible-service-restart")
    ):
        raise ValueError("projection_recipe_outcome_inconsistent")
    # Recompute the existing receipt builder's deterministic binding. This is
    # local tamper detection, NOT a signature, persisted audit, or Core evidence.
    outcomes = ("SUCCESS", "FAILURE") if status == "BLOCKED" else (
        ("FAILURE",) if status == "SIMULATED_FAILURE" else ("SUCCESS",)
    )
    valid_digests = set()
    for outcome in outcomes:
        binding = {
            "run_id": receipt["run_id"],
            "scenario_id": receipt["scenario_id"],
            "mode": projection["mode"],
            "proposal_digest": projection["proposal_digest"],
            "evidence_ids": ids,
            "outcome": outcome,
        }
        valid_digests.add(hashlib.sha256(
            json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest())
    if digest not in valid_digests:
        raise ValueError("receipt_binding_digest_mismatch")
    # Match remediation_lab.canonical_digest: a matching arbitrary 64-hex key
    # is not a valid no-effect idempotency binding.
    expected_idempotency = hashlib.sha256(json.dumps(
        {"proposal_digest": projection["proposal_digest"], "executor": "NO_EFFECT_SIMULATOR"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()).hexdigest()
    if projection["idempotency_key"] != expected_idempotency:
        raise ValueError("idempotency_digest_mismatch")
    if gate.get("status") == "SIMULATED" and (
        gate.get("dry_run") is not True
        or gate.get("preconditions") != "FIXTURE_ASSERTED_NOT_RUNTIME_VERIFIED"
        or type(gate.get("approval_actor")) is not str
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", gate["approval_actor"])
    ):
        raise ValueError("gate_fixture_invalid")
    if status in _SIMULATED and gate.get("status") == "SIMULATED":
        decision = "SIMULATE"
    elif status == "BLOCKED" and gate.get("status") == "BLOCKED" and before == after:
        decision = "BLOCKED"
    else:
        raise ValueError("projection_gate_inconsistent")
    # Never let untrusted receipt text claim a real approval, runtime check,
    # or recovery reason. Only reason codes emitted by the existing builders.
    expected_reason = {
        "SIMULATED_SUCCESS": "HYPOTHETICAL_RECOVERY_NOT_VERIFIED",
        "SIMULATED_FAILURE": "HYPOTHETICAL_POSTCONDITION_FAILURE",
        "SIMULATED_NO_RECOVERY": "RECIPE_NOT_RECOVERY_CAPABLE",
    }.get(status)
    if decision == "SIMULATE":
        if gate.get("reason") != "NO_SIDE_EFFECTS" or projection.get("reason") != expected_reason:
            raise ValueError("projection_reason_inconsistent")
    elif (
        not isinstance(gate.get("reason"), str)
        or gate["reason"] not in _BLOCKED_REASONS
        or projection.get("reason") != gate["reason"]
    ):
        raise ValueError("projection_reason_inconsistent")
    # Gate metadata is a catalog-bound *plan*, never a completed postcheck.
    # A BLOCKED gate emitted by evaluate_simulation contains no approval actor
    # or dry-run assertion; reject forged mixed-state receipts fail-closed.
    if type(gate.get("timeout_seconds")) is not int or gate["timeout_seconds"] != recipe["timeout_seconds"]:
        raise ValueError("gate_catalog_binding_invalid")
    if decision == "SIMULATE":
        if (
            gate.get("planned_postchecks") != recipe["postchecks"]
            or gate.get("compensation") != recipe["compensation"]
        ):
            raise ValueError("gate_catalog_binding_invalid")
    elif any(
        key in gate for key in (
            "approval_actor", "preconditions", "dry_run",
            "planned_postchecks", "compensation",
        )
    ):
        raise ValueError("gate_blocked_fixture_invalid")
    # Preserve builder compatibility while rejecting any unrecognized claim.
    # These are allowlists (not required-field sets): existing checks above
    # enforce mandatory fields and their semantics.
    for node, allowed, error in (
        (receipt, _ALLOWED_RECEIPT_FIELDS, "receipt_fields_unexpected"),
        (projection, _ALLOWED_PROJECTION_FIELDS, "projection_fields_unexpected"),
        (gate, _ALLOWED_GATE_FIELDS, "gate_fields_unexpected"),
        (rollback, _ALLOWED_ROLLBACK_FIELDS, "rollback_fields_unexpected"),
    ):
        if set(node) - allowed:
            raise ValueError(error)
    return {
        "schema": "aiops.acme-policy-demo-result.v1",
        "classification": "SIMULATED" if decision == "SIMULATE" else "UNKNOWN",
        "source": "OFFLINE_FIXTURE_NOT_CORE",
        "run_id": receipt["run_id"],
        "scenario_id": receipt["scenario_id"],
        "option": {"recipe_id": projection.get("recipe_id"), "target_ci": projection["target_ci"], "scope": "TARGET_ONLY_NOT_SAN_REMEDIATION"},
        "policy": {"decision": decision, "source": "LOCAL_NO_EFFECT_GATE", "core_policy_verified": False, "reason": projection.get("reason", gate.get("reason", "UNKNOWN"))},
        "human": {
            "status": "APPROVAL_FIXTURE_ONLY" if decision == "SIMULATE" else "NO_APPROVAL_ATTESTED",
            "authenticated_runtime": False, "glpi_ticket_verified": False,
            "approval_valid_now": False, "approval_expiry_verified": False,
        },
        "permissions": {
            "rbac_verified": False, "tenant_acl_qualified": False,
            "separation_of_duties_runtime_verified": False, "action_allowed": False,
        },
        "audit": {
            "source": "LOCAL_RECEIPT_FIXTURE_ONLY", "proposal_digest": projection["proposal_digest"],
            "receipt_digest": digest, "persisted": False, "runtime_verified": False,
            "observed_at": None,
        },
        "before_after": {"before": dict(before), "after_hypothesis": dict(after), "observed": False, "provenance": "WHAT_IF_FIXTURE_NOT_OBSERVED"},
        "rollback": {"status": rollback.get("status", "UNKNOWN"), "executed": False, "projected_only": True},
        "risks": ["SAN_TO_PAYMENTS_CAUSALITY_UNVERIFIED", "HUMAN_APPROVAL_NOT_AUTHENTICATED", "NO_RUNTIME_POSTCHECKS", "ROLLBACK_NOT_EXECUTED"],
        "evidence": {"ids": list(ids), "receipt_digest": digest, "core_verified": False, "tenant_acl_qualified": False, "runtime_attested": False},
        "effect_applied": False,
        "persisted": False,
    }
