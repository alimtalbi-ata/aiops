"""Pure safety helpers shared by API handlers and offline contract tests."""
import hashlib
import json


def canonical_sha256(value):
    """Stable digest for immutable proposal/policy snapshots."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def gold_set_eligible(run_mode, evidence_synthetic, human_reviewed, outcome_verified):
    """Only reviewed, independently verified, non-synthetic LIVE cases can be gold data."""
    return run_mode == "LIVE" and not evidence_synthetic and bool(human_reviewed) and bool(outcome_verified)


def critical_approval_complete(roles):
    """Critical actions require two different authorized roles, not merely two clicks."""
    return {"security_admin", "incident_commander"}.issubset({str(role).strip().lower() for role in roles})
