"""FS364: fail-closed correlation gate for the existing GLPI incident 147.

Pure validation only. No GLPI writes, workflow dispatch or HITL authority.
Persistence and authenticated service integration are separate requirements.
"""
import re

TICKET_ID = 147
REFERENCE = "AIOPS2-REAL-FS-20261106"
RUN_RE = re.compile(r"RUN-[A-F0-9]{16}\\Z")
ID_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{7,127}\\Z")


def qualify_link(alert, run, evidence, ticket):
    blocked = {"status": "BLOCKED", "reason": "CORRELATION_NOT_VERIFIED",
               "can_execute": False, "can_resolve": False}
    if not all(type(item) is dict for item in (alert, run, evidence, ticket)):
        return blocked
    if type(ticket.get("id")) is not int or ticket["id"] != TICKET_ID:
        return {**blocked, "reason": "WRONG_GLPI_TICKET"}
    if ticket.get("reference") != REFERENCE:
        return blocked
    fingerprint = alert.get("fingerprint")
    incident = run.get("incident_id")
    run_id = run.get("run_id")
    evidence_id = evidence.get("evidence_id")
    if not all(type(v) is str and ID_RE.fullmatch(v) for v in (fingerprint, incident, evidence_id)):
        return blocked
    if type(run_id) is not str or not RUN_RE.fullmatch(run_id):
        return blocked
    if (alert.get("status") != "firing" or alert.get("mode") != "DEMO"
            or run.get("mode") != "DEMO" or evidence.get("mode") != "DEMO"
            or run.get("alert_fingerprint") != fingerprint
            or evidence.get("run_id") != run_id
            or evidence.get("incident_id") != incident
            or evidence.get("alert_fingerprint") != fingerprint
            or run.get("glpi_ticket_id") != TICKET_ID
            or evidence.get("glpi_ticket_id") != TICKET_ID):
        return blocked
    if any(item.get("live_effects") is not False for item in (run, evidence)):
        return blocked
    return {"status": "CORRELATED_READ_ONLY", "reason": "NOT_AUTHORIZATION",
            "run_id": run_id, "incident_id": incident, "evidence_id": evidence_id,
            "glpi_ticket_id": TICKET_ID, "can_execute": False, "can_resolve": False}
