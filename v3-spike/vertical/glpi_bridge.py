"""Explicit synthetic ticket binding; never publish followups."""
from glpi_demo import preview

def preview_ticket(client, ticket_id, followup_id, core, context, *, synthetic_ticket_id, synthetic_run_id):
    if type(ticket_id) is not int or ticket_id != synthetic_ticket_id:
        raise ValueError("ticket not explicitly bound to lab")
    if core["run"]["run_id"] != synthetic_run_id or core["run"]["mode"] != "DEMO":
        raise ValueError("run not explicitly bound to lab")
    ticket, followups = client.read_ticket(ticket_id)
    if ticket.get("id") != ticket_id or ticket.get("is_deleted",0) not in (0,"0",False):
        raise ValueError("ticket unavailable")
    if ticket.get("name") != "[SYNTHETIC] "+synthetic_run_id:
        raise ValueError("synthetic ticket marker missing")
    matches=[f for f in followups if f.get("id")==followup_id]
    if len(matches)!=1:
        raise ValueError("followup missing or ambiguous")
    return preview({"id":ticket_id,"synthetic":True,"run_id":synthetic_run_id},matches[0],core,context)
