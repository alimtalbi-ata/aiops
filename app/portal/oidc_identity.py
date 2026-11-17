"""Server-only OIDC identity verification for a future Portal authorization handshake.

No Portal route consumes this verifier yet. The browser's Authorization header,
X-Actor, X-Tenant, GLPI profile and Run ID are never an actor/tenant authority.
Only a trusted server-side OIDC code-exchange callback may pass its ID token
here. A verified identity is NOT a Core exact-Run/ticket authorization.
JWKS are provisioned out of band, never fetched from untrusted token URLs.
"""
from __future__ import annotations

import base64
import binascii
import json
import hmac
import os
import re
import time
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

_B64 = re.compile(r"[A-Za-z0-9_-]+\Z")
_SUBJECT = re.compile(r"[\x21-\x7e]{1,255}\Z")
_ROLES = frozenset({"N1", "N2", "N3", "manager"})
_MAX_JWT_BYTES = 16384
_MAX_TOKEN_AGE = 3600
_CLOCK_SKEW = 30


class IdentityRejected(ValueError):
    """The assertion, tenant mapping or verified claims cannot be trusted."""


class IdentityUnavailable(RuntimeError):
    """Server identity configuration or signature-verification engine missing."""


@dataclass(frozen=True)
class PortalActorContext:
    subject: str
    tenant_id: str
    roles: tuple[str, ...]
    issuer: str
    audience: str
    # This is identity evidence only; Core must separately qualify exact ACL.
    tenant_acl_qualified: bool = False
    expires_at: int = 0


def _json_strict(raw: str | bytes) -> object:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise IdentityRejected("duplicate JSON member")
            result[key] = value
        return result
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise IdentityRejected("invalid identity JSON") from exc


def _decode(value: str) -> bytes:
    if not isinstance(value, str) or not value or _B64.fullmatch(value) is None:
        raise IdentityRejected("invalid base64url")
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4),
                                altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise IdentityRejected("invalid base64url") from exc


def _map(raw: str, name: str) -> dict[str, str]:
    value = _json_strict(raw)
    if (not isinstance(value, dict) or not value or len(value) > 128
            or any(not isinstance(k, str) or not k or len(k) > 128
                   or not isinstance(v, str) or not v or len(v) > 128
                   or not v.isascii() or not v.isprintable()
                   for k, v in value.items())):
        raise IdentityUnavailable("invalid " + name)
    return value


def _configuration(env: Mapping[str, str]) -> tuple[str, str, dict, dict, dict]:
    issuer = env.get("AIOPS_PORTAL_OIDC_ISSUER", "")
    audience = env.get("AIOPS_PORTAL_OIDC_AUDIENCE", "")
    try:
        parsed = urlsplit(issuer)
    except ValueError as exc:
        raise IdentityUnavailable("invalid OIDC issuer") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or not audience or len(audience) > 256
            or not audience.isascii() or not audience.isprintable()):
        raise IdentityUnavailable("invalid OIDC issuer/audience")
    jwks = _json_strict(env.get("AIOPS_PORTAL_OIDC_JWKS_JSON", ""))
    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise IdentityUnavailable("invalid pinned JWKS")
    tenant_map = _map(env.get("AIOPS_PORTAL_OIDC_TENANT_GROUP_MAP_JSON", ""),
                      "tenant group map")
    role_map = _map(env.get("AIOPS_PORTAL_OIDC_ROLE_GROUP_MAP_JSON", ""),
                    "role group map")
    if any(role not in _ROLES for role in role_map.values()):
        raise IdentityUnavailable("invalid Portal role mapping")
    return issuer, audience, jwks, tenant_map, role_map


def _verify_rs256(signing_input: bytes, signature: bytes,
                  kid: str, jwks: dict) -> None:
    keys = jwks["keys"]
    if not keys or len(keys) > 32:
        raise IdentityRejected("invalid JWKS key set")
    matches = [key for key in keys if isinstance(key, dict)
               and key.get("kid") == kid]
    if len(matches) != 1:
        raise IdentityRejected("unknown or ambiguous signing key")
    key = matches[0]
    if (key.get("kty") != "RSA" or key.get("alg", "RS256") != "RS256"
            or key.get("use", "sig") != "sig"):
        raise IdentityRejected("unsupported signing key")
    try:
        n = int.from_bytes(_decode(key["n"]), "big")
        e = int.from_bytes(_decode(key["e"]), "big")
    except (KeyError, TypeError) as exc:
        raise IdentityRejected("invalid RSA JWK") from exc
    if n.bit_length() < 2048 or e != 65537 or len(signature) != (n.bit_length() + 7) // 8:
        raise IdentityRejected("invalid RSA key or signature size")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
    except ImportError as exc:
        raise IdentityUnavailable("OIDC RSA verifier not installed") from exc
    try:
        public_key = rsa.RSAPublicNumbers(e, n).public_key()
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, ValueError) as exc:
        raise IdentityRejected("OIDC signature rejected") from exc


