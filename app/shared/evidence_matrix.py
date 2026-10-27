"""Read-only evidence matrix projection for Analyst/Critic review.

This module does not retrieve evidence, decide truth, or authorize actions. It
projects normalized evidence into a provenance/freshness-aware review matrix.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .evidence_contract import validate_evidence, contradictory_snapshots
from .freshness import assess_evidence_freshness


SCHEMA = "aiops.evidence-matrix-read-model.v1"


def build_evidence_matrix(
    evidence: list[Any],
    hypotheses: list[dict[str, Any]] | None = None,
    *,
    now: datetime | None = None,
    max_age_seconds: int | None = None,
) -> dict[str, Any]:
    """Build a deterministic matrix; statuses are review hints, never approvals.

    Invalid objects are retained as explicit invalid rows. Missing timestamps
    remain UNKNOWN. Contradictions are surfaced without choosing a winning
    source. Supply a fixed 'now' value for reproducible tests and replays.
    """
    if not isinstance(evidence, list):
        evidence = []
        input_errors = ["evidence_collection_not_a_list"]
    else:
        input_errors = []

    if hypotheses is None:
        hypothesis_items: list[Any] = []
    elif not isinstance(hypotheses, list):
        hypothesis_items = []
        input_errors.append("hypotheses_collection_not_a_list")
    else:
        hypothesis_items = hypotheses
        input_errors.extend(
            f"hypothesis_not_an_object:{index}"
            for index, hypothesis in enumerate(hypothesis_items)
            if not isinstance(hypothesis, dict)
        )

    contract_errors = validate_evidence(evidence)
    invalid_positions: set[int] = set()
    duplicate_ids: set[str] = set()
    for error in contract_errors:
        if error.startswith("duplicate_evidence_id:"):
            duplicate_ids.add(error.split(":", 1)[1])
            continue
        _, separator, suffix = error.rpartition(":")
        if separator and suffix.isdigit():
            invalid_positions.add(int(suffix))
    object_positions = [
        (position, item) for position, item in enumerate(evidence)
        if isinstance(item, dict)
    ]
    valid_items = [item for _, item in object_positions]
    freshness = assess_evidence_freshness(
        valid_items, now=now, max_age_seconds=max_age_seconds
    )
    freshness_by_position = {
        position: freshness["items"][index]
        for index, (position, _) in enumerate(object_positions)
    }

    hypothesis_refs: dict[str, list[dict[str, str]]] = {}
    for index, hypothesis in enumerate(hypothesis_items):
        if not isinstance(hypothesis, dict):
            continue
        label = str(hypothesis.get("hypothesis_id") or hypothesis.get("title") or f"H{index + 1}")
        for relation, key in (
            ("SUPPORTS", "supporting_evidence_ids"),
            ("CONTRADICTS", "contradicting_evidence_ids"),
        ):
            refs = hypothesis.get(key, [])
            if not isinstance(refs, list):
                continue
            for evidence_id in refs:
                if isinstance(evidence_id, str) and evidence_id:
                    hypothesis_refs.setdefault(evidence_id, []).append(
                        {"hypothesis": label, "relation": relation}
                    )

    rows = []
    for position, item in enumerate(evidence):
        if not isinstance(item, dict):
            rows.append({
                "position": position,
                "evidence_id": None,
                "source": None,
                "claim": None,
                "observed_at": None,
                "freshness": "UNKNOWN",
                "freshness_reason": "evidence_not_an_object",
                "provenance": "UNVERIFIED",
                "synthetic": None,
                "hypotheses": [],
                "integrity": "INVALID",
            })
            continue
        timing = freshness_by_position[position]
        provenance = item.get("provenance")
        if not isinstance(provenance, dict):
            provenance = {}
        integrity = "UNVERIFIED"
        if position in invalid_positions or item.get("evidence_id") in duplicate_ids:
            integrity = "INVALID"
        elif provenance.get("identity_contract") == "canonical-envelope-v1":
            integrity = "HASH_VERIFIED"
        rows.append({
            "position": position,
            "evidence_id": item.get("evidence_id"),
            "source": item.get("source"),
            "external_id": item.get("external_id"),
            "claim": item.get("claim"),
            "observed_at": timing.get("observed_at"),
            "age_seconds": timing.get("age_seconds"),
            "freshness": timing.get("status", "UNKNOWN"),
            "freshness_reason": timing.get("reason", "freshness_not_assessed"),
            "provenance": (
                "SYNTHETIC" if provenance.get("synthetic") is True else
                "NON_SYNTHETIC_CLAIMED" if provenance.get("synthetic") is False else
                "UNATTESTED"
            ),
            "synthetic": provenance.get("synthetic") if isinstance(provenance.get("synthetic"), bool) else None,
            "payload_hash": item.get("payload_hash"),
            "integrity": integrity,
            "hypotheses": hypothesis_refs.get(item.get("evidence_id"), []),
        })

    tensions = contradictory_snapshots(valid_items)
    if input_errors or contract_errors:
        status = "BLOCKED_FOR_REVIEW"
    elif not rows:
        status = "UNKNOWN"
    elif any(row["freshness"] in ("STALE", "FUTURE") for row in rows) or tensions:
        status = "DEGRADED_REVIEW"
    elif any(row["freshness"] == "UNKNOWN" for row in rows):
        status = "UNKNOWN"
    else:
        status = "READY_FOR_REVIEW"

    return {
        "schema": SCHEMA,
        "status": status,
        "action_authorized": False,
        "decision_authority": "NONE_READ_MODEL_ONLY",
        "input_errors": input_errors,
        "contract_errors": contract_errors,
        "freshness_summary": freshness,
        "evidence_count": len(rows),
        "hypothesis_count": len(hypothesis_items),
        "contradictions": tensions,
        "items": rows,
    }
