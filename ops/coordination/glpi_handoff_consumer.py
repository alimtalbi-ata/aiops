"""Read-only handoff adapter using the existing GLPI owner's ticket reader.

The caller supplies a server-owned reader that enforces authentication and ACL.
No HTTP client, credential handling, scheduler or ticket writer lives here.
A successful readback is not proof of durable Core linkage or Worker execution.
This module is not an independently runnable GLPI client.
"""
import re
from urllib.error import HTTPError, URLError


def _has_marker(text, marker):
    # IDs embedded in a longer ID must never establish correlation.
    return re.search(r"(?<![\w-])" + re.escape(marker) + r"(?![\w-])", text) is not None


def consume(handoff, ticket_id, read_ticket=None):
    """Read once through a trusted existing connector, then propose Core linkage.

    read_ticket(ticket_id) must return an authorized GLPI Ticket dictionary.
    Never accept this callable or its credentials from browser/request data.
    Without a wired connector this adapter stays HOLD.
    """
    if not isinstance(handoff, dict) or handoff.get("schema") != "aiops2-itsm-handoff-v1":
        raise ValueError("invalid handoff")
    if handoff.get("requested_operation") != "UPSERT_INCIDENT_TRACKING" or handoff.get("delivery_status") != "NOT_SENT":
        raise ValueError("handoff state not supported")
    if (handoff.get("execution_authorized") is not False
            or handoff.get("execute_worker") is not False
            or handoff.get("create_ticket_authorized") is not False):
        raise ValueError("handoff must prohibit execution and ticket creation")
    run_id = handoff.get("run_id")
    incident_id = handoff.get("incident_id")
    key = handoff.get("idempotency_key")
    if (not all(isinstance(v, str) and v.strip() == v and v for v in (run_id, incident_id, key))
            or not run_id.startswith("RUN-")):
        raise ValueError("missing handoff identity")
    if handoff.get("correlation_id") != incident_id:
        raise ValueError("correlation mismatch")
    if type(ticket_id) is not int or ticket_id <= 0:
        raise ValueError("invalid ticket ID")
    result = {
        "schema": "aiops2-itsm-consumer-result-v1",
        "run_id": run_id,
        "incident_id": incident_id,
        "idempotency_key": key,
        "ticket_id": ticket_id,
        "operation": "READ_EXISTING_TICKET",
        "read_only": True,
        "worker_execution_authorized": False,
        "ticket_creation_authorized": False,
        "core_xref_persisted": False,
        "status": "HOLD",
        "reason": "GLPI_READBACK_NOT_VERIFIED",
    }
    if not callable(read_ticket):
        result["reason"] = "GLPI_EXISTING_READER_REQUIRED"
        return result
    try:
        ticket = read_ticket(ticket_id)
    except HTTPError as exc:
        result["reason"] = "GLPI_AUTH_REQUIRED" if exc.code in (401, 403) else "GLPI_HTTP_ERROR"
        result["http_status"] = exc.code
        return result
    except (URLError, TimeoutError, OSError, ValueError):
        result["reason"] = "GLPI_CONNECTION_ERROR"
        return result
    if (not isinstance(ticket, dict) or type(ticket.get("id")) is not int
            or ticket["id"] != ticket_id):
        result["reason"] = "GLPI_TICKET_ID_MISMATCH"
        return result
    # Require both exact markers. A ticket title alone or an incidental #201
    # observation must not be treated as a verified case identity.
    text = str(ticket.get("name") or "") + "\n" + str(ticket.get("content") or "")
    run_match = _has_marker(text, run_id)
    incident_match = _has_marker(text, incident_id)
    if not run_match or not incident_match:
        result["reason"] = "GLPI_CORRELATION_MARKERS_MISSING"
        result["run_marker_present"] = run_match
        result["incident_marker_present"] = incident_match
        return result
    result["glpi_readback_verified"] = True
    result["status"] = "READY_FOR_CORE_RECONCILIATION"
    result["reason"] = "GLPI_IDENTITY_VERIFIED_CORE_LINK_PENDING"
    result["proposed_core_xref"] = {
        "run_id": run_id,
        "incident_id": incident_id,
        "glpi_ticket_id": ticket_id,
        "idempotency_key": key,
    }
    return result
