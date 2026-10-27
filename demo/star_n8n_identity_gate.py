"""Offline, fail-closed V1 workflow 02 -> 03 canonical identity qualification.

No n8n API, network, imports, ticket writes, or synthetic identity creation.
Only sanitized four-stage observations may be supplied by an operator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Mapping

STAGES = ("webhook_02", "rag_02", "canonical_02", "prepare_analyst_03")
FIELDS = ("run_id", "incident_id", "correlation_id")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,95}\Z")
MAX_BYTES = 16384


class IdentityRejected(ValueError):
    """A required upstream identity is missing, invalid, or contradictory."""


def _identity(stage: str, payload: object) -> dict[str, str]:
    if not isinstance(payload, Mapping):
        raise IdentityRejected(f"{stage}: missing identity object")
    # Refuse unknown/alias fields: a second identity must not be hidden beside
    # the canonical one (e.g. runId, identity.run_id or a shadow run_id).
    # The input contract is intentionally *only* the three canonical strings.
    if set(payload) != set(FIELDS):
        raise IdentityRejected(f"{stage}: identity schema mismatch")
    result: dict[str, str] = {}
    for field in FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            raise IdentityRejected(f"{stage}: {field} missing or invalid")
        result[field] = value
    return result


def verify_handoff(observations: object) -> dict[str, object]:
    """Require independently observed, identical identities at all four stages.

    The input is evidence supplied by an operator, not a source of truth. This
    validates consistency only, not actual n8n execution or business success.
    """
    if not isinstance(observations, Mapping) or set(observations) != set(STAGES):
        raise IdentityRejected("all four exact workflow stages required")
    first = _identity(STAGES[0], observations[STAGES[0]])
    for stage in STAGES[1:]:
        current = _identity(stage, observations[stage])
        for field in FIELDS:
            if current[field] != first[field]:
                raise IdentityRejected(f"{stage}: contradictory {field}")
    fingerprint = hashlib.sha256(json.dumps(first, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": "STAR_N8N_IDENTITY_HANDOFF_V1",
        "result": "CONSISTENT_UNAUTHENTICATED",
        "identity_sha256": fingerprint,
        "stages_checked": list(STAGES),
        "run_id": first["run_id"],
        "incident_id": first["incident_id"],
        "correlation_id": first["correlation_id"],
        "runtime_execution_authenticated": False,
        "analyst_completed": False,
        "business_outcome_verified": False,
        "live_remediation_authorized": False,
    }


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise IdentityRejected("duplicate JSON key")
        result[key] = value
    return result


def read_observations(path: Path) -> object:
    """Read only a small local, non-symlink, sanitized JSON sample."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise IdentityRejected("unsafe or oversized evidence input")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise IdentityRejected("invalid JSON") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline n8n 02/03 run identity consistency gate")
    parser.add_argument("sanitized_stages", type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify_handoff(read_observations(args.sanitized_stages))
    except (IdentityRejected, OSError):
        # Never echo input content, URLs, paths, credentials or raw exceptions.
        print(json.dumps({"result": "BLOCKED", "reason": "IDENTITY_UNVERIFIED"}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
