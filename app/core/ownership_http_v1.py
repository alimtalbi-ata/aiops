"""Core #233 fail-closed HTTP boundary for ownership verification.

Not a route and not an authority provider. The caller MUST inject independently
trusted OIDC and GLPI READMY verification functions and a durable PG16 ledger.
No synthetic positive evidence, network call, or LIVE side effect occurs here.
"""
from app.core.ownership_v1 import OwnershipDenied, verify_and_consume


def ownership_http_decision(claims, signature, core_key, expected,
                            oidc_authority, glpi_readmy_authority,
                            consume_once, now=None):
    """Return (HTTP status, payload). Unknown or denied is always HTTP 503.

    Authority functions MUST validate independent evidence themselves; a
    caller-supplied boolean cannot substitute for either authority.
    """
    if not callable(oidc_authority) or not callable(glpi_readmy_authority):
        return 503, {"status": "UNKNOWN"}
    try:
        oidc_ok = oidc_authority(claims, expected)
        if oidc_ok is not True:
            return 503, {"status": "UNKNOWN"}
        glpi_ok = glpi_readmy_authority(claims, expected)
        if glpi_ok is not True:
            return 503, {"status": "UNKNOWN"}
        verified = verify_and_consume(
            claims, signature, core_key, expected,
            oidc_verified=True, glpi_readmy_verified=True,
            consume_once=consume_once, now=now,
        )
        return 200, {"status": "VERIFIED", "run_id": verified["run_id"],
                     "incident_id": verified["incident_id"]}
    except (OwnershipDenied, Exception):
        # Even unexpected provider/ledger failures must never produce ALLOW.
        return 503, {"status": "UNKNOWN"}
