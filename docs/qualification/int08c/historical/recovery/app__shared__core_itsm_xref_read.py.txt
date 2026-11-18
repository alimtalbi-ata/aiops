"""Proposed Core-owned ITSM cross-reference *read contract*, not a connector.

This is a fail-closed projection for issue #203. The injectable ``core_get``
MUST be implemented by a trusted, tenant-scoped, authenticated Core client.
Nothing in this module opens sockets, reads GLPI, or authenticates a caller.
An ID in ticket text is never a link. This module is not wired into Portal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

SCHEMA = "aiops.core-itsm-xref-read.v1"
ENDPOINT_TEMPLATE = "/api/tenants/{tenant_id}/itsm/glpi/{instance_id}/tickets/{ticket_id}/xref"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z", re.ASCII)
_TICKET = re.compile(r"[1-9][0-9]{0,17}\Z", re.ASCII)
_RUN = re.compile(r"RUN-[A-Za-z0-9_-]{1,96}\Z", re.ASCII)
_INC = re.compile(r"INC-[A-Za-z0-9_-]{1,96}\Z", re.ASCII)
_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z", re.ASCII)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_ALLOWED = frozenset({"schema", "status", "tenant_id", "glpi_instance_id", "ticket_id",
    "incident_id", "run_id", "source_system", "source_event_id", "association_id",
    "mapping_version", "verification_method", "tenant_acl_qualified",
    "glpi_ticket_readback_verified", "core_run_readback_verified",
    "observed_at", "known_at", "provenance"})


@dataclass(frozen=True)
class CoreRead:
    """Trusted Core HTTP adapter result (never populate from untrusted JSON)."""
    http_status: int
    body: object = None
    authenticated: bool = False
    tenant_acl_checked: bool = False


def _utc(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 48 or _STAMP.fullmatch(value) is None:
        return None
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        dt = dt.astimezone(timezone.utc)
        return dt if dt >= _EPOCH else None
    except (OverflowError, ValueError, TypeError):
        return None


def _result(link_status="UNKNOWN", connection_state="UNKNOWN", reason="CORE_XREF_NOT_VERIFIED", **verified):
    result = {"schema": SCHEMA, "link_status": link_status,
              "connection_state": connection_state, "reason": reason,
              "tenant_id": None, "glpi_instance_id": None, "ticket_id": None,
              "incident_id": None, "run_id": None, "ci_ids": [],
              "evidence_id": None, "verified_evidence_ids": [],
              "source_event_id": None, "association_id": None,
              "mapping_version": None, "observed_at": None, "known_at": None,
              "provenance": None}
    result.update(verified)
    return result


def resolve_ticket_run(*, tenant_id: str, tenant_authenticated: bool,
                       tenant_acl_qualified: bool, glpi_instance_id: str,
                       ticket_id: str, expected_incident_id: str | None = None,
                       expected_run_id: str | None = None,
                       evidence_known_at: str | None = None,
                       core_get: Callable[[str], CoreRead] | None = None,
                       now: datetime | None = None) -> dict:
    """Validate caller identity and Core read-back; expose Run only if VERIFIED.

    ``tenant_*`` MUST come from trusted server auth middleware, never request
    JSON. ``core_get`` MUST pin Core origin, use a scoped service credential,
    enforce GET/no redirects/response bounds, and return its own auth/ACL flags.
    The endpoint is a *proposal*, not implemented on main as of 2026-10-30.
    No GLPI call, ticket-text search, DB access or Evidence promotion occurs.
    """
    if (not isinstance(tenant_id, str) or _ID.fullmatch(tenant_id) is None or
            tenant_authenticated is not True or tenant_acl_qualified is not True):
        return _result(reason="TENANT_AUTH_OR_SCOPE_INVALID")
    if (not isinstance(glpi_instance_id, str) or _ID.fullmatch(glpi_instance_id) is None or
            not isinstance(ticket_id, str) or _TICKET.fullmatch(ticket_id) is None or
            (expected_run_id is not None and (not isinstance(expected_run_id, str) or
                 _RUN.fullmatch(expected_run_id) is None)) or
            (expected_incident_id is not None and (not isinstance(expected_incident_id, str) or
                 _INC.fullmatch(expected_incident_id) is None))):
        return _result(reason="IDENTIFIER_PREFLIGHT_INVALID")
    try:
        clock = datetime.now(timezone.utc) if now is None else now
        if not isinstance(clock, datetime) or clock.utcoffset() is None:
            raise ValueError("invalid clock")
        clock = clock.astimezone(timezone.utc)
        if clock < _EPOCH or clock.year >= 9999:
            raise ValueError("out-of-range clock")
        if evidence_known_at is not None:
            evidence_stamp = _utc(evidence_known_at)
            # Core rejects future Evidence and refuses to verify a stale
            # Evidence binding. The consumer must apply the same fence even
            # when the injected core_get does not forward query parameters.
            if evidence_stamp is None or evidence_stamp > clock:
                raise ValueError("invalid Evidence time")
            if clock - evidence_stamp > timedelta(minutes=5):
                return _result(link_status="STALE", connection_state="UNKNOWN",
                               reason="EVIDENCE_STALE")
    except (OverflowError, TypeError, ValueError):
        return _result(reason="UTC_PREFLIGHT_INVALID")
    if core_get is None:
        return _result(connection_state="NOT_INSTALLED", reason="CORE_XREF_ENDPOINT_NOT_INSTALLED")
    path = ENDPOINT_TEMPLATE.format(tenant_id=tenant_id, instance_id=glpi_instance_id,
                                    ticket_id=ticket_id)
    try:
        response = core_get(path)
    except Exception:
        return _result(connection_state="UNAVAILABLE", reason="CORE_READ_UNAVAILABLE")
    if not isinstance(response, CoreRead) or type(response.http_status) is not int:
        return _result(connection_state="UNAVAILABLE", reason="CORE_TRANSPORT_UNQUALIFIED")
    if response.http_status in (401, 403):
        return _result(link_status="UNAUTHORIZED", connection_state="UNAUTHORIZED",
                       reason="CORE_AUTH_OR_TENANT_DENIED")
    if response.http_status not in (200, 404):
        return _result(connection_state="UNAVAILABLE", reason="CORE_READ_UNAVAILABLE")
    if response.authenticated is not True or response.tenant_acl_checked is not True:
        return _result(link_status="UNAUTHORIZED", connection_state="UNAUTHORIZED",
                       reason="CORE_AUTH_OR_TENANT_UNQUALIFIED")
    if response.http_status == 404:
        return _result(connection_state="CONNECTED", reason="NO_AUTHORITATIVE_MAPPING")
    body = response.body
    if not isinstance(body, dict) or not set(body).issubset(_ALLOWED) or body.get("schema") != SCHEMA:
        return _result(connection_state="CONNECTED", reason="CORE_XREF_CONTRACT_INVALID")
    status = body.get("status")
    # Core intentionally omits all business IDs on UNKNOWN/CONFLICT/STALE.
    # These are authenticated, tenant-scoped *negative* read-backs, not
    # VERIFIED mappings. Never reinterpret their missing IDs as 403.
    # Conversely, reject any explicitly contradictory scope returned by Core.
    if body.get("tenant_id") is not None and body["tenant_id"] != tenant_id:
        return _result(link_status="UNAUTHORIZED", connection_state="UNAUTHORIZED",
                       reason="CROSS_TENANT_MAPPING_DENIED")
    if ((body.get("glpi_instance_id") is not None and body["glpi_instance_id"] != glpi_instance_id)
            or (body.get("ticket_id") is not None and body["ticket_id"] != ticket_id)):
        return _result(connection_state="CONNECTED", reason="AUTHORITATIVE_ID_MISMATCH")
    if status in ("CONFLICT", "STALE"):
        return _result(link_status=status, connection_state="CONNECTED", reason="CORE_MAPPING_" + status)
    if status != "VERIFIED":
        return _result(connection_state="CONNECTED", reason="CORE_MAPPING_NOT_VERIFIED")
    # Positive links require every canonical identifier, not just an
    # authenticated transport and a status string.
    if body.get("tenant_id") != tenant_id:
        return _result(link_status="UNAUTHORIZED", connection_state="UNAUTHORIZED",
                       reason="CROSS_TENANT_MAPPING_DENIED")
    if (body.get("glpi_instance_id") != glpi_instance_id or
            body.get("ticket_id") != ticket_id or
            not isinstance(body.get("run_id"), str) or _RUN.fullmatch(body["run_id"]) is None or
            not isinstance(body.get("incident_id"), str) or _INC.fullmatch(body["incident_id"]) is None or
            (expected_run_id is not None and body["run_id"] != expected_run_id) or
            (expected_incident_id is not None and body["incident_id"] != expected_incident_id)):
        return _result(connection_state="CONNECTED", reason="AUTHORITATIVE_ID_MISMATCH")
    if (body.get("tenant_acl_qualified") is not True or
            body.get("glpi_ticket_readback_verified") is not True or
            body.get("core_run_readback_verified") is not True or
            body.get("source_system") != "GLPI" or
            body.get("verification_method") != "AUTHENTICATED_ID_READBACK" or
            not isinstance(body.get("source_event_id"), str) or
            _ID.fullmatch(body["source_event_id"]) is None or
            not isinstance(body.get("association_id"), str) or
            _ID.fullmatch(body["association_id"]) is None or
            type(body.get("mapping_version")) is not int or body["mapping_version"] < 1 or
            body.get("provenance") != "AUTHENTICATED_SOURCE_API"):
        return _result(connection_state="CONNECTED", reason="PROVENANCE_OR_ACL_UNQUALIFIED")
    observed, known = _utc(body.get("observed_at")), _utc(body.get("known_at"))
    if observed is None or known is None:
        return _result(connection_state="CONNECTED", reason="CORE_XREF_TIMESTAMP_INVALID")
    if observed > known or known > clock + timedelta(minutes=5):
        return _result(link_status="CONFLICT", connection_state="CONNECTED", reason="CORE_MAPPING_CLOCK_CONFLICT")
    if clock - observed > timedelta(minutes=5) or clock - known > timedelta(minutes=5):
        return _result(link_status="STALE", connection_state="CONNECTED", reason="CORE_MAPPING_STALE")
    return _result(link_status="VERIFIED", connection_state="CONNECTED",
                   reason="AUTHENTICATED_TENANT_SCOPED_CORE_READBACK",
                   tenant_id=tenant_id, glpi_instance_id=glpi_instance_id,
                   ticket_id=ticket_id, incident_id=body["incident_id"],
                   run_id=body["run_id"], source_event_id=body["source_event_id"],
                   association_id=body["association_id"],
                   mapping_version=body["mapping_version"],
                   observed_at=body["observed_at"], known_at=body["known_at"],
                   provenance=body["provenance"])
