"""Validate raw Core/GLPI readback shapes without inventing canonical identity.

The legacy Core GET /api/runs/{id} returns a nested 'run' with run_id,
incident_id and mode, but does NOT provide tenant, GLPI instance/entity or
ticket identity. The legacy GLPI GET Ticket/{id} provides ticket id and
entities_id but does NOT attest Core incident/run or tenant. Those missing
values MUST come from an independently authorized canonical xref resolver,
never from ticket text or caller-supplied flags.
"""


class RawReadbackInvalid(ValueError):
    pass


def normalize_core_run_readback(payload, *, expected_run_id):
    if not isinstance(payload, dict) or not isinstance(payload.get("run"), dict):
        raise RawReadbackInvalid("core_run_missing")
    run = payload["run"]
    if not isinstance(expected_run_id, str) or run.get("run_id") != expected_run_id:
        raise RawReadbackInvalid("core_run_mismatch")
    if not isinstance(run.get("incident_id"), str) or not run["incident_id"]:
        raise RawReadbackInvalid("core_incident_missing")
    if run.get("mode") != "DEMO":
        raise RawReadbackInvalid("core_mode_not_qualified")
    return {"run_id": run["run_id"], "incident_id": run["incident_id"],
            "mode": run["mode"]}


def normalize_glpi_ticket_readback(payload, *, expected_ticket_id):
    if not isinstance(payload, dict):
        raise RawReadbackInvalid("glpi_ticket_missing")
    ticket = payload.get("id")
    entity = payload.get("entities_id")
    if type(ticket) not in (str, int) or type(entity) not in (str, int):
        raise RawReadbackInvalid("glpi_ticket_or_entity_missing")
    ticket, entity = str(ticket), str(entity)
    if (not ticket.isascii() or not ticket.isdecimal()
            or ticket.startswith("0") or ticket != expected_ticket_id
            or not entity.isascii() or not entity.isdecimal()
            or len(entity) > 18):
        raise RawReadbackInvalid("glpi_ticket_or_entity_mismatch")
    return {"ticket_id": ticket, "glpi_entity_id": entity}
