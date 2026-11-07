"""Synchronous mandatory GLPI ticket gate for newly ingested incidents.

Opt-in with AIOPS_GLPI_TICKETS_REQUIRED=true. Fail closed if GLPI is unavailable.
A crash/timeout after remote POST leaves UNKNOWN, never an automatic duplicate.
"""
from fastapi import HTTPException
from shared.db import db
from core.glpi_client import Glpi,GlpiError

DDL="""create table if not exists aiops.glpi_ticket_links(
 incident_id text primary key references aiops.incidents(incident_id),
 glpi_ticket_id bigint unique,
 state text not null check(state in ('PENDING','CLAIMED','CONFIRMED','UNKNOWN','ERROR')),
 attempts integer not null default 0,
 last_error text,
 claimed_at timestamptz,
 confirmed_at timestamptz,
 created_at timestamptz not null default now()
)"""

def ensure_ticket(incident):
    iid=incident["incident_id"]
    # Verify configuration before creating a claim.
    try:client=Glpi()
    except GlpiError:raise HTTPException(503,"GLPI_API_NOT_CONFIGURED") from None
    with db() as c:
        c.execute(DDL)
        c.execute("""insert into aiops.glpi_ticket_links(incident_id,state)
                     values(%s,'PENDING') on conflict(incident_id) do nothing""",(iid,))
        row=c.execute("""select state,glpi_ticket_id from aiops.glpi_ticket_links
                         where incident_id=%s for update""",(iid,)).fetchone()
        if row[0]=="CONFIRMED":
            return {"state":"CONFIRMED","glpi_ticket_id":row[1]}
        if row[0]!="PENDING":
            raise HTTPException(503,"GLPI_TICKET_RECONCILIATION_REQUIRED")
        c.execute("""update aiops.glpi_ticket_links
                     set state='CLAIMED',claimed_at=now(),attempts=attempts+1
                     where incident_id=%s""",(iid,))
    try:
        with client:ticket_id=client.create(incident)
    except GlpiError:
        with db() as c:
            c.execute("""update aiops.glpi_ticket_links
                         set state='UNKNOWN',last_error='GLPI_REQUEST_OUTCOME_UNKNOWN'
                         where incident_id=%s and state='CLAIMED'""",(iid,))
        raise HTTPException(503,"GLPI_TICKET_RECONCILIATION_REQUIRED") from None
    with db() as c:
        c.execute("""update aiops.glpi_ticket_links
                     set state='CONFIRMED',glpi_ticket_id=%s,confirmed_at=now()
                     where incident_id=%s and state='CLAIMED'""",(ticket_id,iid))
    return {"state":"CONFIRMED","glpi_ticket_id":ticket_id}
