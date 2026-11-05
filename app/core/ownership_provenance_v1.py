"""Core #233: evidence-bound authority adapter, not a public HTTP route.

Provider callbacks must independently validate OIDC and GLPI READMY evidence.
They return an exact verification record, not a caller-supplied allow boolean.
This module never fetches GLPI, validates OIDC itself, or activates LIVE work.
"""
import hmac

from app.core.ownership_http_v1 import ownership_http_decision


def ownership_evidence_http_decision(claims, signature, core_key, expected,
                                     oidc_verifier, glpi_readmy_verifier,
                                     consume_once, now=None):
    """Return 503 UNKNOWN unless both independently verified evidence digests bind.

    Provider result schema: {"verified": True, "proof_sha256": lowercase hex}.
    The providers must validate provenance, expiry, revocation and subject/tenant
    against trusted sources before returning this record.
    """
    unknown = (503, {"status": "UNKNOWN"})
    if not callable(oidc_verifier) or not callable(glpi_readmy_verifier):
        return unknown
    if oidc_verifier is glpi_readmy_verifier:
        return unknown
    if type(claims) is not dict:
        return unknown

    def bind(provider, field):
        def verify(signed_claims, bindings):
            result = provider(signed_claims, bindings)
            if type(result) is not dict or set(result) != {"verified", "proof_sha256"}:
                return False
            digest = result["proof_sha256"]
            claimed = signed_claims.get(field)
            return (result["verified"] is True
                    and type(digest) is str and len(digest) == 64
                    and all(c in "0123456789abcdef" for c in digest)
                    and type(claimed) is str
                    and hmac.compare_digest(digest, claimed))
        return verify

    return ownership_http_decision(
        claims, signature, core_key, expected,
        bind(oidc_verifier, "oidc_proof_sha256"),
        bind(glpi_readmy_verifier, "glpi_readmy_proof_sha256"),
        consume_once, now=now,
    )
