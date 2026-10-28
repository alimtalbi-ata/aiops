"""Fail-closed ACME DEMO ITSM binding contract; no network or ticket writes.

This pure verifier requires three separately acquired inputs: a canonical Core
readback, a GLPI API observation, and a signed binding receipt. Callers must
obtain them from trusted adapters, never from an arbitrary browser payload.
A contract match is NOT Temporal, monitoring, or LIVE attestation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

SCHEMA = "aiops.acme-itsm-binding.v1"
RECEIPT_SCHEMA = "aiops.acme-itsm-binding-receipt.v1"
CORE_SCHEMA = "aiops.acme-golden-run-readback.v1"
GLPI_SCHEMA = "aiops.glpi.ticket-observation.v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RUN = re.compile(r"RUN-[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z")
_TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z\Z")
_RECEIPT_FIELDS = frozenset({
    "schema", "issuer", "mode", "run_id", "incident_id", "ticket_id",
    "entity_id", "fixture_sha256", "issued_at_utc", "expires_at_utc",
})
MAX_RECEIPT_BYTES = 4096
MAX_AGE = timedelta(minutes=5)
CLOCK_SKEW = timedelta(seconds=30)


def _unknown() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "UNKNOWN", "reason": "BINDING_NOT_VERIFIED",
        "canonical_run_id": None, "canonical_incident_id": None,
        "glpi_ticket_id": None, "glpi_entity_id": None,
        "mode": None, "fixture_sha256": None,
        "glpi_correlation": "UNKNOWN", "runtime_attested": False,
        "production_qualified": False, "live_remediation_authorized": False,
    }


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate receipt field")
        out[key] = value
    return out


def _constant(value):
    raise ValueError("non-standard JSON")


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise ValueError("invalid UTC timestamp")
    result = datetime.fromisoformat(value[:-1] + "+00:00")
    if result.utcoffset() != timedelta(0):
        raise ValueError("invalid timezone")
    return result


def _positive_id(value: object) -> str:
    if (not isinstance(value, str) or not value.isascii()
            or not value.isdecimal() or len(value) > 10
            or not 1 <= int(value) <= 2147483647):
        raise ValueError("invalid ticket identifier")
    return str(int(value))


def correlate_acme_ticket(core: object, glpi: object, receipt_bytes: object,
                          receipt_signature: object, signing_key: object,
                          *, authorized_entity_id: object = None,
                          now: datetime | None = None) -> dict[str, Any]:
    """Verify a fresh HMAC Core binding against independent DEMO read models.

    Receipt signer and GLPI adapter are not implemented here. An application
    MUST authenticate both upstream sources and derive authorized_entity_id
    from trusted RBAC context, never from a browser-provided field. This is a
    GLPI entity fence, not a proof of Core tenant isolation.
    Invalid/expired/contradictory evidence returns UNKNOWN without identifiers.
    """
    unknown = _unknown()
    try:
        clock = now if now is not None else datetime.now(timezone.utc)
        if (not isinstance(clock, datetime) or clock.tzinfo is None
                or clock.utcoffset() is None):
            raise ValueError("naive clock")
        clock = clock.astimezone(timezone.utc)
        # The entity authorization scope is mandatory, independent of receipt
        # and GLPI content. bool is not a valid integer authorization scope.
        if (type(authorized_entity_id) is not int
                or not 0 <= authorized_entity_id <= 2147483647):
            raise ValueError("missing or invalid authorized GLPI entity scope")
        if (not isinstance(signing_key, bytes) or len(signing_key) < 32
                or not isinstance(receipt_bytes, bytes)
                or not 0 < len(receipt_bytes) <= MAX_RECEIPT_BYTES
                or not isinstance(receipt_signature, str)
                or _SHA.fullmatch(receipt_signature) is None):
            raise ValueError("invalid signed receipt")
        expected = hmac.new(signing_key, receipt_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, receipt_signature):
            raise ValueError("invalid signature")
        receipt = json.loads(receipt_bytes.decode("utf-8"), object_pairs_hook=_pairs,
                             parse_constant=_constant)
        if (not isinstance(receipt, dict) or frozenset(receipt) != _RECEIPT_FIELDS
                or receipt.get("schema") != RECEIPT_SCHEMA
                or receipt.get("issuer") != "CANONICAL_CORE_ITSMLINK"
                or receipt.get("mode") != "DEMO"):
            raise ValueError("invalid binding receipt")
        issued, expires = _utc(receipt["issued_at_utc"]), _utc(receipt["expires_at_utc"])
        if (expires <= issued or expires - issued > MAX_AGE
                or issued > clock + CLOCK_SKEW or expires <= clock):
            raise ValueError("expired or future receipt")
        if (not isinstance(core, dict) or core.get("schema") != CORE_SCHEMA
                or core.get("state") != "MATCHED_UNATTESTED"
                or core.get("mode") != "DEMO"
                or core.get("glpi_ticket_id") is not None
                or core.get("glpi_correlation") != "UNKNOWN"
                or core.get("runtime_attested") is not False
                or core.get("production_qualified") is not False
                or core.get("live_remediation_authorized") is not False
                or not isinstance(core.get("canonical_run_id"), str)
                or _RUN.fullmatch(core["canonical_run_id"]) is None
                or core.get("canonical_incident_id") != "INC-ACME-DEMO-SAN-001"
                or core.get("scenario_id") != "SCN-GOLDEN-PAYMENT-P1"
                or not isinstance(core.get("fixture_sha256"), str)
                or _SHA.fullmatch(core["fixture_sha256"]) is None):
            raise ValueError("unverified canonical Core readback")
        if (not isinstance(glpi, dict) or glpi.get("schema") != GLPI_SCHEMA
                or glpi.get("state") != "OBSERVED_UNCORRELATED"
                or glpi.get("source") != "AUTHENTICATED_GLPI_API_READ_NOT_ATTESTATION"
                or glpi.get("correlation_state") != "UNKNOWN"
                or glpi.get("incident_id") is not None or glpi.get("run_id") is not None
                or glpi.get("runtime_attested") is not False
                or glpi.get("production_qualified") is not False
                or glpi.get("live_remediation_authorized") is not False
                or type(glpi.get("entity_id")) is not int
                or not 0 <= glpi["entity_id"] <= 2147483647
                or not isinstance(glpi.get("response_sha256"), str)
                or _SHA.fullmatch(glpi["response_sha256"]) is None):
            raise ValueError("unverified GLPI observation")
        observed = _utc(glpi.get("read_at_utc"))
        if observed > clock + CLOCK_SKEW or clock - observed > MAX_AGE:
            raise ValueError("stale GLPI observation")
        ticket = _positive_id(glpi.get("ticket_id"))
        if (receipt.get("run_id") != core["canonical_run_id"]
                or receipt.get("incident_id") != core["canonical_incident_id"]
                or receipt.get("fixture_sha256") != core["fixture_sha256"]
                or receipt.get("ticket_id") != ticket
                or type(receipt.get("entity_id")) is not int
                or receipt["entity_id"] != glpi["entity_id"]
                or receipt["entity_id"] != authorized_entity_id):
            raise ValueError("identity or entity mismatch")
        return {
            "schema": SCHEMA, "state": "CONTRACT_MATCHED_UNATTESTED",
            "reason": "FRESH_SIGNED_BINDING_AND_GLPI_OBSERVATION_MATCH",
            "canonical_run_id": core["canonical_run_id"],
            "canonical_incident_id": core["canonical_incident_id"],
            "glpi_ticket_id": ticket, "glpi_entity_id": glpi["entity_id"],
            "mode": "DEMO", "fixture_sha256": core["fixture_sha256"],
            "glpi_correlation": "CONTRACT_MATCHED_UNATTESTED",
            "runtime_attested": False, "production_qualified": False,
            "live_remediation_authorized": False,
        }
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        return unknown
