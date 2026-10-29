"""Run-bound, offline ACME remediation receipt. No DB, HTTP, subprocess or effects.

This is a deterministic fixture builder, NOT a Core/Temporal authorization endpoint.
"""
from __future__ import annotations
import hashlib
import json
import re
from typing import Any

from .acme_remediation_projection import project_remediation

SAFE_RUN = re.compile(r"^RUN-[A-Za-z0-9_-]{1,120}$")
SAFE_SCENARIO = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SAFE_EVIDENCE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def build_run_remediation_receipt(
    run: dict[str, Any],
    proposal: dict[str, Any],
    decision: dict[str, Any],
    preconditions: dict[str, bool],
    before: dict[str, Any],
    evidence_ids: list[str],
    *,
    outcome: str = "SUCCESS",
    now=None,
) -> dict[str, Any]:
    """Bind a synthetic what-if to explicit run and evidence identifiers.

    Identifiers are caller-provided references, not verified Core records.
    """
    if not isinstance(run, dict) or set(run) != {"run_id", "scenario_id", "mode", "synthetic"}:
        raise ValueError("run_schema_invalid")
    if not isinstance(run["run_id"], str) or not SAFE_RUN.fullmatch(run["run_id"]):
        raise ValueError("run_id_invalid")
    if not isinstance(run["scenario_id"], str) or not SAFE_SCENARIO.fullmatch(run["scenario_id"]):
        raise ValueError("scenario_id_invalid")
    if run["synthetic"] is not True or run["mode"] not in {"DEMO", "REPLAY", "STORY"}:
        raise ValueError("run_not_synthetic")
    if run["mode"] != proposal.get("mode"):
        raise ValueError("run_proposal_mode_mismatch")
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or len(evidence_ids) > 32
        or any(not isinstance(x, str) or not SAFE_EVIDENCE.fullmatch(x) for x in evidence_ids)
        or len(set(evidence_ids)) != len(evidence_ids)
    ):
        raise ValueError("evidence_refs_invalid")
    projection = project_remediation(proposal, decision, preconditions, before, outcome=outcome, now=now)
    binding = {
        "run_id": run["run_id"],
        "scenario_id": run["scenario_id"],
        "mode": run["mode"],
        "proposal_digest": projection["proposal_digest"],
        "evidence_ids": sorted(evidence_ids),
        "outcome": outcome,
    }
    digest = hashlib.sha256(
        json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    return {
        "schema": "aiops.acme-remediation-receipt.v1",
        "classification": "SYNTHETIC_UNVERIFIED",
        "run_id": run["run_id"],
        "scenario_id": run["scenario_id"],
        "evidence_ids": sorted(evidence_ids),
        "evidence_verified": False,
        "core_run_verified": False,
        "receipt_digest": digest,
        "projection": projection,
        "effect_applied": False,
        "persisted": False,
    }
