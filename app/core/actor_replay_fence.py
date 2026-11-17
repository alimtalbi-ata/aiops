"""Durable, negative-only actor replay fence; PostgreSQL is the audit authority.

An accepted nonce/JTI is not an actor permission or an ALLOW decision. The
caller must independently authenticate IdP, GLPI human session and Core xref
before attempting a consume. All failures remain non-enumerating.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from core import itsm_xref as x

SCHEMA = "aiops.core-actor-resource-authorization.v1"
_RESOURCE_KEYS = ("tenant_id", "run_id", "incident_id", "glpi_instance_id",
                  "ticket_id", "glpi_entity_id", "permission", "nonce")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _resource_digest(expected: dict) -> str:
    # Domain-separated and canonical: a nonce from a different ticket, entity,
    # tenant, Run or permission must never authorize this exact resource.
    scope = {key: expected[key] for key in _RESOURCE_KEYS}
    raw = json.dumps({"schema": SCHEMA, "scope": scope},
                     sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _digest(raw)


def consume_actor_delegation(claims: dict, expected: dict, now: int):
    """Return True only for an atomic first consume, False for refusal, None on DB error.

    The SQL function serializes concurrent consume/revoke on issuer+JTI and
    persists immutable audit rows. This helper never issues ALLOW, never deletes
    audit rows, and never calls GLPI or the IdP.
    """
    try:
        if (not isinstance(claims, dict) or not isinstance(expected, dict)
                or type(now) is not int
                or any(not isinstance(expected.get(k), str) or not expected[k]
                       for k in _RESOURCE_KEYS)
                or any(not isinstance(claims.get(k), str) or not claims[k]
                       for k in ("iss", "sub", "jti"))
                or type(claims.get("exp")) is not int
                or not now < claims["exp"] <= now + 300):
            return False
        expiry = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        args = (expected["tenant_id"], claims["iss"], _digest(claims["sub"]),
                _digest(claims["jti"]), _digest(expected["nonce"]),
                _resource_digest(expected), expiry)
        with x.db() as conn:
            result = conn.execute(
                "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,%s)",
                args).fetchone()
        return result is not None and len(result) == 1 and result[0] is True
    except (ValueError, TypeError, KeyError, OverflowError):
        return False
    except Exception:
        # DB/schema/connection failure must never become a positive decision.
        return None
