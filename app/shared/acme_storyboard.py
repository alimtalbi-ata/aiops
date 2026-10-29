"""Offline ACME presentation storyboard: explanatory only, no runtime evidence.

Pure stdlib. Never contacts Core, Portal, Docker or external services.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any

_STEPS = (
    ("san", "Incident SAN", "Anomalie FC CRC sur ACME-SAN-FABRIC-A"),
    ("payments", "Impact Payments", "Latence applicative potentiellement accrue"),
    ("analysis", "Diagnostic IA", "Hypothèse Analyst et vérification Critic"),
    ("policy", "Policy et approbation", "Décision SIMULATE, sans action LIVE"),
    ("evidence", "Evidence", "Références de preuves et provenance"),
    ("remediation", "Remédiation simulée", "Projection avant/après et rollback hypothétique"),
)


def build_acme_storyboard(
    *,
    observed: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a presentation manifest; missing observations never become verified.

    Caller-supplied data is displayed only as untrusted, unverified reference
    metadata. The module does not authenticate the caller or its sources.
    """
    if observed is None:
        observed = {}
    if not isinstance(observed, dict):
        raise ValueError("invalid_observed")
    unknown = set(observed) - {key for key, _, _ in _STEPS}
    if unknown:
        raise ValueError("unknown_storyboard_step")
    steps = []
    for key, title, explanation in _STEPS:
        entry = observed.get(key)
        if entry is not None and not isinstance(entry, dict):
            raise ValueError("invalid_step_observation")
        entry = entry or {}
        # Do not trust caller-supplied verified flags or freeform payloads.
        source = entry.get("source")
        reference = entry.get("reference")
        if not isinstance(source, str) or not source.strip() or len(source) > 128:
            source = None
        if not isinstance(reference, str) or not reference.strip() or len(reference) > 128:
            reference = None
        steps.append({
            "step_id": key,
            "title": title,
            "explanation": explanation,
            "presentation": "OFFLINE_EXPLANATORY",
            "source_status": "CALLER_SUPPLIED_UNVERIFIED" if source and reference else "UNKNOWN",
            "source": source,
            "reference": reference,
            "runtime_verified": False,
            "effect_applied": False,
        })
    return {
        "schema": "aiops.acme-storyboard.v1",
        "mode": "OFFLINE_PRESENTATION",
        "classification": "SYNTHETIC_EXPLANATORY",
        "runtime_attested": False,
        "tenant_acl_qualified": False,
        "steps": deepcopy(steps),
    }