def verify_server_oidc_assertion(token: str, *,
                                 env: Mapping[str, str] | None = None,
                                 now: int | None = None,
                                 expected_nonce: str | None = None) -> PortalActorContext:
    """Verify an ID token obtained by the SERVER from its trusted IdP.

    This function MUST NOT be called with an unverified browser bearer, proxy
    identity header, or client-provided tenant/actor. It grants no data access.
    """
    settings = os.environ if env is None else env
    issuer, audience, jwks, tenant_map, role_map = _configuration(settings)
    if (not isinstance(token, str) or len(token) > _MAX_JWT_BYTES
            or not token.isascii() or token.count(".") != 2):
        raise IdentityRejected("invalid OIDC assertion")
    header_part, payload_part, signature_part = token.split(".")
    header = _json_strict(_decode(header_part))
    payload = _json_strict(_decode(payload_part))
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise IdentityRejected("invalid JWT structure")
    kid = header.get("kid")
    if (header.get("alg") != "RS256" or header.get("typ", "JWT") != "JWT"
            or not isinstance(kid, str) or not kid or len(kid) > 128
            or "jku" in header or "x5u" in header or "crit" in header):
        raise IdentityRejected("unsupported JWT header")
    signing_input = (header_part + "." + payload_part).encode("ascii")
    _verify_rs256(signing_input, _decode(signature_part), kid, jwks)
    clock = int(time.time()) if now is None else int(now)
    exp, nbf, iat = payload.get("exp"), payload.get("nbf"), payload.get("iat")
    if (payload.get("iss") != issuer or payload.get("aud") != audience
            or type(exp) is not int or type(nbf) is not int or type(iat) is not int
            or exp <= clock or nbf > clock + _CLOCK_SKEW
            or iat > clock + _CLOCK_SKEW or exp <= iat
            or exp - iat > _MAX_TOKEN_AGE or iat < clock - _MAX_TOKEN_AGE):
        raise IdentityRejected("OIDC issuer/audience/lifetime rejected")
    if expected_nonce is not None:
        nonce = payload.get("nonce")
        if (not isinstance(expected_nonce, str) or not expected_nonce
                or not isinstance(nonce, str)
                or not hmac.compare_digest(nonce, expected_nonce)):
            raise IdentityRejected("OIDC nonce rejected")
    subject, groups = payload.get("sub"), payload.get("groups")
    if (not isinstance(subject, str) or _SUBJECT.fullmatch(subject) is None
            or not isinstance(groups, list) or not groups or len(groups) > 64
            or any(not isinstance(g, str) or not g or len(g) > 128
                   for g in groups)):
        raise IdentityRejected("invalid subject/groups")
    tenants = {tenant_map[g] for g in groups if g in tenant_map}
    roles = tuple(sorted({role_map[g] for g in groups if g in role_map}))
    if len(tenants) != 1 or not roles:
        raise IdentityRejected("ambiguous or unmapped tenant/role")
    return PortalActorContext(subject, tenants.pop(), roles, issuer, audience,
                              expires_at=exp)


def core_xref_preflight(identity: PortalActorContext, *, tenant_id: str,
                        run_id: str, ticket_id: str,
                        env: Mapping[str, str] | None = None) -> dict:
    """Preflight only: NEVER performs HTTP or authorizes a Core/GLPI read.

    A future Core adapter needs its own service token and a positive server
    authorization decision for this exact tenant/Run/ticket association.
    """
    settings = os.environ if env is None else env
    service = settings.get("AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN", "")
    viewer = settings.get("AIOPS_PORTAL_READ_TOKEN", "")
    operator = settings.get("AIOPS_PORTAL_OPERATOR_TOKEN", "")
    if (not isinstance(identity, PortalActorContext)
            or identity.tenant_acl_qualified is not False
            or identity.tenant_id != tenant_id
            or not isinstance(run_id, str) or not re.fullmatch(r"RUN-[A-Za-z0-9_.-]{2,124}", run_id)
            or not isinstance(ticket_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", ticket_id)
            or len(service) < 32 or len(service) > 256 or not service.isascii()
            or not service.isprintable() or any(ch.isspace() for ch in service)
            or service in (viewer, operator)):
        raise IdentityRejected("Core xref preflight rejected")
    # Do not return the service secret or use it in a browser request.
    return {"state": "UNKNOWN", "reason": "TENANT_ACL_NOT_QUALIFIED",
            "connection_state": "UNKNOWN", "tenant_acl_qualified": False}
