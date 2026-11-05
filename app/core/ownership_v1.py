"""Core #233 ownership v1: fail-closed verification primitive, NOT an authorization endpoint.

A trusted caller must verify OIDC issuer/audience/signature and independent GLPI READMY
ownership before issuing. A durable PostgreSQL consume callback must atomically INSERT
the jti under a UNIQUE constraint in the same transaction as authorization recording.
No in-memory replay cache, synthetic positive authority or LIVE side effect.
"""
import hashlib
import hmac
import json
import time

FIELDS = ("version", "issuer", "subject", "tenant_id", "actor_id", "incident_id",
          "run_id", "glpi_ticket_id", "glpi_entity_id", "scope", "jti", "iat", "exp",
          "oidc_proof_sha256", "glpi_readmy_proof_sha256")
VERSION = "aiops.core-ownership-proof.v1"


class OwnershipDenied(Exception):
    """Fail closed; HTTP adapter must map missing authority to 503 UNKNOWN."""


def canonical(claims):
    if not isinstance(claims, dict) or set(claims) != set(FIELDS):
        raise OwnershipDenied("schema")
    return json.dumps(claims, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sign(claims, core_key):
    if not isinstance(core_key, bytes) or len(core_key) < 32:
        raise OwnershipDenied("core signing key unavailable")
    return hmac.new(core_key, canonical(claims), hashlib.sha256).hexdigest()


def verify_and_consume(claims, signature, core_key, expected, oidc_verified,
                       glpi_readmy_verified, consume_once, now=None):
    """consume_once(issuer,jti,expires_at) MUST be a durable atomic PG16 insert.

    Returns verified claims only after the durable transaction commits.
    Any exception from consume_once is an UNKNOWN denial, never ALLOW.
    """
    if oidc_verified is not True or glpi_readmy_verified is not True:
        raise OwnershipDenied("independent authority missing")
    if not callable(consume_once):
        raise OwnershipDenied("durable ledger missing")
    if not isinstance(signature, str) or len(signature) != 64:
        raise OwnershipDenied("signature format")
    candidate = sign(claims, core_key)
    if not hmac.compare_digest(candidate, signature):
        raise OwnershipDenied("signature")
    if claims["version"] != VERSION or claims["scope"] != "run:read":
        raise OwnershipDenied("version or scope")
    if any(not isinstance(claims[k], str) or not claims[k].strip()
           for k in FIELDS if k not in ("iat", "exp")):
        raise OwnershipDenied("empty binding")
    if any(len(claims[k]) != 64 or any(c not in "0123456789abcdef" for c in claims[k])
           for k in ("oidc_proof_sha256", "glpi_readmy_proof_sha256")):
        raise OwnershipDenied("provenance digest")
    if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
        raise OwnershipDenied("time schema")
    if now is not None and type(now) is not int:
        raise OwnershipDenied("clock schema")
    t = int(time.time()) if now is None else now
    if (claims["iat"] > t + 30 or claims["exp"] <= t or
            claims["exp"] <= claims["iat"] or claims["exp"] - claims["iat"] > 300):
        raise OwnershipDenied("expired or excessive validity")
    required = ("issuer", "subject", "tenant_id", "actor_id", "incident_id",
                "run_id", "glpi_ticket_id", "glpi_entity_id")
    if not isinstance(expected, dict) or set(expected) != set(required):
        raise OwnershipDenied("expected binding unavailable")
    if any(type(expected[k]) is not str or not expected[k].strip() for k in required):
        raise OwnershipDenied("expected binding schema")
    if any(not hmac.compare_digest(claims[k], expected[k]) for k in required):
        raise OwnershipDenied("binding mismatch")
    try:
        consumed = consume_once(claims["issuer"], claims["jti"], claims["exp"])
    except Exception as exc:
        raise OwnershipDenied("ledger unavailable") from exc
    if consumed is not True:
        raise OwnershipDenied("replay or ledger unknown")
    return dict(claims)
