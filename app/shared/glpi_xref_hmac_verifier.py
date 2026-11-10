"""HMAC-SHA256 verification for server-fetched canonical GLPI xref events.

This is a concrete trust adapter, NOT a production-installed trust root.
A deployment must supply a protected key, durable replay protection, and a
server-owned actor/tenant ACL evaluator. Never accept these from HTTP clients.
"""
import hashlib
import hmac
import json
import time
from collections.abc import Callable


class XrefSignatureRejected(ValueError):
    pass


def canonical_event_bytes(claims):
    if not isinstance(claims, dict):
        raise XrefSignatureRejected("claims_invalid")
    return json.dumps(claims, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def verify_hmac_xref_event(
    *, event, actor, tenant_id, ticket_id, secret: bytes,
    consume_nonce: Callable | None = None,
    authorize_actor: Callable | None = None,
    now: int | None = None,
    expected_audience="aiops-glpi-copilot-xref",
    expected_issuer="aiops-core-xref-signer",
):
    """Verify signature, scope, audience, time, replay and server ACL.

    consume_nonce(tenant_id=..., nonce=..., expires_at=...) must be an atomic,
    durable insert-if-absent. authorize_actor(...) must enforce server ACL.
    Both callbacks must return exactly True to authorize. No writes to GLPI.
    """
    if (not isinstance(secret, bytes) or len(secret) < 32
            or not callable(consume_nonce) or not callable(authorize_actor)):
        raise XrefSignatureRejected("trust_dependencies_missing")
    if not isinstance(event, dict) or set(event) != {"claims", "signature"}:
        raise XrefSignatureRejected("event_shape_invalid")
    claims, signature = event["claims"], event["signature"]
    if not isinstance(claims, dict) or not isinstance(signature, str):
        raise XrefSignatureRejected("signature_missing")
    if len(signature) != 64 or any(c not in "0123456789abcdef" for c in signature):
        raise XrefSignatureRejected("signature_format_invalid")
    try:
        signed = canonical_event_bytes(claims)
    except (TypeError, ValueError, OverflowError) as exc:
        raise XrefSignatureRejected("claims_not_canonical") from exc
    expected = hmac.new(secret, signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise XrefSignatureRejected("signature_invalid")
    if (claims.get("aud") != expected_audience
            or claims.get("iss") != expected_issuer
            or claims.get("actor") != actor
            or claims.get("tenant_id") != tenant_id
            or claims.get("ticket_id") != ticket_id):
        raise XrefSignatureRejected("signed_scope_invalid")
    issued, expiry, nonce = (claims.get("iat"), claims.get("exp"),
                             claims.get("nonce"))
    current = int(time.time()) if now is None else now
    if (type(current) is not int or type(issued) is not int
            or type(expiry) is not int or issued > current + 30
            or expiry <= current or expiry - issued > 300
            or issued > expiry):
        raise XrefSignatureRejected("signed_time_invalid")
    if (claims.get("association_state") != "ACTIVE"
            or type(claims.get("association_count")) is not int
            or claims["association_count"] != 1):
        raise XrefSignatureRejected("signed_association_not_unique_active")
    required_identity = ("glpi_instance_id", "glpi_entity_id",
                         "incident_id", "run_id")
    if any(not isinstance(claims.get(field), str) or not claims[field]
           for field in required_identity):
        raise XrefSignatureRejected("signed_identity_missing")
    if (not isinstance(nonce, str) or not 16 <= len(nonce) <= 128
            or not nonce.isascii() or not nonce.isalnum()):
        raise XrefSignatureRejected("signed_nonce_invalid")
    if authorize_actor(actor=actor, tenant_id=tenant_id,
                       ticket_id=ticket_id, claims=claims) is not True:
        raise XrefSignatureRejected("actor_acl_denied")
    if consume_nonce(tenant_id=tenant_id, nonce=nonce,
                     expires_at=expiry) is not True:
        raise XrefSignatureRejected("replayed_event")
    return dict(claims)
