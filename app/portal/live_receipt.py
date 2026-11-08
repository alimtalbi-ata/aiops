"""Read-only qualification receipt adapter for the Portal; no network or side effects."""
from datetime import datetime, timezone


def portal_usecase_status(receipt, now_utc, max_age_seconds=180):
    """Return evidence state, never equating missing proof with a functional failure."""
    if not isinstance(receipt, dict):
        return {"status": "UNVERIFIED", "reason": "receipt_missing", "holds": []}
    timestamp = receipt.get("collected_at")
    if not isinstance(timestamp, str):
        return {"status": "UNVERIFIED", "reason": "timestamp_missing", "holds": []}
    try:
        collected = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if collected.tzinfo is None:
            raise ValueError("naive timestamp")
        age = (now_utc.astimezone(timezone.utc) - collected.astimezone(timezone.utc)).total_seconds()
    except (ValueError, TypeError, AttributeError):
        return {"status": "UNVERIFIED", "reason": "timestamp_invalid", "holds": []}
    if age < -30:
        return {"status": "UNVERIFIED", "reason": "timestamp_future", "holds": []}
    if age > max_age_seconds:
        return {"status": "STALE", "reason": "receipt_too_old", "holds": []}
    checks = receipt.get("checks")
    if not isinstance(checks, list):
        return {"status": "UNVERIFIED", "reason": "checks_missing", "holds": []}
    holds = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("status") == "HOLD":
            holds.append({"id": str(check.get("id") or "unknown"),
                          "reason": str(check.get("reason") or "unspecified")})
    return {"status": "HOLD" if holds else "UNVERIFIED", "reason": "hold_reported" if holds else "no_hold_not_proof_of_pass", "holds": holds}
