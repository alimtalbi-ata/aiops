"""Read-only GLPI consumer for an AIOps2 ITSM handoff.

Performs an authenticated GLPI REST Ticket GET, validates both incident and run
markers, and emits a deterministic reconciliation proposal. Never creates or
modifies a ticket, posts to Core, or authorizes Worker execution.
A GLPI readback is not evidence of a durable Core xref.
"""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def _ticket_get(base_url, ticket_id, session_token, app_token=None, timeout=10):
    base = base_url.rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid GLPI base URL")
    if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("remote GLPI requires HTTPS")
    headers = {"Accept": "application/json", "Session-Token": session_token}
    if app_token:
        headers["App-Token"] = app_token
    url = base + "/apirest.php/Ticket/" + str(ticket_id)
    with urlopen(Request(url, headers=headers, method="GET"), timeout=timeout) as response:
        return json.load(response)


def consume(handoff, ticket_id, base_url, session_token, app_token=None, timeout=10):
    if not isinstance(handoff, dict) or handoff.get("schema") != "aiops2-itsm-handoff-v1":
        raise ValueError("invalid handoff")
    if handoff.get("requested_operation") != "UPSERT_INCIDENT_TRACKING" or handoff.get("delivery_status") != "NOT_SENT":
        raise ValueError("handoff state not supported")
    if handoff.get("execute_worker") is not False or handoff.get("create_ticket_authorized") is not False:
        raise ValueError("handoff must prohibit execution and ticket creation")
    run_id = handoff.get("run_id")
    incident_id = handoff.get("incident_id")
    key = handoff.get("idempotency_key")
    if not all(isinstance(v, str) and v for v in (run_id, incident_id, key)):
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
    if not session_token:
        result["reason"] = "GLPI_AUTH_REQUIRED"
        return result
    try:
        ticket = _ticket_get(base_url, ticket_id, session_token, app_token, timeout)
    except HTTPError as exc:
        result["reason"] = "GLPI_AUTH_REQUIRED" if exc.code in (401, 403) else "GLPI_HTTP_ERROR"
        result["http_status"] = exc.code
        return result
    except (URLError, TimeoutError, OSError, ValueError):
        result["reason"] = "GLPI_CONNECTION_ERROR"
        return result
    if not isinstance(ticket, dict) or str(ticket.get("id")) != str(ticket_id):
        result["reason"] = "GLPI_TICKET_ID_MISMATCH"
        return result
    # Require both exact markers. A ticket title alone or an incidental #201
    # observation must not be treated as a verified case identity.
    text = str(ticket.get("name") or "") + "\n" + str(ticket.get("content") or "")
    if run_id not in text or incident_id not in text:
        result["reason"] = "GLPI_CORRELATION_MARKERS_MISSING"
        result["run_marker_present"] = run_id in text
        result["incident_marker_present"] = incident_id in text
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff_json")
    parser.add_argument("--ticket-id", type=int, required=True)
    parser.add_argument("--base-url", default=os.environ.get("AIOPS2_GLPI_BASE_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args(argv)
    try:
        with open(args.handoff_json, encoding="utf-8") as stream:
            handoff = json.load(stream)
        result = consume(handoff, args.ticket_id, args.base_url,
                         os.environ.get("AIOPS2_GLPI_SESSION_TOKEN"),
                         os.environ.get("AIOPS2_GLPI_APP_TOKEN"), args.timeout)
    except (ValueError, OSError, UnicodeError) as exc:
        result = {"status": "HOLD", "reason": type(exc).__name__}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_CORE_RECONCILIATION" else 2


if __name__ == "__main__":
    sys.exit(main())
