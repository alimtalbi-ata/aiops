"""Read-only presentation contract for an offline ACME Policy/HITL what-if.

Consumes a receipt produced by build_run_remediation_receipt. Never calls Core,
GLPI, Temporal, a remediation adapter, or a database. Not a Policy authorization.
"""
from __future__ import annotations

import re
from typing import Any

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_RUN = re.compile(r"^RUN-[A-Za-z0-9_-]{1,120}$")
_SIMULATED = frozenset({"SIMULATED_SUCCESS", "SIMULATED_FAILURE", "SIMULATED_NO_RECOVERY"})


def present_demo_policy_result(receipt: dict[str, Any]) -> dict[str, Any]:
    """Summarize a *synthetic, unverified* receipt without elevating its claims.

    The caller must build the receipt with the existing offline receipt builder.
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
    if not isinstance(receipt.get("scenario_id"), str) or not receipt["scenario_id"]:
        raise ValueError("scenario_identity_invalid")
    ids = receipt.get("evidence_ids")
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("evidence_refs_invalid")
    digest = receipt.get("receipt_digest")
    if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
        raise ValueError("receipt_digest_invalid")
    projection = receipt.get("projection")
    if not isinstance(projection, dict) or not isinstance(projection.get("gate"), dict):
        raise ValueError("projection_missing")
    gate = projection["gate"]
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
    rollback = projection.get("rollback")
    if not isinstance(rollback, dict) or rollback.get("effect_applied") is not False:
        raise ValueError("rollback_effect_claim_forbidden")
    before, after = projection.get("before"), projection.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict) or before.get("target_ci") != projection["target_ci"] or after.get("target_ci") != projection["target_ci"]:
        raise ValueError("snapshot_binding_invalid")
    status = projection.get("status")
    if gate.get("status") == "SIMULATED" and (
        gate.get("dry_run") is not True
        or gate.get("preconditions") != "FIXTURE_ASSERTED_NOT_RUNTIME_VERIFIED"
        or not isinstance(gate.get("approval_actor"), str)
        or not gate["approval_actor"]
    ):
        raise ValueError("gate_fixture_invalid")
    if status in _SIMULATED and gate.get("status") == "SIMULATED":
        decision = "SIMULATE"
    elif status == "BLOCKED" and gate.get("status") == "BLOCKED" and before == after:
        decision = "BLOCKED"
    else:
        raise ValueError("projection_gate_inconsistent")
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
